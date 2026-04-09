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
from io import StringIO

import extern
import pandas as pd

sys.path = [os.path.join(os.path.dirname(os.path.realpath(__file__)),'..')]+sys.path
kingfisher = os.path.join(os.path.dirname(os.path.realpath(__file__)),'..','bin','kingfisher')

from bird_tool_utils import in_tempdir

class NgdcTests(unittest.TestCase):
    maxDiff = None

    # CRR302577 is a small paired-end 16S run (~14 MB total) from CRA004536
    TEST_RUN = 'CRR302577'

    def test_ngdc_http_fastq_gz(self):
        with in_tempdir():
            extern.run('{} get -r {} -m ngdc-http'.format(kingfisher, self.TEST_RUN))
            self.assertTrue(os.path.getsize('{}_f1.fastq.gz'.format(self.TEST_RUN)) == 6478403)
            self.assertTrue(os.path.getsize('{}_r2.fastq.gz'.format(self.TEST_RUN)) == 8310697)

    def test_ngdc_http_with_cra_accession(self):
        with in_tempdir():
            extern.run('{} get -r {} -m ngdc-http --cra-accession CRA004536'.format(kingfisher, self.TEST_RUN))
            self.assertTrue(os.path.getsize('{}_f1.fastq.gz'.format(self.TEST_RUN)) == 6478403)
            self.assertTrue(os.path.getsize('{}_r2.fastq.gz'.format(self.TEST_RUN)) == 8310697)

    def test_ngdc_ascp_fastq_gz(self):
        with in_tempdir():
            extern.run('{} get -r {} -m ngdc-ascp ngdc-http'.format(kingfisher, self.TEST_RUN))
            self.assertTrue(os.path.getsize('{}_f1.fastq.gz'.format(self.TEST_RUN)) == 6478403)
            self.assertTrue(os.path.getsize('{}_r2.fastq.gz'.format(self.TEST_RUN)) == 8310697)

    def test_ngdc_annotate_csv(self):
        stdout = extern.run('{} annotate -r {} -f csv --all-columns'.format(kingfisher, self.TEST_RUN))
        df = pd.read_csv(StringIO(stdout))
        self.assertEqual(len(df), 1)
        self.assertEqual(df['run'].iloc[0], self.TEST_RUN)
        self.assertEqual(df['cra_accession'].iloc[0], 'CRA004536')
        self.assertIn('CRR302577_f1.fastq.gz', df['filenames'].iloc[0])
        self.assertIn('CRR302577_r2.fastq.gz', df['filenames'].iloc[0])
        # Stats from the _sta.xml file on the download server
        self.assertEqual(df['bases'].iloc[0], 32365928)
        self.assertEqual(df['spots'].iloc[0], 53764)
        self.assertEqual(df['library_layout'].iloc[0], 'PAIRED')


if __name__ == "__main__":
    unittest.main()
