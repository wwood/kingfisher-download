#!/usr/bin/env python3

#=======================================================================
# Authors: Ben Woodcroft
#
# Unit tests for NGDC/GSA download methods.
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

import extern

sys.path = [os.path.join(os.path.dirname(os.path.realpath(__file__)),'..')]+sys.path
kingfisher = os.path.join(os.path.dirname(os.path.realpath(__file__)),'..','bin','kingfisher')

from bird_tool_utils import in_tempdir

class NgdcTests(unittest.TestCase):
    maxDiff = None

    # CRR302577 is a small paired-end 16S run (~14 MB total) from CRA004536
    TEST_RUN = 'CRR302577'

    def test_ngdc_ftp_fastq_gz(self):
        with in_tempdir():
            extern.run('{} get -r {} -m ngdc-ftp'.format(kingfisher, self.TEST_RUN))
            self.assertTrue(os.path.exists('{}_f1.fastq.gz'.format(self.TEST_RUN)))
            self.assertTrue(os.path.exists('{}_r2.fastq.gz'.format(self.TEST_RUN)))
            self.assertTrue(os.path.getsize('{}_f1.fastq.gz'.format(self.TEST_RUN)) > 0)
            self.assertTrue(os.path.getsize('{}_r2.fastq.gz'.format(self.TEST_RUN)) > 0)

    def test_ngdc_ascp_fastq_gz(self):
        with in_tempdir():
            extern.run('{} get -r {} -m ngdc-ascp'.format(kingfisher, self.TEST_RUN))
            self.assertTrue(os.path.exists('{}_f1.fastq.gz'.format(self.TEST_RUN)))
            self.assertTrue(os.path.exists('{}_r2.fastq.gz'.format(self.TEST_RUN)))
            self.assertTrue(os.path.getsize('{}_f1.fastq.gz'.format(self.TEST_RUN)) > 0)
            self.assertTrue(os.path.getsize('{}_r2.fastq.gz'.format(self.TEST_RUN)) > 0)


if __name__ == "__main__":
    unittest.main()
