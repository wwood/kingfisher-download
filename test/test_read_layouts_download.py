"""Network integration tests using a complete 148 kB public SRA run."""
import subprocess
import sys
from pathlib import Path

import pytest

from test_read_layouts_real_sra import read_fastq

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize('method', ['aws-http', 'prefetch'])
def test_download_and_extract_real_technical_reads(tmp_path, method):
    result = subprocess.run([
        sys.executable, str(ROOT / 'bin' / 'kingfisher'), 'get',
        '-r', 'DRR002803', '-m', method, '-f', 'fastq.gz',
        '--include-technical', '--read-layout', 'custom',
        '--read-names', 'KEY,BARCODE,LINKER,R1',
        '--output-directory', str(tmp_path), '-t', '2'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    assert result.returncode == 0, result.stderr.decode()
    files = sorted(tmp_path.glob('DRR002803_*.fastq.gz'))
    assert {p.name for p in files} == {
        'DRR002803_{}.fastq.gz'.format(name) for name in ('KEY', 'BARCODE', 'LINKER', 'R1')}
    assert all(len(read_fastq(path)) == 116 for path in files)
    assert not (tmp_path / 'DRR002803.sra').exists()
