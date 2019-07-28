#!/usr/bin/env python3

__author__ = "Ben Woodcroft"
__copyright__ = "Copyright 2019"
__credits__ = ["Ben Woodcroft"]
__license__ = "GPL3+"
__maintainer__ = "Ben Woodcroft"
__email__ = "b.woodcroft near uq.edu.au"
__status__ = "Development"

import argparse
import logging
import subprocess

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Quickly download FASTQ files from the European Nucleotide Archive (ENA) using aspera.\n\n'
        'Requires curl and ascp (i.e. aspera, see https://www.biostars.org/p/325010/#389254) to be in the $PATH.')
    parser.add_argument('run_identifier',help='Run number to download e.g. ERR1739691')
    parser.add_argument('--output_directory',help='Output files to this directory [default: \'.\']',default='.')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG,format='%(asctime)s %(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

    # Use the example set out at this very helpful post:
    # https://www.biostars.org/p/325010

    run_id = args.run_identifier
    output_directory = args.output_directory

    # Get the textual representation of the run. We specifically need the fastq_ftp bit
    logging.info("Querying ENA for FTP paths ..")
    text = subprocess.check_output("curl --silent 'https://www.ebi.ac.uk/ena/data/warehouse/filereport?accession={}&result=read_run&fields=fastq_ftp&download=txt'".format(
        run_id),shell=True)

    ftp_urls = []
    header=True
    for line in text.decode('utf8').split('\n'):
        if header:
            header=False
        else:
            for url in line.split(';'):
                if url.strip() != '': ftp_urls.append(url.strip())
    logging.info("Found {} FTP URLs for download e.g. {}".format(len(ftp_urls), ftp_urls[1]))

    aspera_commands = []
    for url in ftp_urls:
        cmd = "ascp -QT -l 300m -P33001 -i $HOME/.aspera/connect/etc/asperaweb_id_dsa.openssh era-fasp@fasp.sra.ebi.ac.uk:{} {}".format(
            url.replace('ftp.sra.ebi.ac.uk',''), output_directory)
        logging.info("Running command: {}".format(cmd))
        subprocess.check_call(cmd,shell=True)

logging.info("All done.")
