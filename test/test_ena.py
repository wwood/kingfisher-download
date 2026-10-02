#!/usr/bin/env python3

#=======================================================================
# Authors: Ben Woodcroft
#
# Unit tests.
#
# Copyright
#
# This is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License.
# If not, see <http://www.gnu.org/licenses/>.
#=======================================================================

import unittest
import os.path
import sys
from unittest import mock

import extern
import pytest

sys.path = [os.path.join(os.path.dirname(os.path.realpath(__file__)),'..')]+sys.path
from kingfisher import ena as kingfisher_ena
kingfisher = os.path.join(os.path.dirname(os.path.realpath(__file__)),'..','bin','kingfisher')

from bird_tool_utils import in_tempdir

class Tests(unittest.TestCase):
    maxDiff = None
    
    @pytest.mark.flaky
    def test_fastq_gz(self):
        cmd_stub = '{} get -r SRR12118866 -m'.format(kingfisher)
        with in_tempdir():
            extern.run("{} {}".format(cmd_stub,'ena-ascp'))
            self.assertTrue(os.path.getsize('SRR12118866_1.fastq.gz')==4117481)
            self.assertTrue(os.path.getsize('SRR12118866_2.fastq.gz')==4945891)

    @pytest.mark.flaky
    def test_fastq_via_ena_ascp(self):
        with in_tempdir():
            extern.run('{} get -r SRR12118866 -m ena-ascp --output-format-possibilities fastq'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866_1.fastq')==19930812)
            self.assertTrue(os.path.getsize('SRR12118866_2.fastq')==19930812)

    @pytest.mark.flaky
    def test_fasta_via_ena_ascp(self):
        with in_tempdir():
            extern.run('{} get -r SRR12118866 -m ena-ascp --output-format-possibilities fasta.gz fasta'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866_1.fasta')==10391100)
            self.assertTrue(os.path.getsize('SRR12118866_2.fasta')==10391100)

    @pytest.mark.flaky
    def test_fasta_gz_via_ena_ascp(self):
        with in_tempdir():
            extern.run('{} get -r SRR12118866 -m ena-ascp --output-format-possibilities fasta.gz'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866_1.fasta.gz')==746749)
            self.assertTrue(os.path.getsize('SRR12118866_2.fasta.gz')==899862)

    def test_fasta_gz_via_ena_ftp(self):
        '''not sure why but this fails on travis'''
        with in_tempdir():
            extern.run('{} get -r SRR12118866 -m ena-ftp --output-format-possibilities fasta.gz'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866_1.fasta.gz')==746749)
            self.assertTrue(os.path.getsize('SRR12118866_2.fasta.gz')==899862)

    def test_fasta_gz_via_ena_ftp_output_directory(self):
        with in_tempdir():
            extern.run('{} get -r SRR12118866 -m ena-ftp --output-format-possibilities fasta.gz --output-directory outdir'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('outdir/SRR12118866_1.fasta.gz')==746749)
            self.assertTrue(os.path.getsize('outdir/SRR12118866_2.fasta.gz')==899862)

    def test_aria2_aws_fasta(self):
        '''cannot test this in travis because conda aria2 is broken'''
        with in_tempdir():
            extern.run('{} get --download-threads 4 -r SRR12118866 -m aws-http --output-format-possibilities fasta.gz'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866_1.fasta.gz')==633881)
            self.assertTrue(os.path.getsize('SRR12118866_2.fasta.gz')==788010)

    def test_aria2_aws_fasta_output_directory(self):
        '''cannot test this in travis because conda aria2 is broken'''
        with in_tempdir():
            extern.run('{} get --download-threads 4 -r SRR12118866 -m aws-http --output-format-possibilities fasta.gz --output-directory outdir'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('outdir/SRR12118866_1.fasta.gz')==633881)
            self.assertTrue(os.path.getsize('outdir/SRR12118866_2.fasta.gz')==788010)

    def test_aria2_ena_fastq_gz(self):
        '''cannot test this in travis because conda aria2 is broken'''
        with in_tempdir():
            extern.run('{} get --download-threads 4 -r SRR12118866 -m ena-ftp -f fastq.gz'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866_1.fastq.gz')==4117481)
            self.assertTrue(os.path.getsize('SRR12118866_2.fastq.gz')==4945891)

    def test_aria2_ena_fastq_gz_check_md5sum(self):
        '''cannot test this in travis because conda aria2 is broken'''
        with in_tempdir():
            extern.run('{} get --download-threads 4 -r SRR12118866 -m ena-ftp -f fastq.gz --check-md5sums 2>kingfisher_stderr'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866_1.fastq.gz')==4117481)
            self.assertTrue(os.path.getsize('SRR12118866_2.fastq.gz')==4945891)
            with open('kingfisher_stderr') as f:
                stderr = f.read()
                self.assertTrue('MD5sum OK for SRR12118866_1.fastq.gz' in stderr)
                self.assertTrue('MD5sum OK for SRR12118866_2.fastq.gz' in stderr)
                self.assertFalse('MD5sum failed' in stderr)

    def test_aria2_ena_fastq_gz_check_md5sum_mismatch(self):
        '''Downloads real bytes via aria2c (needs network) against a deliberately wrong MD5, and checks they are rejected and deleted'''
        downloader = kingfisher_ena.EnaDownloader()
        real_report = downloader.get_ftp_download_urls('SRR12118866')
        wrong_report = kingfisher_ena.EnaFileReport(
            real_report.file_paths, ['0' * 32] * len(real_report.md5sums))
        with in_tempdir():
            with mock.patch.object(kingfisher_ena.EnaDownloader, 'get_ftp_download_urls',
                                   lambda _self, run_id: wrong_report):
                with self.assertLogs(level='ERROR') as logs:
                    result = downloader.download_with_curl(
                        'SRR12118866', 4, os.getcwd(), check_md5sums=True)
            self.assertFalse(result)
            self.assertTrue(any('MD5sum failed' in line for line in logs.output))
            self.assertEqual([], os.listdir('.'))


if __name__ == "__main__":
    unittest.main()
