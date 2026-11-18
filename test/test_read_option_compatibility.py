"""Read-option validation must run before metadata requests or filesystem writes."""
from unittest import mock

import pytest

import kingfisher
from kingfisher.exception import KingfisherException
from kingfisher.read_layouts import SRA_DOWNLOAD_METHODS, validate_read_extraction_options


@pytest.mark.parametrize('methods', [
    ['ena-ftp'], ['ena-ascp'], ['ngdc-http'], ['ngdc-ascp'],
    ['prefetch', 'ena-ftp'], ['ena-ftp', 'prefetch'],
    ['aws-http', 'ngdc-http', 'prefetch'],
])
@pytest.mark.parametrize('options', [
    {'include_technical': True},
    {'read_layout': 'illumina-pe'},
    {'read_layout': 'custom', 'read_names': 'R1,R2'},
    {'read_layout': '10x-gex', 'include_technical': True},
])
def test_rejects_direct_fastq_methods_before_any_side_effect(tmp_path, methods, options):
    destination = tmp_path / 'must-not-be-created'
    with mock.patch('kingfisher.OutputLocation') as output, \
            mock.patch('kingfisher.SraMetadata') as metadata, \
            mock.patch('kingfisher.extern.run') as run, \
            mock.patch('kingfisher.EnaDownloader') as ena, \
            mock.patch('kingfisher.NgdcDownloader') as ngdc, \
            mock.patch('kingfisher.NcbiLocationJson') as ncbi:
        # A BioProject would otherwise trigger metadata lookup before per-run checks.
        with pytest.raises(KingfisherException, match='Incompatible download method'):
            kingfisher.download_and_extract(
                run_identifiers=None, run_identifiers_file=None,
                bioproject_accessions=['PRJNA594401'], download_methods=methods,
                output_directory=str(destination), **options)
        with pytest.raises(KingfisherException, match='Incompatible download method'):
            kingfisher.download_and_extract_one_run(
                'SRR10612247', download_methods=methods,
                output_directory=str(destination), **options)
        for boundary in (output, metadata, run, ena, ngdc, ncbi):
            boundary.assert_not_called()
    assert not destination.exists()


@pytest.mark.parametrize('method', SRA_DOWNLOAD_METHODS)
@pytest.mark.parametrize('options', [
    {'include_technical': True},
    {'read_layout': 'illumina-pe'},
    {'read_layout': '10x-gex', 'include_technical': True},
])
def test_accepts_sra_methods(method, options):
    validate_read_extraction_options(download_methods=[method], **options)


@pytest.mark.parametrize('options,message', [
    ({'read_layout': '10x-gex'}, 'Use --include-technical'),
    ({'read_layout': 'illumina-pe', 'stdout': True}, '--stdout'),
    ({'include_technical': True, 'stdout': True}, '--stdout'),
    ({'read_layout': 'illumina-pe', 'output_format_possibilities': ['sra']}, 'Remove'),
    ({'include_technical': True, 'output_format_possibilities': ['fastq', 'sra']}, 'Remove'),
    ({'sample_name': 'sample'}, 'require a non-default'),
    ({'read_name_style': 'illumina'}, 'require a non-default'),
])
def test_invalid_options_fail_before_download_or_extraction(tmp_path, options, message):
    with mock.patch('kingfisher.OutputLocation') as output, \
            mock.patch('kingfisher.extern.run') as run:
        with pytest.raises(KingfisherException, match=message):
            kingfisher.download_and_extract_one_run(
                'RUN', download_methods=['prefetch'], output_directory=str(tmp_path),
                **options)
        with pytest.raises(KingfisherException, match=message):
            kingfisher.extract(sra_file='RUN.sra', output_directory=str(tmp_path), **options)
        output.assert_not_called()
        run.assert_not_called()


def test_default_options_still_allow_direct_fastq_and_sra_output():
    validate_read_extraction_options(download_methods=['ena-ftp', 'ngdc-http'])
    validate_read_extraction_options(download_methods=['prefetch'],
                                     output_format_possibilities=['sra'])


@pytest.mark.parametrize('options', [
    ['--include-technical'], ['--read-layout', 'illumina-pe'],
])
def test_cli_rejects_mixed_methods_before_download(tmp_path, options):
    import subprocess
    import sys
    from pathlib import Path
    result = subprocess.run([
        sys.executable, str(Path(__file__).resolve().parent.parent / 'bin' / 'kingfisher'),
        'get', '-r', 'SRR10612247', '-m', 'prefetch', 'ena-ftp',
        '--output-directory', str(tmp_path / 'absent')] + options,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    assert result.returncode == 1
    assert b'Incompatible download method(s): ena-ftp' in result.stderr
    assert b'Traceback' not in result.stderr
    assert not (tmp_path / 'absent').exists()
