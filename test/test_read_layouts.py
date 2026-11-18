import os

import pytest

from kingfisher.exception import KingfisherException
from kingfisher.read_layouts import (
    READ_LAYOUTS,
    apply_read_layout,
    canonical_read_layout,
    parse_custom_read_names,
    read_names_for_layout,
    require_technical_reads_for_sra,
)


@pytest.mark.parametrize('layout,count,expected', [
    ('illumina-se', 1, ('R1',)),
    ('illumina-pe', 2, ('R1', 'R2')),
    ('illumina-se-single-index', 2, ('R1', 'I1')),
    ('illumina-se-dual-index', 3, ('R1', 'I1', 'I2')),
    ('illumina-pe-single-index', 3, ('R1', 'I1', 'R2')),
    ('illumina-pe-dual-index', 4, ('R1', 'I1', 'I2', 'R2')),
    ('10x-atac', 4, ('R1', 'I1', 'I2', 'R2')),
    ('10x-atac-bcl', 4, ('R1', 'I1', 'R2', 'R3')),
])
def test_fixed_layout_registry(layout, count, expected):
    assert read_names_for_layout(layout, count) == expected


def test_parse_aliases_reference_canonical_layouts():
    assert canonical_read_layout('parse-wt-single-index') == 'illumina-pe-single-index'
    assert canonical_read_layout('parse-wt-dual-index') == 'illumina-pe-dual-index'
    assert READ_LAYOUTS[canonical_read_layout('parse-wt-single-index')] is READ_LAYOUTS['illumina-pe-single-index']
    assert READ_LAYOUTS[canonical_read_layout('parse-wt-dual-index')] is READ_LAYOUTS['illumina-pe-dual-index']


@pytest.mark.parametrize('layout', ['10x-gex', '10x-vdj', '10x-spatial'])
@pytest.mark.parametrize('count,expected', [
    (2, ('R1', 'R2')),
    (3, ('R1', 'I1', 'R2')),
    (4, ('R1', 'I1', 'I2', 'R2')),
])
def test_flexible_10x_layouts(layout, count, expected):
    assert read_names_for_layout(layout, count) == expected


def test_custom_layout():
    assert read_names_for_layout('custom', 4, 'R1,BC1,BC2,R2') == (
        'R1', 'BC1', 'BC2', 'R2')


@pytest.mark.parametrize('names', ['R1,I1,R2', 'R1,,R2'])
def test_custom_layout_rejects_wrong_count_or_empty_name(names):
    with pytest.raises(KingfisherException):
        read_names_for_layout('custom', 4, names)


@pytest.mark.parametrize('names', ['R1,../escape,R2', 'R1,bad/name,R2',
                                    'R1,bad\\name,R2', 'R1,R1'])
def test_custom_layout_rejects_unsafe_or_duplicate_names(names):
    with pytest.raises(KingfisherException):
        parse_custom_read_names(names)


def _create_streams(tmp_path, extension='fastq.gz'):
    paths = []
    for number in range(1, 5):
        path = tmp_path / 'RUN_{}.{}'.format(number, extension)
        path.write_bytes('stream {}'.format(number).encode())
        paths.append(str(path))
    return paths


def test_simple_rename_preserves_compressed_contents(tmp_path):
    sources = _create_streams(tmp_path)

    outputs = apply_read_layout(
        sources, 'RUN', 'illumina-pe-dual-index', read_name_style='simple')

    assert [os.path.basename(path) for path in outputs] == [
        'RUN_R1.fastq.gz', 'RUN_I1.fastq.gz',
        'RUN_I2.fastq.gz', 'RUN_R2.fastq.gz']
    assert [open(path, 'rb').read() for path in outputs] == [
        b'stream 1', b'stream 2', b'stream 3', b'stream 4']
    assert not any(os.path.exists(path) for path in sources)


def test_illumina_style_and_sample_name(tmp_path):
    sources = _create_streams(tmp_path, 'fasta')

    outputs = apply_read_layout(
        sources, 'RUN', '10x-atac-bcl', read_name_style='illumina',
        sample_name='patient01')

    assert [os.path.basename(path) for path in outputs] == [
        'patient01_S1_R1_001.fasta', 'patient01_S1_I1_001.fasta',
        'patient01_S1_R2_001.fasta', 'patient01_S1_R3_001.fasta']


def test_layout_count_mismatch_renames_nothing(tmp_path):
    sources = _create_streams(tmp_path)[:2]
    for path in _create_streams(tmp_path)[2:]:
        os.remove(path)

    with pytest.raises(KingfisherException, match='expected 4 read streams but found 2'):
        apply_read_layout(sources, 'RUN', 'illumina-pe-dual-index')

    assert all(os.path.exists(path) for path in sources)


def test_collision_check_happens_before_any_rename(tmp_path):
    sources = _create_streams(tmp_path)
    (tmp_path / 'RUN_I2.fastq.gz').write_bytes(b'existing')

    with pytest.raises(KingfisherException, match='already exist'):
        apply_read_layout(sources, 'RUN', 'illumina-pe-dual-index')

    assert all(os.path.exists(path) for path in sources)
    assert (tmp_path / 'RUN_I2.fastq.gz').read_bytes() == b'existing'


def test_force_replaces_colliding_target(tmp_path):
    sources = _create_streams(tmp_path)
    (tmp_path / 'RUN_I2.fastq.gz').write_bytes(b'existing')

    outputs = apply_read_layout(
        sources, 'RUN', 'illumina-pe-dual-index', force=True)

    assert (tmp_path / 'RUN_I2.fastq.gz').read_bytes() == b'stream 3'
    assert all(os.path.exists(path) for path in outputs)


def test_sra_layout_is_noop(tmp_path):
    sources = _create_streams(tmp_path)
    assert apply_read_layout(sources, 'RUN') == sources
    assert all(os.path.exists(path) for path in sources)


def test_index_layout_requires_technical_reads_for_sra():
    with pytest.raises(KingfisherException, match='--include-technical'):
        require_technical_reads_for_sra('10x-gex', False)
    require_technical_reads_for_sra('illumina-pe', False)


@pytest.mark.parametrize('sample', ['../patient', 'bad/name', 'bad\\name'])
def test_unsafe_sample_name_rejected(tmp_path, sample):
    sources = _create_streams(tmp_path)
    with pytest.raises(KingfisherException, match='Unsafe sample name'):
        apply_read_layout(sources, 'RUN', 'illumina-pe-dual-index', sample_name=sample)
    assert all(os.path.exists(path) for path in sources)
