"""Exercise actual SRA extraction, conversion, and semantic naming without stubs."""
import gzip
import hashlib
from pathlib import Path

import pytest

import kingfisher
from kingfisher.exception import KingfisherException

DATA = Path(__file__).resolve().parent / 'data'


def read_fastq(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt') as handle:
        lines = handle.read().splitlines()
    assert lines and len(lines) % 4 == 0
    records = []
    for i in range(0, len(lines), 4):
        header, sequence, separator, quality = lines[i:i + 4]
        assert header.startswith('@') and separator.startswith('+')
        assert len(sequence) == len(quality)
        records.append((header, sequence, quality))
    return records


@pytest.mark.parametrize('output_format', ['fastq', 'fastq.gz'])
def test_real_technical_reads_preserve_every_stream(tmp_path, output_format):
    # This existing 148 kB 454 run has three technical streams and one biological
    # stream. Custom names describe its deposited order without implying Illumina.
    baseline = tmp_path / 'numbered'
    named = tmp_path / 'named'
    names = ('KEY', 'BARCODE', 'LINKER', 'R1')
    numbered = kingfisher.extract(
        sra_file=str(DATA / 'DRR002803.sra'), include_technical=True,
        output_format_possibilities=['fastq'], output_directory=str(baseline), threads=2)
    outputs = kingfisher.extract(
        sra_file=str(DATA / 'DRR002803.sra'), include_technical=True,
        read_layout='custom', read_names=','.join(names),
        output_format_possibilities=[output_format], output_directory=str(named), threads=2)
    assert [Path(p).name for p in outputs] == [
        'DRR002803_{}.{}'.format(name, output_format) for name in names]
    assert len(numbered) == 4
    for source, target in zip(numbered, outputs):
        expected = read_fastq(source)
        assert len(expected) == 116
        assert read_fastq(target) == expected
    assert not list(named.glob('DRR002803_[1-4].*'))


@pytest.mark.parametrize('output_format,style', [('fastq', 'simple'), ('fastq.gz', 'illumina')])
def test_gse141701_real_subset(tmp_path, output_format, style):
    source = DATA / 'SRR10612247.first100.sra'
    outputs = kingfisher.extract(
        sra_file=str(source), include_technical=True, read_layout='10x-gex',
        read_name_style=style, sample_name='ECs', threads=2,
        output_format_possibilities=[output_format], output_directory=str(tmp_path))
    pattern = 'ECs_{}.{}' if style == 'simple' else 'ECs_S1_{}_001.{}'
    assert [Path(p).name for p in outputs] == [
        pattern.format(name, output_format) for name in ('R1', 'R2')]
    records = [read_fastq(path) for path in outputs]
    # Hash sequence and quality strings against the original fastq-dump export.
    # Headers change when the bounded reads are repacked into the fixture archive.
    assert [hashlib.sha256(''.join(seq + qual for _, seq, qual in reads).encode()).hexdigest()
            for reads in records] == [
        '3cdbb1eeb4b4a40e69744924fee005e0eae5d57cfde8ef161c56b5f589eb439a',
        'c61705f4b340d43cd1e79030811faa22d1c9c7877a38d4e4def21b844fb4ee7e']
    assert [len(reads) for reads in records] == [100, 100]
    assert all(len(record[1]) == 26 for record in records[0])
    assert all(len(record[1]) == 98 for record in records[1])
    assert [record[0].split()[0] for record in records[0]] == [
        record[0].split()[0] for record in records[1]]
    # Existing semantic outputs should be reused on a repeat request.
    assert kingfisher.extract(
        sra_file=str(source), include_technical=True, read_layout='10x-gex',
        read_name_style=style, sample_name='ECs', threads=2,
        output_format_possibilities=[output_format], output_directory=str(tmp_path)) == outputs


def test_gse141701_layout_mismatch_leaves_numbered_reads(tmp_path):
    with pytest.raises(KingfisherException, match='expected 4 read streams but found 2'):
        kingfisher.extract(
            sra_file=str(DATA / 'SRR10612247.first100.sra'),
            include_technical=True, read_layout='illumina-pe-dual-index',
            output_format_possibilities=['fastq'], output_directory=str(tmp_path), threads=2)
    assert len(list(tmp_path.glob('SRR10612247.first100_[12].fastq'))) == 2
    assert not list(tmp_path.glob('*_R*.fastq'))
