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

import extern

sys.path = [os.path.join(os.path.dirname(os.path.realpath(__file__)),'..')]+sys.path
sys.path = [os.path.join(os.path.dirname(os.path.realpath(__file__)),'..','..')]+sys.path
kingfisher = os.path.join(os.path.dirname(os.path.realpath(__file__)),'..','..','bin','kingfisher')

class Tests(unittest.TestCase):
    maxDiff = None
    
    def test_one_sample_annotate(self):
        self.assertEqual('Run        | SRAStudy  | Gbp   | LibraryStrategy | LibrarySelection | Model               | SampleName   | ScientificName\n' \
            '---------- | --------- | ----- | --------------- | ---------------- | ------------------- | ------------ | --------------\n' \
            'ERR1739691 | ERP017539 | 2.382 | WGS             | RANDOM           | Illumina HiSeq 2500 | SAMEA4497179 | metagenome    \n',
            extern.run('{} annotate -r ERR1739691 --debug'.format(kingfisher)))

    def test_one_project_annotate(self):
        self.assertEqual('Run        | SRAStudy  | Gbp   | LibraryStrategy | LibrarySelection | Model               | SampleName   | ScientificName\n' \
            '---------- | --------- | ----- | --------------- | ---------------- | ------------------- | ------------ | --------------\n' \
            'ERR1739691 | ERP017539 | 2.382 | WGS             | RANDOM           | Illumina HiSeq 2500 | SAMEA4497179 | metagenome    \n' \
            'ERR1739692 | ERP017539 | 2.382 | WGS             | RANDOM           | Illumina HiSeq 2500 | SAMEA4497180 | metagenome    \n' \
            'ERR1739693 | ERP017539 | 2.364 | WGS             | RANDOM           | Illumina HiSeq 2500 | SAMEA4497181 | metagenome    \n' \
            'ERR1739694 | ERP017539 | 2.501 | WGS             | RANDOM           | Illumina HiSeq 2500 | SAMEA4497182 | metagenome    \n' \
            'ERR1739695 | ERP017539 | 2.379 | WGS             | RANDOM           | Illumina HiSeq 2500 | SAMEA4497183 | metagenome    \n' \
            'ERR1739696 | ERP017539 | 2.351 | WGS             | RANDOM           | Illumina HiSeq 2500 | SAMEA4497184 | metagenome    \n' \
            'ERR1739697 | ERP017539 | 2.524 | WGS             | RANDOM           | Illumina HiSeq 2500 | SAMEA4497185 | metagenome    \n' \
            'ERR1739698 | ERP017539 | 2.358 | WGS             | RANDOM           | Illumina HiSeq 2500 | SAMEA4497186 | metagenome    \n' \
            'ERR1739699 | ERP017539 | 2.465 | WGS             | RANDOM           | Illumina HiSeq 2500 | SAMEA4497187 | metagenome    \n',
            extern.run('{} annotate -p PRJEB15706 --debug'.format(kingfisher)))

    def test_one_sample_annotate_csv(self):
        self.assertEqual('Run,SRAStudy,Gbp,LibraryStrategy,LibrarySelection,Model,SampleName,ScientificName,ReleaseDate,LoadDate,spots,bases,spots_with_mates,avgLength,size_MB,AssemblyName,download_path,Experiment,LibraryName,LibrarySource,LibraryLayout,InsertSize,InsertDev,Platform,BioProject,Study_Pubmed_id,ProjectID,Sample,BioSample,SampleType,TaxID,g1k_pop_code,source,g1k_analysis_group,Subject_ID,Sex,Disease,Tumor,Affection_Status,Analyte_Type,Histological_Type,Body_Site,CenterName,Submission,dbgap_study_accession,Consent,RunHash,ReadHash\n' \
            'ERR1739691,ERP017539,2.382,WGS,RANDOM,Illumina HiSeq 2500,SAMEA4497179,metagenome,2017-06-13 08:05:22,2017-06-13 08:09:29,7938968,2381690400,7938968,300,893,,https://sra-downloadb.st-va.ncbi.nlm.nih.gov/sos1/sra-pub-run-12/ERR1739691/ERR1739691.1,ERX1809317,unspecified,METAGENOMIC,PAIRED,800,0,ILLUMINA,PRJEB15706,,390087,ERS1396358,SAMEA4497179,simple,256318,,,,,,,no,,,,,ROYAL NETHERLANDS INSTITUTE FOR SEA RESEARCH,ERA767571,,public,8B5D4F846F55BA6589A6F4FF6D4379D1,6578A402A8F0902F56B2D1FF43882F98\n',
            extern.run('{} annotate -r ERR1739691 -f csv --all-columns'.format(kingfisher)))

if __name__ == "__main__":
    unittest.main()
