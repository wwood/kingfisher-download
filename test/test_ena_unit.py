#!/usr/bin/env python3

import os.path
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
