#!/usr/bin/env python3

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
import kingfisher.cli
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


class Tests(unittest.TestCase):
    """Stubs out ENA/NCBI metadata and every external downloader, so that no
    network access is needed. The fake downloaders write whatever bytes the
    test registers in self.served."""

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

        patches = [
            mock.patch.object(kingfisher.ena.EnaDownloader, 'get_ftp_download_urls',
                              lambda _self, run_id: self.ena_report),
            mock.patch.object(kingfisher.Location, 'get_ncbi_locations',
                              lambda run_id: FakeNcbiLocations(self.aws_locations)),
            mock.patch.object(subprocess, 'check_call', self._fake_curl_or_aria2c),
            mock.patch.object(extern, 'run', self._fake_extern_run),
            mock.patch.object(kingfisher.ena, '_resolve_ascp', lambda: 'ascp'),
            mock.patch.object(kingfisher, 'gzip_test_files', lambda files: None),
        ]
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

    def download(self, methods, threads=1):
        kingfisher.download_and_extract_one_run(
            RUN,
            download_methods=methods,
            output_format_possibilities=['sra', 'fastq.gz'],
            check_md5sums=True,
            download_threads=threads,
            output_directory=self.outdir,
            ascp_ssh_key=__file__,
        )

    def files_left(self):
        return sorted(os.listdir(self.outdir))

    def test_mismatch_logs_deletes_file_and_fails_method(self):
        for method, threads in ROUTES:
            with self.subTest(method=method, threads=threads):
                self._reset()
                self.serve_route(method, served_good=False)
                with self.assertLogs(level='ERROR') as logs:
                    with self.assertRaisesRegex(Exception, "No more specified download methods"):
                        self.download([method], threads)
                self.assertTrue(any('MD5sum failed' in line for line in logs.output), logs.output)
                self.assertEqual([], self.files_left())

    def test_matching_md5_is_kept(self):
        for method, threads in ROUTES:
            with self.subTest(method=method, threads=threads):
                self._reset()
                self.serve_route(method, served_good=True)
                self.download([method], threads)
                expected_file = ENA_FILE if method.startswith('ena-') else '{}.sra'.format(RUN)
                self.assertEqual([expected_file], self.files_left())

    def test_next_method_used_after_mismatch(self):
        for method, threads in ROUTES:
            with self.subTest(method=method, threads=threads):
                self._reset()
                self.serve_route(method, served_good=False)
                # Correct bytes from a different route, which must be kept.
                if method.startswith('aws-'):
                    fallback, expected_file = 'ena-ftp', ENA_FILE
                    self.serve_ena(GOOD_FASTQ_GZ, GOOD_FASTQ_GZ)
                else:
                    fallback, expected_file = 'aws-http', '{}.sra'.format(RUN)
                    self.serve_aws('aws-a.example', GOOD_SRA, GOOD_SRA)
                self.download([method, fallback], threads)
                self.assertEqual([expected_file], self.files_left())

    def test_paired_mismatch_in_second_file_removes_both(self):
        files = ('{}_1.fastq.gz'.format(RUN), '{}_2.fastq.gz'.format(RUN))
        for method, threads in [('ena-ascp', 1), ('ena-ftp', 1), ('ena-ftp', 4)]:
            with self.subTest(method=method, threads=threads):
                self._reset()
                self.serve_ena(GOOD_FASTQ_GZ, GOOD_FASTQ_GZ, files)
                self.served[files[1]] = BAD_FASTQ_GZ
                with self.assertLogs(level='ERROR') as logs:
                    with self.assertRaisesRegex(Exception, "No more specified download methods"):
                        self.download([method], threads)
                self.assertTrue(any('MD5sum failed' in line for line in logs.output), logs.output)
                self.assertEqual([], self.files_left())

    def test_aws_http_tries_next_location_after_mismatch(self):
        self.serve_aws('aws-a.example', BAD_SRA, GOOD_SRA)
        self.serve_aws('aws-b.example', GOOD_SRA, GOOD_SRA)
        self.download(['aws-http'])
        path = os.path.join(self.outdir, '{}.sra'.format(RUN))
        with open(path, 'rb') as f:
            self.assertEqual(GOOD_SRA, f.read())

    def test_aws_http_keeps_good_location_over_later_bad_one(self):
        self.serve_aws('aws-a.example', GOOD_SRA, GOOD_SRA)
        self.serve_aws('aws-b.example', BAD_SRA, GOOD_SRA)
        self.download(['aws-http'])
        path = os.path.join(self.outdir, '{}.sra'.format(RUN))
        with open(path, 'rb') as f:
            self.assertEqual(GOOD_SRA, f.read())

    def test_cli_exits_non_zero_and_leaves_nothing_when_every_method_fails(self):
        self.serve_ena(BAD_FASTQ_GZ, GOOD_FASTQ_GZ)
        self.serve_aws('aws-a.example', BAD_SRA, GOOD_SRA)
        argv = ['kingfisher', 'get', '-r', RUN, '-m', 'ena-ftp', 'aws-http',
                '-f', 'sra', 'fastq.gz', '--check-md5sums', '--output-directory', self.outdir]
        with mock.patch.object(sys, 'argv', argv):
            with self.assertRaises(SystemExit) as cm:
                kingfisher.cli.main()
        self.assertNotEqual(0, cm.exception.code)
        self.assertEqual([], self.files_left())

    def _reset(self):
        """Reset state between subTests."""
        for f in os.listdir(self.outdir):
            os.remove(os.path.join(self.outdir, f))
        self.served.clear()
        self.aws_locations.clear()
        self.ena_report = EnaFileReport([], [])


if __name__ == "__main__":
    unittest.main()
