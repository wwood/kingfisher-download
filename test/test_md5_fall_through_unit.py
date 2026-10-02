#!/usr/bin/env python3

import os
import sys

sys.path = [os.path.join(os.path.dirname(os.path.realpath(__file__)),'..')] + sys.path

import unittest
from unittest import mock

import kingfisher.cli

import fake_downloads
from fake_downloads import (
    BAD_FASTQ_GZ, BAD_SRA, ENA_FILE, GOOD_FASTQ_GZ, GOOD_SRA, ROUTES, RUN)


class Tests(fake_downloads.FakeDownloadsTestCase):
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


if __name__ == "__main__":
    unittest.main()
