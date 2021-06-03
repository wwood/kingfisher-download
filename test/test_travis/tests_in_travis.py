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
import subprocess

import extern

sys.path = [os.path.join(os.path.dirname(os.path.realpath(__file__)),'..')]+sys.path
sys.path = [os.path.join(os.path.dirname(os.path.realpath(__file__)),'..','..')]+sys.path
kingfisher = os.path.join(os.path.dirname(os.path.realpath(__file__)),'..','..','bin','kingfisher')

from in_tempdir import in_tempdir

class Tests(unittest.TestCase):
    maxDiff = None
    
    def test_unpaid_methods(self):
        cmd_stub = '{} get -r SRR12118866 -m'.format(kingfisher)
        for method in ('aws-http','prefetch'):
            with in_tempdir():
                extern.run("{} {}".format(cmd_stub,method))
                self.assertTrue(os.path.getsize('SRR12118866_1.fastq')==21411192)
                self.assertTrue(os.path.getsize('SRR12118866_2.fastq')==21411192)

    def test_fasta_via_sra(self):
        with in_tempdir():
            extern.run('{} get -r SRR12118866 -m aws-http --output-format-possibilities fasta.gz fasta'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866_1.fasta')==10705596)
            self.assertTrue(os.path.getsize('SRR12118866_2.fasta')==10705596)

    def test_fasta_gz_via_sra(self):
        with in_tempdir():
            extern.run('{} get -r SRR12118866 -m aws-http --output-format-possibilities fasta.gz'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866_1.fasta.gz')==757641)
            self.assertTrue(os.path.getsize('SRR12118866_2.fasta.gz')==907591)

    def test_sra_via_aws(self):
        with in_tempdir():
            extern.run('{} get -r SRR12118866 -m aws-http --output-format-possibilities sra'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866.sra')==11643188)

    def test_stdout_unsorted_fasta_via_sra(self):
        self.assertEqual('7fc33e5ea211377de944b7bd603e213a  -\n',
            extern.run('{} get -r SRR12118866 -m aws-http --output-format-possibilities fasta --stdout --unsorted |md5sum'.format(
                kingfisher
            )))

    def test_extract_stdout_fasta(self):
        extern.run('{} get -r SRR12118866 -m aws-http --output-format-possibilities sra'.format(kingfisher))
        self.assertEqual('7fc33e5ea211377de944b7bd603e213a  -\n',
            extern.run('{} extract --sra SRR12118866.sra --output-format-possibilities fasta --stdout --unsorted |md5sum'.format(
                kingfisher
            )))

    def test_extract_fastq(self):
        with in_tempdir():
            extern.run('{} get -r SRR12118866 -m aws-http --output-format-possibilities sra'.format(kingfisher))
            extern.run('{} extract --sra SRR12118866.sra --output-format-possibilities fastq'.format(
                kingfisher
            ))
            self.assertTrue(os.path.getsize('SRR12118866_1.fastq')==21411192)
            self.assertTrue(os.path.getsize('SRR12118866_2.fastq')==21411192)

    def test_extract_fastq_no_force(self):
        with in_tempdir():
            extern.run('{} get -r SRR12118866 -m aws-http --output-format-possibilities sra'.format(kingfisher))
            # extern.run('touch SRR12118866.sra')
            extern.run('touch SRR12118866.fastq SRR12118866_1.fastq SRR12118866_2.fastq'.format(kingfisher))
            r = subprocess.run(['bash','-c','{} extract --sra SRR12118866.sra --output-format-possibilities fastq'.format(
                kingfisher
                )],
                stderr=subprocess.PIPE,
                check=True)
            self.assertTrue('SRR12118866 as an output file already appears to exist' in r.stderr.decode())

    def test_extract_fastq_force(self):
        with in_tempdir():
            extern.run('{} get -r SRR12118866 -m aws-http --output-format-possibilities sra'.format(kingfisher))
            # extern.run('touch SRR12118866.sra')
            extern.run('touch SRR12118866.fastq SRR12118866_1.fastq SRR12118866_2.fastq'.format(kingfisher))
            r = subprocess.run(['bash','-c','{} extract --sra SRR12118866.sra --output-format-possibilities fastq --force'.format(
                kingfisher
                )],
                stderr=subprocess.PIPE,
                check=True)
            self.assertTrue(os.path.getsize('SRR12118866_1.fastq')==21411192)
            self.assertTrue(os.path.getsize('SRR12118866_2.fastq')==21411192)
            self.assertFalse('SRR12118866 as an output file already appears to exist' in r.stderr.decode())

    def test_download_fastq_no_force(self):
        with in_tempdir():
            extern.run('touch SRR12118866.fastq SRR12118866_1.fastq SRR12118866_2.fastq'.format(kingfisher))
            r = subprocess.run(['bash','-c','{} get -m prefetch -r SRR12118866 --output-format-possibilities fastq'.format(
                kingfisher
                )],
                stderr=subprocess.PIPE,
                check=True)
            self.assertTrue('SRR12118866 as an output file already appears to exist' in r.stderr.decode())

    def download_force(self):
        with in_tempdir():
            extern.run('touch SRR12118866.fastq SRR12118866_1.fastq SRR12118866_2.fastq'.format(kingfisher))
            r = subprocess.run(['bash','-c','{} get -m prefetch -r SRR12118866 --output-format-possibilities fastq --force'.format(
                kingfisher
                )],
                stderr=subprocess.PIPE,
                check=True)
            self.assertTrue(os.path.getsize('SRR12118866_1.fastq')==21411192)
            self.assertTrue(os.path.getsize('SRR12118866_2.fastq')==21411192)
            self.assertFalse('SRR12118866 as an output file already appears to exist' in r.stderr.decode())

    # def test_noqual(self):
    #     with in_tempdir():
    #         extern.run("{} -r ERR3209781 --allowable-output-formats ".format(kingfisher, ))
    #         self.assertTrue(os.path.getsize('ERR3209781_1.fasta')==21411192)
    #         self.assertTrue(os.path.getsize('ERR3209781_2.fasta')==21411192)

if __name__ == "__main__":
    unittest.main()
