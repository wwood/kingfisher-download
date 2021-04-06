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
from extern import ExternCalledProcessError

class NcbiAwsLocation:
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
                self.j['bucket'], self.j['key']
            )
        elif self.service() == 's3-odp':
            return 'aws s3 cp s3://sra-pub-run-odp/sra/{}/{}'.format(run_id, run_id)
        else:
            raise Exception("Unexpected json location found: {}", self.j)

    def link(self):
        return self.j['link']


class NcbiGcpLocation:
    def __init__(self, j):
        self.j = j

    def gs_path(self):
        return 'gs://{}/{}'.format(self.j['bucket'], self.j['key'])

def get_ncbi_locations(run_id, location, accept_charges_str):
    json_location_string = 'https://locate.ncbi.nlm.nih.gov/sdl/2/retrieve?location={}&acc={}&location-type=forced&accept-charges={}'.format(
        location, run_id, accept_charges_str
    )
    json_response = extern.run('curl -q \'{}\''.format(json_location_string))
    logging.debug("Got location JSON: {}".format(json_response))

    j = json.loads(json_response)
    if 'version' not in j or j['version'] != '2':
        raise Exception(
            "Unexpected json location string returned: {}", json_location_string)
    # TODO: Assumes there is only 1 result, which is all I've ever seen
    return flatten_list(list([list([l for l in f['locations']]) for f in j['result'][0]['files']]))

def get_ncbi_aws_locations(run_id):
    return list([NcbiAwsLocation(l) for l in get_ncbi_locations(run_id, 's3.us-east-1', 'aws')])

def get_ncbi_gcp_locations(run_id):
    return list([NcbiGcpLocation(l) for l in get_ncbi_locations(run_id, 'gs.us', 'gcp')])

def flatten_list(_2d_list):
    flat_list = []
    # Iterate through the outer list
    for element in _2d_list:
        if type(element) is list:
            # If the element is of type list, iterate through the sublist
            for item in element:
                flat_list.append(item)
        else:
            flat_list.append(element)
    return flat_list

class DownloadMethodFailed(Exception):
    pass

if __name__ == '__main__':
    parser= argparse.ArgumentParser(
        description='Download and extract reads from the NCBI SRA database. \
            Requires the SRA toolkit to be installed, available at \
            https://github.com/ncbi/sra-tools - a full list of conda \
            requirements is: python extern pigz sra-tools')
    parser.add_argument(
        '--run-identifier','--run_identifier','-r',
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
        '-m','--download_methods', '--download-methods',
        nargs='+',
        help='how to download .sra file. One or more of \'aws-http\', \'prefetch\', \'aws-cp\', \'gcp-cp\'',
        choices=['aws-http', 'prefetch', 'aws-cp', 'gcp-cp'], required=True)
    parser.add_argument(
        '--gcp_project','--gcp-project',
        help='Downloading from Google Cloud buckets require a Google project to charge '
        '(they are requester-pays) e.g. \'my-project\'. This can alternately be set '
        'beforehand using \'gcloud config set project PROJECT_ID\'')
    # parser.add_argument(
    #     '--extraction_method', '--extraction-method',
    #     help='how to extract .sra file',
    #     choices=['fastq-dump', 'fasterq-dump'],
    #     required=True)
    parser.add_argument(
        '--allow_paid', '--allow-paid',
        help='allow aws to cp from retriever-pays s3 buckets',
        action='store_true')

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

    if args.allow_paid:
        allowable_sources = ('s3-pay', 's3-odp', 'gcp-cp')
    else:
        allowable_sources = ('s3-odp')

    # Download phase
    if os.path.exists("{}.sra".format(args.run_identifier)):
        logging.info(
            "Skipping download of {} as the file already appears to exist".format(args.run_identifier))

    else:
        worked = False
        for method in args.download_methods:
            logging.info("Attempting download method {} ..".format(method))
            if method == 'prefetch':
                try:
                    extern.run("prefetch -o {}.sra {}".format(
                        args.run_identifier, args.run_identifier))
                    worked = True
                except ExternCalledProcessError as e:
                    logging.warning("Method {} failed: Error was: {}".format(method, e))
                
            elif method == 'aws-http':
                locations = get_ncbi_aws_locations(args.run_identifier)
                odp_http_locations = list([l.link for l in locations if l.service == 'sra-odp'])
                if len(odp_http_locations) > 0:
                    logging.info("Found ODP link {}".format(odp_http_locations[0]))
                    odp_link = odp_http_locations[0]

                    logging.info(
                        "Downloading .SRA file from AWS Open Data Program HTTP link ..")
                    try:
                        extern.run("curl -q -o {}.sra '{}'".format(args.run_identifier, odp_link))
                        logging.info("Download finished")
                        worked = True
                    except ExternCalledProcessError as e:
                        logging.warning("Method {} failed: Error was: {}".format(method, e))
                else:
                    logging.warning("Method {} failed: No ODP URL could be found".format(method))

            elif method == 'aws-cp':
                locations = get_ncbi_aws_locations(args.run_identifier) 
                s3_locations = list([l for l in locations if l.service() in allowable_sources])

                if len(s3_locations) > 0:
                    s3_location = s3_locations[0]
                    logging.info("Found s3 link {}".format(s3_location.j['link']))

                    command = '{} {}.sra'.format(
                        s3_location.s3_command_prefix(args.run_identifier), args.run_identifier
                    )
                    logging.info("Downloading from S3..")
                    try:
                        extern.run(command)
                        worked = True
                    except ExternCalledProcessError as e:
                        logging.warning("Method {} failed: Error was: {}".format(method, e))
                else:
                    logging.warning("Method {} failed: No S3 location could be found".format(method))

            elif method == 'gcp-cp':
                if 'gcp-cp' in allowable_sources:
                    locations = get_ncbi_gcp_locations(args.run_identifier)
                    if len(locations) > 0:
                        loc = locations[0]
                        command = 'gsutil'
                        if args.gcp_project:
                            command = command + " -u {}".format(args.gcp_project)
                        else:
                            logging.info("Finding Google cloud project to charge")
                            project_id = extern.run('gcloud config get-value project').strip()
                            logging.info("Charging to project \'{}\'".format(project_id))
                            command = command + " -u {}".format(project_id)
                        command += ' cp {} {}.sra'.format(
                            loc.gs_path(), args.run_identifier
                        )
                        logging.info("Downloading from GCP..")
                        try:
                            extern.run(command)
                            worked = True
                        except ExternCalledProcessError as e:
                            logging.warning("Method {} failed: Error was: {}".format(method, e))
                    else:
                        logging.warning("Method {} failed: No GCP location could be found".format(method))
                else:
                    logging.warn("Not using method gcp-cp as --allow-paid was not specified")

            else:
                raise Exception("Unknown method: {}".format(method))
            
            if worked:
                logging.info("Method {} worked.".format(method))
                break
            else:
                logging.warning("Method {} failed".format(method))

        if worked is False:
            raise Exception("No more specified download methods, cannot continue")

    # if args.extraction_method == 'fastq-dump':
    #     # Unfortunately the fasterq-dump method is incompatible with mkfifo and
    #     # therefore on the fly conversion to fasta and pigz compression
    #     extract_bash_script= '''
    #         set -e

    #         mkfifo SRR000001_1.fastq;
    #         mkfifo SRR000001_2.fastq;
    #         mkfifo SRR000001.fastq;
    #         fastq-dump --split-3 ./SRR000001.sra & pid=$!
    #         cat SRR000001_1.fastq fq2fa |pigz >SRR000001_1.fastq.gz &
    #         cat SRR000001_2.fastq fq2fa |pigz >SRR000001_2.fastq.gz &
    #         cat SRR000001.fastq fq2fa |pigz >SRR000001.fastq.gz &
    #         wait $pid;
    #         echo -n >SRR000001_1.fastq;
    #         echo -n >SRR000001_2.fastq;
    #         echo -n >SRR000001.fastq;
    #         wait;
    #         rm SRR000001_1.fastq SRR000001_2.fastq SRR000001.fastq;
    #         '''.replace('SRR000001', args.run_identifier).replace(
    #             'fq2fa', "|awk '{print \">\" substr($0,2);getline;print;getline;getline}'"
    #         ).replace('fastq.gz', 'fasta.gz')
    #     with tempfile.NamedTemporaryFile(prefix='ncbi-download', suffix='.bash') as tf:

    #         tf.write(extract_bash_script.encode())
    #         tf.flush()
    #         logging.debug(extern.run('cat {}'.format(tf.name)))

    #         logging.info("Running extraction script ..")
    #         stdout= extern.run('bash "{}"'.format(tf.name))
    #         logging.debug("script stdout: {}".format(stdout))

    if True: #args.extraction_method == 'fasterq-dump':
        extern.run("fasterq-dump ./{}.sra".format(args.run_identifier))
        os.remove('{}.sra'.format(args.run_identifier))

        # def convert_file(stub):
        #     if os.path.exists("{}.fastq".format(stub)):
        #         return "fq2fa {}.fastq |pigz >{}.fasta.gz".format(
        #             stub, stub
        #         ).replace('fq2fa', "awk '{print \">\" substr($0,2);getline;print;getline;getline}'")
        #     else:
        #         return None

        # commands= []
        # f0= convert_file(args.run_identifier)
        # if f0 is not None: commands.append(f0)
        # print(commands)
        # f1= convert_file('{}_1'.format(args.run_identifier))
        # if f1 is not None: commands.append(f1)
        # print(commands)
        # f2= convert_file('{}_2'.format(args.run_identifier))
        # if f2 is not None: commands.append(f2)

        # logging.info(
        #     "Running FASTQ->FASTA conversions on {} files".format(len(commands)))
        # extern.run_many(commands)
    else:
        raise Exception("Programming error")

logging.info("All done.")
