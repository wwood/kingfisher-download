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
kingfisher = os.path.join(os.path.dirname(os.path.realpath(__file__)),'..','bin','kingfisher')

from bird_tool_utils import in_tempdir

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

    def test_aws_guess_location(self):
        with in_tempdir():
            extern.run('{} get -r SRR12118866 -m aws-http --output-format-possibilities sra --guess_aws_location'.format(
                kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866.sra')==11643188)

    def test_aws_cp_covid(self):
        with in_tempdir():
            extern.run('{} get -r ERR6167542 --force -f sra -m aws-cp'.format(kingfisher))
            self.assertTrue(os.path.getsize('ERR6167542.sra')==3463862)

    def test_stdout_unsorted_fasta_via_sra(self):
        with in_tempdir():
            self.assertEqual('e53aeb5b0ae367d24bea4023ce940eea  -\n',
                extern.run('{} get -r SRR12118866 -m aws-http --output-format-possibilities fasta --stdout --unsorted |md5sum'.format(
                    kingfisher
                )))

    def test_extract_stdout_fasta(self):
        with in_tempdir():
            extern.run('{} get -r SRR12118866 -m aws-http --output-format-possibilities sra'.format(kingfisher))
            self.assertEqual('e53aeb5b0ae367d24bea4023ce940eea  -\n',
                extern.run('{} extract --sra SRR12118866.sra --output-format-possibilities fasta --stdout --unsorted |md5sum'.format(
                    kingfisher
                )))

    def test_unsorted_get_fasta_file_output(self):
        with in_tempdir():
            extern.run('{} get -r SRR12118866 -m aws-http --output-format-possibilities fasta --unsorted'.format(kingfisher))
            self.assertTrue(os.path.getsize('SRR12118866_1.fasta')==10122654)
            self.assertTrue(os.path.getsize('SRR12118866_2.fasta')==10122654)
            self.assertFalse(os.path.exists('SRR12118866.fasta'))

    def test_unsorted_extract_file_outputs(self):
        sra = f"test/data/SRR12118866.sra"

        if os.path.exists('SRR12118866_1.fasta'):
            os.remove('SRR12118866_1.fasta')
        if os.path.exists('SRR12118866_2.fasta'):
            os.remove('SRR12118866_2.fasta')

        extern.run('{} extract --sra {} --output-format-possibilities fasta --unsorted'.format(kingfisher, sra))
        self.assertTrue(os.path.getsize('SRR12118866_1.fasta')==10122654)
        self.assertTrue(os.path.getsize('SRR12118866_2.fasta')==10122654)
        self.assertFalse(os.path.exists('SRR12118866.fasta'))
        os.remove('SRR12118866_1.fasta')
        os.remove('SRR12118866_2.fasta')

        extern.run('{} extract --sra {} --output-format-possibilities fasta.gz --unsorted'.format(kingfisher, sra))
        self.assertEqual('fb284c28aac4513249b196ec75dc3c8d  -\n', extern.run('pigz -cd SRR12118866_1.fasta.gz |md5sum'))
        self.assertEqual('311f8898bd6d575ae3ec6a7188b08836  -\n', extern.run('pigz -cd SRR12118866_2.fasta.gz |md5sum'))
        self.assertFalse(os.path.exists('SRR12118866.fasta.gz'))
        os.remove('SRR12118866_1.fasta.gz')
        os.remove('SRR12118866_2.fasta.gz')

        extern.run('{} extract --sra {} --output-format-possibilities fastq --unsorted'.format(kingfisher, sra))
        self.assertTrue(os.path.getsize('SRR12118866_1.fastq')==19662366)
        self.assertTrue(os.path.getsize('SRR12118866_2.fastq')==19662366)
        self.assertFalse(os.path.exists('SRR12118866.fastq'))
        os.remove('SRR12118866_1.fastq')
        os.remove('SRR12118866_2.fastq')

        extern.run('{} extract --sra {} --output-format-possibilities fastq.gz --unsorted'.format(kingfisher, sra))
        self.assertTrue(os.path.getsize('SRR12118866_1.fastq.gz')==4009949)
        self.assertTrue(os.path.getsize('SRR12118866_2.fastq.gz')==4834456)
        self.assertFalse(os.path.exists('SRR12118866.fastq.gz'))
        os.remove('SRR12118866_1.fastq.gz')
        os.remove('SRR12118866_2.fastq.gz')

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

    def test_aws_failure_curl(self):
        with in_tempdir():
            with self.assertRaises(extern.ExternCalledProcessError):
                extern.run('{} get -r DRR014182_not --force -f sra -m aws-http --guess-aws-location'.format(kingfisher))
            self.assertFalse(os.path.exists('DRR014182.sra'))

    def test_aws_failure_aria2(self):
        with in_tempdir():
            with self.assertRaises(extern.ExternCalledProcessError):
                # As of writing DRR014182 actually doesn't exist at AWS.
                extern.run('{} get -r DRR014182 --force -f sra -m aws-http --guess-aws-location --download-threads 5'.format(kingfisher))
            self.assertFalse(os.path.exists('DRR014182.sra'))

    def test_prefetch_max_size_limit(self):
        with in_tempdir():
            with self.assertRaises(extern.ExternCalledProcessError):
                # As of writing DRR014182 actually doesn't exist at AWS.
                extern.run('{} get -r SRR12118866 -f sra -m prefetch --prefetch-max-size 1M'.format(kingfisher))
            self.assertFalse(os.path.exists('DRR014182.sra'))

    def test_get_run_identifiers_list(self):
        with in_tempdir():
            with open('runlist','w') as f:
                f.write('SRR12118864\n')
                f.write('SRR12118866\n')
            extern.run('{} get --run-identifiers-list runlist -f sra -m prefetch'.format(kingfisher))
            self.assertTrue(os.path.exists('SRR12118864.sra'))
            self.assertTrue(os.path.exists('SRR12118866.sra'))

    def test_aws_cp(self):
        with in_tempdir():
            extern.run('{} get -r SRR12118866 --force -f sra -m aws-cp'.format(kingfisher))
            self.assertTrue(os.path.exists('SRR12118866.sra'))     
            self.assertTrue(os.path.getsize('SRR12118866.sra')==11643188)

    def test_aws_http_md5sums(self):
        with in_tempdir():
            extern.run('{} get -r SRR12118866 --force -f sra -m aws-http --check-md5sums 2>kingfisher_stderr'.format(kingfisher))
            self.assertTrue(os.path.exists('SRR12118866.sra'))
            self.assertTrue(os.path.getsize('SRR12118866.sra')==11643188)
            with open('kingfisher_stderr') as f:
                stderr = f.read()
                self.assertTrue('MD5sum OK for SRR12118866.sra' in stderr)



    # def test_noqual(self):
    #     with in_tempdir():
    #         extern.run("{} -r ERR3209781 --allowable-output-formats ".format(kingfisher, ))
    #         self.assertTrue(os.path.getsize('ERR3209781_1.fasta')==21411192)
    #         self.assertTrue(os.path.getsize('ERR3209781_2.fasta')==21411192)

    # e.g. DRR014182
    # ERR1877729
    # ERR3209781 => all at gcp only, so leave that be for now I think.

if __name__ == "__main__":
    unittest.main()
