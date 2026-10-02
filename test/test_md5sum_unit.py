#!/usr/bin/env python3

import hashlib
import os
import sys
import tempfile
import unittest

sys.path = [os.path.join(os.path.dirname(os.path.realpath(__file__)),'..')] + sys.path

from kingfisher.md5sum import MD5


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.write(b"some read data\n")
        self.tmp.close()
        self.expected = hashlib.md5(b"some read data\n").hexdigest()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_correct_md5_passes(self):
        self.assertIs(MD5.check_md5sum(self.tmp.name, self.expected), True)

    def test_wrong_md5_fails(self):
        self.assertIs(MD5.check_md5sum(self.tmp.name, "0" * 32), False)

    def test_uppercase_md5_passes(self):
        self.assertIs(MD5.check_md5sum(self.tmp.name, self.expected.upper()), True)

    def test_surrounding_whitespace_ignored(self):
        self.assertIs(MD5.check_md5sum(self.tmp.name, " {}\n".format(self.expected)), True)


if __name__ == "__main__":
    unittest.main()
