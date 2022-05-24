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
kingfisher = os.path.join(os.path.dirname(os.path.realpath(__file__)),'..','bin','kingfisher')

class Tests(unittest.TestCase):
    maxDiff = None
    
    def test_one_sample_annotate(self):
        self.assertEqual(
            'run        | study_accession | Gbp   | library_strategy | library_selection | model               | sample_name | taxon_name\n' \
            '---------- | --------------- | ----- | ---------------- | ----------------- | ------------------- | ----------- | ----------\n' \
            'ERR1739691 | ERP017539       | 2.382 | WGS              | RANDOM            | Illumina HiSeq 2500 | MM1_1       | metagenome\n',
            extern.run('{} annotate -r ERR1739691 --debug'.format(kingfisher)))

    def test_one_project_annotate(self):
        self.assertEqual('run        | study_accession | Gbp   | library_strategy | library_selection | model               | sample_name | taxon_name\n' \
        '---------- | --------------- | ----- | ---------------- | ----------------- | ------------------- | ----------- | ----------\n' \
        'ERR1739691 | ERP017539       | 2.382 | WGS              | RANDOM            | Illumina HiSeq 2500 | MM1_1       | metagenome\n' \
        'ERR1739692 | ERP017539       | 2.382 | WGS              | RANDOM            | Illumina HiSeq 2500 | MM1_2       | metagenome\n' \
        'ERR1739693 | ERP017539       | 2.364 | WGS              | RANDOM            | Illumina HiSeq 2500 | MM1_3       | metagenome\n' \
        'ERR1739694 | ERP017539       | 2.501 | WGS              | RANDOM            | Illumina HiSeq 2500 | MM1_4       | metagenome\n' \
        'ERR1739695 | ERP017539       | 2.379 | WGS              | RANDOM            | Illumina HiSeq 2500 | MM1_5       | metagenome\n' \
        'ERR1739696 | ERP017539       | 2.351 | WGS              | RANDOM            | Illumina HiSeq 2500 | MM1_6       | metagenome\n' \
        'ERR1739697 | ERP017539       | 2.524 | WGS              | RANDOM            | Illumina HiSeq 2500 | MM1_7       | metagenome\n' \
        'ERR1739698 | ERP017539       | 2.358 | WGS              | RANDOM            | Illumina HiSeq 2500 | MM1_8       | metagenome\n' \
        'ERR1739699 | ERP017539       | 2.465 | WGS              | RANDOM            | Illumina HiSeq 2500 | MM1_9       | metagenome\n',
            extern.run('{} annotate -p PRJEB15706 --debug'.format(kingfisher)))

    def test_one_sample_annotate_csv(self):
        self.assertEqual('run,study_accession,Gbp,library_strategy,library_selection,model,sample_name,taxon_name,experiment_accession,experiment_title,library_name,library_source,submitter,study_alias,study_centre_project_name,organisation,organisation_department,organisation_institution,organisation_street,organisation_city,organisation_country,organisation_contact_name,organisation_contact_email,sample_description,sample_alias,sample_accession,ENA first public,ENA last update,External Id,INSDC center alias,INSDC center name,INSDC first public,INSDC last update,INSDC status,Submitter Id,collection date,depth,environment (biome),environment (feature),environment (material),geographic location (country and/or sea),geographic location (depth),geographic location (elevation),geographic location (latitude),geographic location (longitude),investigation type,microbial mat/biofilm environmental package,project name,sample name,sample storage duration,sample storage temperature,sequencing method,study_title,design_description,study_abstract,study_links,number_of_runs_for_sample,spots,bases,run_size,published,read1_length_average,read1_length_stdev,read2_length_average,read2_length_stdev\n' \
            'ERR1739691,ERP017539,2.382,WGS,RANDOM,Illumina HiSeq 2500,MM1_1,metagenome,ERX1809317,Illumina HiSeq 2500 paired end sequencing,unspecified,METAGENOMIC,European Nucleotide Archive,ena-STUDY-NIOZ-10-10-2016-11:18:17:022-1157,Minimal Mat 1,Royal Netherlands Institute for Sea Research,,,,,, ,,"artificial minimal coastal microbial mats at dilution 0, replicate 1",SAMEA4497179,ERS1396358,2017-06-08,2016-11-23,SAMEA4497179,NIOZ,Royal Netherlands Institute for Sea Research,2017-06-08T17:01:18Z,2016-11-23T11:15:32Z,public,MM1_1,2015-11,0.01,Microbial Mat Material,Beach,soil,Netherlands,0,0,53.489606,6.139913,metagenome,microbial mat/biofilm,Minimal Mat,MM1_1,10,20,illumina PE100,construction of minimal coastal microbial mats,,"Minimal coastal microbial mats were created with diluted coastal mat samples obtained from the Dutch barrier island of Schiermonnikoog. The MM\'s were inoculated in fresh sterilized sand in glass containers contained in a MicroBox. The MicroBox has a transparent lid (allowing photosynthetic growth) and a gas exchange filter. The MM\'s are propagated under laboratory conditions at a 16h light / 8h dark regime and at a constant 23 C. Serial dilutions used for this data-set are 0, 3 and 5-fold.",[],1,7938968,2381690400,936643449,2017-06-13 08:05:22,150,0,150,0\n',
            extern.run('{} annotate -r ERR1739691 -f csv --all-columns'.format(kingfisher)))

if __name__ == "__main__":
    unittest.main()
