"""Shared fixture for network-free tests of kingfisher's download routes."""

import gzip
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path = [os.path.join(os.path.dirname(os.path.realpath(__file__)),'..')] + sys.path

import extern
import kingfisher
import kingfisher.ena
from kingfisher.ena import EnaFileReport

RUN = 'SRR0001'
ENA_FILE = '{}.fastq.gz'.format(RUN)
GOOD_FASTQ_GZ = gzip.compress(b"@r\nACGT\n+\nIIII\n")
BAD_FASTQ_GZ = gzip.compress(b"@r\nTTTT\n+\nIIII\n")
GOOD_SRA = b"NCBI.sra" + b"good bytes"
BAD_SRA = b"NCBI.sra" + b"corrupted bytes"

# Each route is (download method, download threads). Threads > 1 selects aria2c
# over curl for ena-ftp and aws-http.
ROUTES = [
    ('ena-ascp', 1),
    ('ena-ftp', 1),
    ('ena-ftp', 4),
    ('aws-http', 1),
    ('aws-http', 4),
]


def md5(data):
    return hashlib.md5(data).hexdigest()


class FakeAwsLocation:
    def __init__(self, link, md5sum):
        self._link = link
        self._md5sum = md5sum

    def link(self):
        return self._link

    def md5sum(self):
        return self._md5sum


class FakeNcbiLocations:
    def __init__(self, locations):
        self.locations = locations

    def object_locations(self, *args):
        return self.locations


class FakeDownloadsTestCase(unittest.TestCase):
    """Stubs out ENA/NCBI metadata and every external downloader, so that no
    network access is needed. The fake downloaders write whatever bytes the
    test registers in self.served.

    Subclasses set patch_gzip_check = False to run the real `pigz -t` on
    downloaded files."""

    patch_gzip_check = True

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.outdir = os.path.join(self.tmp.name, 'out')
        os.mkdir(self.outdir)
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, self.orig_cwd)

        # Substring of the download command -> bytes it writes.
        self.served = {}
        self.ena_report = EnaFileReport([], [])
        self.aws_locations = []
        self.real_extern_run = extern.run

        patches = [
            mock.patch.object(kingfisher.ena.EnaDownloader, 'get_ftp_download_urls',
                              lambda _self, run_id: self.ena_report),
            mock.patch.object(kingfisher.Location, 'get_ncbi_locations',
                              lambda run_id: FakeNcbiLocations(self.aws_locations)),
            mock.patch.object(subprocess, 'check_call', self._fake_curl_or_aria2c),
            mock.patch.object(extern, 'run', self._fake_extern_run),
            mock.patch.object(kingfisher.ena, '_resolve_ascp', lambda: 'ascp'),
        ]
        if self.patch_gzip_check:
            patches.append(mock.patch.object(kingfisher, 'gzip_test_files', lambda files: None))
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _bytes_for(self, cmd):
        for key, data in self.served.items():
            if key in cmd:
                return data
        raise AssertionError("Test did not register bytes for command: {}".format(cmd))

    def _fake_curl_or_aria2c(self, cmd, shell=False):
        output = re.search(r"-o (\S+)", cmd).group(1)
        with open(os.path.abspath(output), 'wb') as f:
            f.write(self._bytes_for(cmd))

    def _fake_extern_run(self, cmd, *args, **kwargs):
        if cmd.startswith('pigz -t') and not self.patch_gzip_check:
            return self.real_extern_run(cmd, *args, **kwargs)
        if 'fasp.sra.ebi.ac.uk' not in cmd:
            raise AssertionError("Unexpected external command: {}".format(cmd))
        # ascp ... era-fasp@fasp.sra.ebi.ac.uk:<remote path> <output directory>
        remote, output_directory = cmd.split()[-2:]
        output = os.path.join(output_directory, os.path.basename(remote))
        with open(output, 'wb') as f:
            f.write(self._bytes_for(cmd))
        return ''

    def serve_ena(self, served, expected, files=(ENA_FILE,)):
        """ENA reports `files` with the md5 of `expected` bytes, but the
        downloader will actually write `served` bytes."""
        urls = ['ftp.sra.ebi.ac.uk/vol1/fastq/{}'.format(f) for f in files]
        self.ena_report = EnaFileReport(urls, [md5(expected)] * len(files))
        for f in files:
            self.served[f] = served

    def serve_aws(self, host, served, expected):
        self.served[host] = served
        self.aws_locations.append(
            FakeAwsLocation('https://{}/{}'.format(host, RUN), md5(expected)))

    def serve_route(self, method, served_good):
        if method.startswith('ena-'):
            self.serve_ena(GOOD_FASTQ_GZ if served_good else BAD_FASTQ_GZ, GOOD_FASTQ_GZ)
        else:
            self.serve_aws('aws-a.example', GOOD_SRA if served_good else BAD_SRA, GOOD_SRA)

    def download(self, methods, threads=1, check_md5sums=True):
        kingfisher.download_and_extract_one_run(
            RUN,
            download_methods=methods,
            output_format_possibilities=['sra', 'fastq.gz'],
            check_md5sums=check_md5sums,
            download_threads=threads,
            output_directory=self.outdir,
            ascp_ssh_key=__file__,
        )

    def files_left(self):
        return sorted(os.listdir(self.outdir))

    def _reset(self):
        """Reset state between subTests."""
        for f in os.listdir(self.outdir):
            os.remove(os.path.join(self.outdir, f))
        self.served.clear()
        self.aws_locations.clear()
        self.ena_report = EnaFileReport([], [])
