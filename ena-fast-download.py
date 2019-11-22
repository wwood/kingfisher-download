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
import sys

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Quickly download FASTQ files from the European Nucleotide Archive (ENA) using aspera.\n\n'
        'Requires curl and ascp (i.e. aspera, see https://www.biostars.org/p/325010/#389254) to be in the $PATH.')
    parser.add_argument('run_identifier',help='Run number to download e.g. ERR1739691')
    parser.add_argument('--output-directory','--output_directory',help='Output files to this directory [default: \'.\']',default='.')
    parser.add_argument('--ssh-key','--ssh_key',help='\'linux\' or \'osx\' for default paths used in each OS respectively, \
    otherwise a path to the openssh key to used for aspera (i.e. the -i flag of ascp) [default: \'linux\']',
                        default='linux')
    parser.add_argument('--ascp-args','--ascp_args',help='extra arguments to pass to ascp e.g. \'-k 2\' to resume with a \
        sparse file checksum [default: \'\']',default='')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG,format='%(asctime)s %(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

    # Use the example set out at this very helpful post:
    # https://www.biostars.org/p/325010

    if args.ssh_key == 'linux':
        ssh_key_file = '$HOME/.aspera/connect/etc/asperaweb_id_dsa.openssh'
    elif args.ssh_key == 'osx':
        ssh_key_file = '$HOME/Applications/Aspera\ Connect.app/Contents/Resources/asperaweb_id_dsa.openssh'
    else:
        ssh_key_file = args.ssh_key
    logging.info("Using aspera ssh key file: {}".format(ssh_key_file))

    run_id = args.run_identifier
    output_directory = args.output_directory

    # Get the textual representation of the run. We specifically need the fastq_ftp bit
    logging.info("Querying ENA for FTP paths for {}..".format(run_id))
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
    if len(ftp_urls) == 0:
        # One (current) example of this is DRR086621
        logging.warn("No FTP download URLs found for run {}, cannot continue".format(run_id))
        sys.exit(1)
    else:
        logging.info("Found {} FTP URLs for download e.g. {}".format(len(ftp_urls), ftp_urls[0]))

    aspera_commands = []
    for url in ftp_urls:
        cmd = "ascp -QT -l 300m -P33001 {} -i {} era-fasp@fasp.sra.ebi.ac.uk:{} {}".format(
            args.ascp_args,
            ssh_key_file,
            url.replace('ftp.sra.ebi.ac.uk',''), output_directory)
        logging.info("Running command: {}".format(cmd))
        subprocess.check_call(cmd,shell=True)

logging.info("All done.")
