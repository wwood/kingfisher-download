#!/usr/bin/env python3

__author__ = "Ben Woodcroft"
__copyright__ = "Copyright 2021"
__credits__ = ["Ben Woodcroft"]
__license__ = "GPL3+"
__maintainer__ = "Ben Woodcroft"
__email__ = "b.woodcroft near qut.edu.au"
__status__ = "Development"

import argparse
import logging
import subprocess
import os
import sys
import warnings
import tempfile
import json

import extern


class NcbiLocation:
    def __init__(self, j):
        self.j = j

    def service(self):
        if self.j['service'] == 's3':
            if 'sra-pub-run-odp' in self.j['link']:
                return 's3-odp'
            else:
                return 's3-pay'
        elif self.j['service'] == 'sra-ncbi':
            return 'sra'

    def s3_command_prefix(self, run_id):
        if self.service() == 's3-pay':
            return 'aws s3api get-object --bucket {} --key {} --request-payer requester'.format(
                self.j['bucket'], self.j['key'], os.path.basename(self.j[key])
            )
        elif self.service() == 's3-odp':
            return 'aws s3 cp s3://sra-pub-run-odp/sra/{}/{}'.format(run_id, run_id)
        else:
            raise Exception("Unexpected json location found: {}", self.j)

    def link(self):
        return self.j['link']


def get_ncbi_aws_locations(run_id):
    json_location_string = 'https://locate.ncbi.nlm.nih.gov/sdl/2/retrieve?location=s3.us-east-1&acc={}&location-type=forced&accept-charges=aws'.format(
        run_id
    )
    json_response = extern.run('curl -q \'{}\''.format(json_location_string))
    logging.debug("Got location JSON: {}".format(json_response))

    j = json.loads(json_response)
    if 'version' not in j or j['version'] != '2':
        raise Exception(
            "Unexpected json location string returned: {}", json_location_string)
    # TODO: Assumes there is only 1 result, which is all I've ever seen
    return list([list([NcbiLocation(l) for l in f['locations']]) for f in j['result'][0]['files'])

if __name__ == '__main__':
    parser= argparse.ArgumentParser(
        description='Download and extract reads from the NCBI SRA database. \
            Requires the SRA toolkit to be installed, available at \
            https://github.com/ncbi/sra-tools - a full list of conda \
            requirements is: python extern pigz sra-tools')
    parser.add_argument(
        'run_identifier',
        help='Run number to download e.g. ERR1739691')
    # parser.add_argument('--output-directory','--output_directory',
    # help='Output files to this directory [default: \'.\']',default='.')
    # parser.add_argument('--forward-only','--forward_only',
    # action="store_true", help='Forward reads only')
    # parser.add_argument('--reverse-only','--reverse_only',
    # action="store_true", help='Reverse reads only')
    # parser.add_argument('--ascp-args','--ascp_args',
    # help='extra arguments to pass to ascp e.g. \'-k 2\' to resume with a \
    #     sparse file checksum [default: \'\']',default='')
    parser.add_argument(
        '--download_method', '--download-method',
        help='how to download .sra file',
        choices=['aws-odp', 'prefetch', 'aws-cp'], required=True)
    parser.add_argument(
        '--extraction_method', '--extraction-method',
        help='how to extract .sra file',
        choices=['fastq-dump', 'fasterq-dump'],
        required=True)

    parser.add_argument('--debug', help='output debug information',
                        action="store_true", default=False)
    parser.add_argument('--quiet', help='only output errors',
                        action="store_true", default=False)
    args= parser.parse_args()

    if args.debug:
        loglevel= logging.DEBUG
    elif args.quiet:
        loglevel= logging.ERROR
    else:
        loglevel= logging.INFO
    logging.basicConfig(
        level=loglevel, format='%(asctime)s %(levelname)s: %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p')

    # Download phase
    if os.path.exists("{}.sra".format(args.run_identifier)):
        logging.info(
            "Skipping download of {} as the file already appears to exist")

    elif args.download_method == 'prefetch':
        extern.run("prefetch -o {}.sra {}".format(
            args.run_identifier, args.run_identifier))

    elif args.download_method == 'aws-http':
        locations= get_ncbi_aws_locations(args.run_identifier)
        odp_http_locations = list([l.link for l in locations if l.service == 'sra'])
        if len(odp_http_locations) > 0:
            logging.info("Found ODP link {}".format(odp_http_locations[0]))
            odp_link= odp_http_locations[0]
        else:
            raise Exception("No ODP URL could be found")

        logging.info(
            "Downloading .SRA file from AWS Open Data Program HTTP link ..")
        extern.run("curl -q -o {}.sra '{}'".format(args.run_identifier, odp_link))
        logging.info("Download finished")

    elif args.download_method == 'aws-cp':
        locations= get_ncbi_aws_locations(args.run_identifier)
        s3_locations = list([l for l in locations if l.service() in ('s3-pay', 's3-odp')])

        if len(s3_locations) > 0:
            logging.info("Found s3 link {}".format(s3_locations[0]))
            s3_location= s3_locations[0]
        else:
            raise Exception("No S3 location could be found")

        command= '{} {}.sra'.format(
            s3_location.s3_command_prefix, args.run_identifier
        )
        logging.info("Downloading from S3..")
        extern.run(command)

    else:
        raise Exception("Programming error")

    if args.extraction_method == 'fastq-dump':
        # Unfortunately the fasterq-dump method is incompatible with mkfifo and
        # therefore on the fly conversion to fasta and pigz compression
        extract_bash_script= '''
            set -e

            mkfifo SRR000001_1.fastq;
            mkfifo SRR000001_2.fastq;
            mkfifo SRR000001.fastq;
            fastq-dump --split-3 ./SRR000001.sra & pid=$!
            cat SRR000001_1.fastq fq2fa |pigz >SRR000001_1.fastq.gz &
            cat SRR000001_2.fastq fq2fa |pigz >SRR000001_2.fastq.gz &
            cat SRR000001.fastq fq2fa |pigz >SRR000001.fastq.gz &
            wait $pid;
            echo -n >SRR000001_1.fastq;
            echo -n >SRR000001_2.fastq;
            echo -n >SRR000001.fastq;
            wait;
            rm SRR000001_1.fastq SRR000001_2.fastq SRR000001.fastq;
            '''.replace('SRR000001', args.run_identifier).replace(
                'fq2fa', "|awk '{print \">\" substr($0,2);getline;print;getline;getline}'"
            ).replace('fastq.gz', 'fasta.gz')
        with tempfile.NamedTemporaryFile(prefix='ncbi-download', suffix='.bash') as tf:

            tf.write(extract_bash_script.encode())
            tf.flush()
            logging.debug(extern.run('cat {}'.format(tf.name)))

            logging.info("Running extraction script ..")
            stdout= extern.run('bash "{}"'.format(tf.name))
            logging.debug("script stdout: {}".format(stdout))

    elif args.extraction_method == 'fasterq-dump':
        extern.run("fasterq-dump ./{}.sra".format(args.run_identifier))

        def convert_file(stub):
            if os.path.exists("{}.fastq".format(stub)):
                return "fq2fa {}.fastq |pigz >{}.fasta.gz".format(
                    stub, stub
                ).replace('fq2fa', "awk '{print \">\" substr($0,2);getline;print;getline;getline}'")
            else:
                return None

        commands= []
        f0= convert_file(args.run_identifier)
        if f0 is not None: commands.append(f0)
        print(commands)
        f1= convert_file('{}_1'.format(args.run_identifier))
        if f1 is not None: commands.append(f1)
        print(commands)
        f2= convert_file('{}_2'.format(args.run_identifier))
        if f2 is not None: commands.append(f2)
        print(commands)

        logging.info(
            "Running FASTQ->FASTA conversions on {} files".format(len(commands)))
        extern.run_many(commands)
    else:
        raise Exception("Programming error")

logging.info("All done.")
