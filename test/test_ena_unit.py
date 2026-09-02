#!/usr/bin/env python3

import json
import os
import os.path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path = [os.path.join(os.path.dirname(os.path.realpath(__file__)),'..')] + sys.path

import kingfisher.ena


class Tests(unittest.TestCase):
    def test_get_ftp_download_urls_handles_unexpected_response(self):
        original_run = kingfisher.ena.extern.run
        try:
            kingfisher.ena.extern.run = lambda _: "accession\nERR123\n"
            result = kingfisher.ena.EnaDownloader().get_ftp_download_urls("ERR123")
            self.assertFalse(result)
        finally:
            kingfisher.ena.extern.run = original_run

    def test_specified_ssh_key_is_used(self):
        with tempfile.NamedTemporaryFile(suffix='.pem') as key:
            self.assertEqual(
                key.name, kingfisher.ena.resolve_ena_ssh_key(key.name))

    def test_specified_ssh_key_must_exist(self):
        with self.assertRaises(Exception):
            kingfisher.ena.resolve_ena_ssh_key('/not/a/real/aspera/key.pem')

    def test_rsa_key_found_in_aspera_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            sdk_dir = os.path.join(tmp, '.aspera', 'sdk')
            os.makedirs(sdk_dir)
            key = os.path.join(sdk_dir, kingfisher.ena.ASPERA_BYPASS_RSA_KEY_NAME)
            with open(key, 'w') as f:
                f.write('not really a key')
            with mock.patch.dict(os.environ, {'HOME': tmp}):
                for ssh_key in kingfisher.ena.AUTOMATIC_SSH_KEY_SPECIFICATIONS:
                    self.assertEqual(key, kingfisher.ena.resolve_ena_ssh_key(ssh_key))

    def test_falls_back_to_bundled_dsa_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {'HOME': tmp, 'PATH': tmp}):
                self.assertEqual(
                    kingfisher.ena.DEFAULT_LINUX_ASPERA_SSH_KEY_LOCATION,
                    kingfisher.ena.resolve_ena_ssh_key(None))

    def test_rsa_key_found_near_ascp(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = os.path.join(tmp, 'aspera', 'bin')
            etc_dir = os.path.join(tmp, 'aspera', 'etc')
            os.makedirs(bin_dir)
            os.makedirs(etc_dir)
            ascp = os.path.join(bin_dir, 'ascp')
            with open(ascp, 'w') as f:
                f.write('#!/bin/sh\n')
            os.chmod(ascp, 0o755)
            key = os.path.join(etc_dir, kingfisher.ena.ASPERA_BYPASS_RSA_KEY_NAME)
            with open(key, 'w') as f:
                f.write('not really a key')
            home = os.path.join(tmp, 'home')
            os.makedirs(home)
            with mock.patch.dict(os.environ, {'HOME': home, 'PATH': bin_dir}):
                self.assertEqual(key, kingfisher.ena.resolve_ena_ssh_key(None))

    def test_rsa_key_found_via_ascli(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = os.path.join(tmp, kingfisher.ena.ASPERA_BYPASS_RSA_KEY_NAME)
            with open(key, 'w') as f:
                f.write('not really a key')
            completed = subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout=json.dumps({'ssh_private_rsa': key}), stderr='')
            with mock.patch.dict(os.environ, {'HOME': tmp}), \
                    mock.patch.object(kingfisher.ena.shutil, 'which',
                                      side_effect=lambda x: '/usr/bin/ascli' if x == 'ascli' else None), \
                    mock.patch.object(kingfisher.ena, '_find_key_in_aspera_home', return_value=None), \
                    mock.patch.object(kingfisher.ena.subprocess, 'run', return_value=completed):
                self.assertEqual(key, kingfisher.ena.resolve_ena_ssh_key(None))

    def test_extract_key_path_from_ascli_output(self):
        extract = kingfisher.ena._extract_key_path_from_ascli_output
        self.assertEqual('/a/b.pem', extract(json.dumps({'ssh_private_rsa': '/a/b.pem'})))
        self.assertEqual('/a/b.pem', extract(json.dumps(
            [{'field': 'ssh_private_rsa', 'value': '/a/b.pem'}])))
        self.assertEqual('/a/b.pem', extract(json.dumps('/a/b.pem')))
        self.assertEqual(None, extract(''))
        self.assertEqual(None, extract('no path here'))
        self.assertEqual(__file__, extract(__file__))
        # Table-style output, as printed when --format=json is not accepted
        self.assertEqual(__file__, extract(
            '| field           | value      |\n'
            '| ssh_private_rsa | {} |\n'.format(__file__)))

    def test_ascp_is_run_with_empty_stdin(self):
        # Otherwise ascp hangs on a "Password:" prompt when the key is rejected
        recorded = {}

        def fake_run(command, stdin=None):
            recorded['command'] = command
            recorded['stdin'] = stdin
            raise Exception("ascp: failed to authenticate, exiting.")

        downloader = kingfisher.ena.EnaDownloader()
        report = kingfisher.ena.EnaFileReport(
            ['ftp.sra.ebi.ac.uk/vol1/fastq/ERR123/ERR123_1.fastq.gz'], ['0' * 32])
        original_run = kingfisher.ena.extern.run
        try:
            kingfisher.ena.extern.run = fake_run
            with mock.patch.object(kingfisher.ena, 'resolve_ena_ssh_key', return_value='/a/key.pem'), \
                    mock.patch.object(kingfisher.ena, '_resolve_ascp', return_value='ascp'), \
                    mock.patch.object(downloader, 'get_ftp_download_urls', return_value=report), \
                    tempfile.TemporaryDirectory() as tmp:
                self.assertFalse(downloader.download_with_aspera('ERR123', tmp))
        finally:
            kingfisher.ena.extern.run = original_run
        self.assertEqual('', recorded['stdin'])
        self.assertIn('-i /a/key.pem', recorded['command'])


if __name__ == "__main__":
    unittest.main()
