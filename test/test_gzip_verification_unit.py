#!/usr/bin/env python3

import os
import subprocess
import sys

sys.path = [os.path.join(os.path.dirname(os.path.realpath(__file__)),'..')] + sys.path

import extern
import fake_downloads
from fake_downloads import ENA_FILE, GOOD_FASTQ_GZ, GOOD_SRA, RUN

ENA_ROUTES = [('ena-ascp', 1), ('ena-ftp', 1), ('ena-ftp', 4)]
CORRUPT_GZIPS = {
    'not gzip at all': b"this is not gzip",
    'truncated gzip': GOOD_FASTQ_GZ[:-5],
}


class Tests(fake_downloads.FakeDownloadsTestCase):
    """The post-download `pigz -t` check runs for real here. It must work
    without --check-md5sums, and a failure must fail the method (deleting the
    file) rather than raise and leave a corrupt file that a later run would
    skip as already downloaded."""

    patch_gzip_check = False

    def test_valid_gzip_is_kept(self):
        for method, threads in ENA_ROUTES:
            with self.subTest(method=method, threads=threads):
                self._reset()
                self.serve_ena(GOOD_FASTQ_GZ, GOOD_FASTQ_GZ)
                self.download([method], threads, check_md5sums=False)
                self.assertEqual([ENA_FILE], self.files_left())

    def test_corrupt_gzip_fails_method_and_deletes_file(self):
        for description, corrupt in CORRUPT_GZIPS.items():
            for method, threads in ENA_ROUTES:
                with self.subTest(corrupt=description, method=method, threads=threads):
                    self._reset()
                    self.serve_ena(corrupt, GOOD_FASTQ_GZ)
                    with self.assertLogs(level='WARNING') as logs:
                        with self.assertRaisesRegex(Exception, "No more specified download methods"):
                            self.download([method], threads, check_md5sums=False)
                    self.assertTrue(any('Download verification failed' in line for line in logs.output), logs.output)
                    self.assertEqual([], self.files_left())

    def test_next_method_used_after_corrupt_gzip(self):
        for method, threads in ENA_ROUTES:
            with self.subTest(method=method, threads=threads):
                self._reset()
                self.serve_ena(CORRUPT_GZIPS['truncated gzip'], GOOD_FASTQ_GZ)
                self.serve_aws('aws-a.example', GOOD_SRA, GOOD_SRA)
                self.download([method, 'aws-http'], threads, check_md5sums=False)
                self.assertEqual(['{}.sra'.format(RUN)], self.files_left())

    def test_corrupt_second_file_of_pair_removes_both(self):
        files = ('{}_1.fastq.gz'.format(RUN), '{}_2.fastq.gz'.format(RUN))
        for method, threads in ENA_ROUTES:
            with self.subTest(method=method, threads=threads):
                self._reset()
                self.serve_ena(GOOD_FASTQ_GZ, GOOD_FASTQ_GZ, files)
                self.served[files[1]] = CORRUPT_GZIPS['truncated gzip']
                with self.assertRaisesRegex(Exception, "No more specified download methods"):
                    self.download([method], threads, check_md5sums=False)
                self.assertEqual([], self.files_left())

    def test_valid_download_is_kept_when_pigz_cannot_run(self):
        # Exit status 127 means pigz is missing, which says nothing about the
        # download, so the file must not be deleted.
        def pigz_not_found(cmd, *args, **kwargs):
            raise extern.ExternCalledProcessError(
                subprocess.CompletedProcess(cmd, 127, b'', b'pigz: command not found'), cmd)
        self.real_extern_run = pigz_not_found
        self.serve_ena(GOOD_FASTQ_GZ, GOOD_FASTQ_GZ)
        with self.assertRaisesRegex(Exception, "Download verification failed"):
            self.download(['ena-ftp'], 1, check_md5sums=False)
        self.assertEqual([ENA_FILE], self.files_left())


if __name__ == "__main__":
    import unittest
    unittest.main()
