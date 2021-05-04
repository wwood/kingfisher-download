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
import tempdir
import sys

import extern

sys.path = [os.path.join(os.path.dirname(os.path.realpath(__file__)),'..')]+sys.path
kingfisher = os.path.join(os.path.dirname(os.path.realpath(__file__)),'..','bin','kingfisher')

class Tests(unittest.TestCase):
    maxDiff = None
    
    def test_unpaid_methods(self):
        cmd_stub = '{} -r SRR12118866 -m'.format(kingfisher)
        for method in ('aws-http','prefetch'):
            with tempdir.in_tempdir():
                extern.run("{} {}".format(cmd_stub,method))
                self.assertTrue(os.path.getsize('SRR12118866_1.fastq')==21411192)
                self.assertTrue(os.path.getsize('SRR12118866_2.fastq')==21411192)
        
        with tempdir.in_tempdir():
            extern.run("{} {}".format(cmd_stub,'ena-ascp'))
            self.assertTrue(os.path.getsize('SRR12118866_1.fastq.gz')==4117481)
            self.assertTrue(os.path.getsize('SRR12118866_2.fastq.gz')==4945891)

    def test_fasta_via_sra(self):
        with tempdir.in_tempdir():
            extern.run('{} -r SRR12118866 -m aws-http --output-format-possibilities fasta.gz fasta'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866_1.fasta')==10705596)
            self.assertTrue(os.path.getsize('SRR12118866_2.fasta')==10705596)

    def test_fasta_gz_via_sra(self):
        with tempdir.in_tempdir():
            extern.run('{} -r SRR12118866 -m aws-http --output-format-possibilities fasta.gz'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866_1.fasta.gz')==757641)
            self.assertTrue(os.path.getsize('SRR12118866_2.fasta.gz')==907591)



    def test_fastq_via_ena_ascp(self):
        with tempdir.in_tempdir():
            extern.run('{} -r SRR12118866 -m ena-ascp --output-format-possibilities fastq'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866_1.fastq')==21411192)
            self.assertTrue(os.path.getsize('SRR12118866_2.fastq')==21411192)

    def test_fasta_via_ena_ascp(self):
        with tempdir.in_tempdir():
            extern.run('{} -r SRR12118866 -m ena-ascp --output-format-possibilities fasta.gz fasta'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866_1.fasta')==10391100)
            self.assertTrue(os.path.getsize('SRR12118866_2.fasta')==10391100)

    def test_fasta_gz_via_ena_ascp(self):
        with tempdir.in_tempdir():
            extern.run('{} -r SRR12118866 -m ena-ascp --output-format-possibilities fasta.gz'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866_1.fasta.gz')==746749)
            self.assertTrue(os.path.getsize('SRR12118866_2.fasta.gz')==899862)



    # def test_noqual(self):
    #     with tempdir.in_tempdir():
    #         extern.run("{} -r ERR3209781 --allowable-output-formats ".format(kingfisher, ))
    #         self.assertTrue(os.path.getsize('ERR3209781_1.fasta')==21411192)
    #         self.assertTrue(os.path.getsize('ERR3209781_2.fasta')==21411192)

    

if __name__ == "__main__":
    unittest.main()
