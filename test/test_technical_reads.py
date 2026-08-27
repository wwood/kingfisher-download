import gzip
import os
import subprocess
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
import kingfisher


@pytest.mark.parametrize('command', ['get', 'extract'])
def test_cli_accepts_include_technical_aliases(command):
    result = subprocess.run(
        [os.path.join(os.path.dirname(__file__), '..', 'bin', 'kingfisher'),
         command, '--help'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode == 0, result.stderr.decode()
    help_text = result.stdout.decode()
    assert '--include-technical' in help_text
    assert '--include_technical' in help_text
    assert '--read-layout' in help_text
    assert '--read_layout' in help_text
    assert '--read-names' in help_text
    assert '--read_names' in help_text
    assert '--read-name-style' in help_text
    assert '--read_name_style' in help_text
    assert '--sample-name' in help_text
    assert '--sample_name' in help_text


def test_find_numbered_read_files_uses_numeric_order(tmp_path):
    for number in (10, 2, 4, 1, 3):
        (tmp_path / 'RUN_{}.fastq'.format(number)).touch()
    (tmp_path / 'OTHER_5.fastq').touch()
    (tmp_path / 'RUN_6.fasta').touch()

    found = kingfisher.find_numbered_read_files('RUN', 'fastq', str(tmp_path))

    assert [os.path.basename(path) for path in found] == [
        'RUN_1.fastq', 'RUN_2.fastq', 'RUN_3.fastq',
        'RUN_4.fastq', 'RUN_10.fastq']


def _mock_fasterq(command):
    if command.startswith('fasterq-dump'):
        for number in range(1, 5):
            with open('RUN_{}.fastq'.format(number), 'w') as handle:
                handle.write('@read{}\nAC\n+\nII\n'.format(number))
        return
    if command.startswith('pigz -c'):
        source = command.split()[-3]
        destination = command.split()[-1]
        with open(source, 'rb') as source_handle:
            with gzip.open(destination, 'wb') as destination_handle:
                destination_handle.write(source_handle.read())
        return
    raise AssertionError('Unexpected command: {}'.format(command))


def test_include_technical_uses_fasterq_and_discovers_all_streams(tmp_path):
    with mock.patch('kingfisher.extern.run', side_effect=_mock_fasterq) as run:
        outputs = kingfisher.extract(
            sra_file=str(tmp_path / 'RUN.sra'),
            output_format_possibilities=['fastq'],
            include_technical=True,
            output_directory=str(tmp_path))

    command = run.call_args_list[0].args[0]
    assert '--include-technical' in command
    assert '--split-files' in command
    assert [os.path.basename(path) for path in outputs] == [
        'RUN_1.fastq', 'RUN_2.fastq', 'RUN_3.fastq', 'RUN_4.fastq']


def test_include_technical_compresses_all_streams(tmp_path):
    with mock.patch('kingfisher.extern.run', side_effect=_mock_fasterq):
        outputs = kingfisher.extract(
            sra_file=str(tmp_path / 'RUN.sra'),
            output_format_possibilities=['fastq.gz'],
            include_technical=True,
            output_directory=str(tmp_path))

    assert [os.path.basename(path) for path in outputs] == [
        'RUN_1.fastq.gz', 'RUN_2.fastq.gz',
        'RUN_3.fastq.gz', 'RUN_4.fastq.gz']
    assert all(os.path.exists(path) for path in outputs)


def test_include_technical_applies_layout_after_compression(tmp_path):
    with mock.patch('kingfisher.extern.run', side_effect=_mock_fasterq):
        outputs = kingfisher.extract(
            sra_file=str(tmp_path / 'RUN.sra'),
            output_format_possibilities=['fastq.gz'],
            include_technical=True,
            read_layout='illumina-pe-dual-index',
            output_directory=str(tmp_path))

    assert [os.path.basename(path) for path in outputs] == [
        'RUN_R1.fastq.gz', 'RUN_I1.fastq.gz',
        'RUN_I2.fastq.gz', 'RUN_R2.fastq.gz']


def test_default_extraction_still_uses_sracat(tmp_path):
    paired = [str(tmp_path / 'RUN_1.fastq'), str(tmp_path / 'RUN_2.fastq')]
    with mock.patch('kingfisher._extract_with_sracat', return_value=paired) as sracat:
        outputs = kingfisher.extract(
            sra_file=str(tmp_path / 'RUN.sra'),
            output_format_possibilities=['fastq'],
            output_directory=str(tmp_path))

    sracat.assert_called_once()
    assert outputs == paired


def test_nontechnical_paired_layout_uses_sracat_then_renames(tmp_path):
    paired = [str(tmp_path / 'RUN_1.fastq'), str(tmp_path / 'RUN_2.fastq')]

    def mock_sracat(*args):
        for path in paired:
            with open(path, 'w') as handle:
                handle.write('@read\nAC\n+\nII\n')
        return paired

    with mock.patch('kingfisher._extract_with_sracat', side_effect=mock_sracat) as sracat:
        outputs = kingfisher.extract(
            sra_file=str(tmp_path / 'RUN.sra'),
            output_format_possibilities=['fastq'],
            read_layout='illumina-pe',
            output_directory=str(tmp_path))

    sracat.assert_called_once()
    assert [os.path.basename(path) for path in outputs] == [
        'RUN_R1.fastq', 'RUN_R2.fastq']


def test_existing_file_detection_finds_all_numbered_streams(tmp_path):
    for number in range(1, 5):
        (tmp_path / 'RUN_{}.fastq'.format(number)).touch()
    location = kingfisher.OutputLocation(str(tmp_path))

    skip, outputs = kingfisher._check_for_existing_files(
        location, 'RUN', ['fastq'], force=False)

    assert skip is True
    assert [os.path.basename(path) for path in outputs] == [
        'RUN_1.fastq', 'RUN_2.fastq', 'RUN_3.fastq', 'RUN_4.fastq']


def test_existing_file_detection_uses_selected_semantic_style(tmp_path):
    names = ('R1', 'I1', 'I2', 'R2')
    for name in names:
        (tmp_path / 'patient_S1_{}_001.fastq.gz'.format(name)).touch()
    location = kingfisher.OutputLocation(str(tmp_path))

    skip, outputs = kingfisher._check_for_existing_files(
        location, 'RUN', ['fastq.gz'], False,
        read_layout='illumina-pe-dual-index',
        read_name_style='illumina', sample_name='patient')

    assert skip is True
    assert [os.path.basename(path) for path in outputs] == [
        'patient_S1_R1_001.fastq.gz', 'patient_S1_I1_001.fastq.gz',
        'patient_S1_I2_001.fastq.gz', 'patient_S1_R2_001.fastq.gz']
