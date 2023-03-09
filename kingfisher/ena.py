from io import StringIO
import subprocess
import logging
import os
import pandas as pd
import hashlib

import extern

from .md5sum import MD5

DEFAULT_LINUX_ASPERA_SSH_KEY_LOCATION = os.path.join(os.path.dirname(os.path.realpath(__file__)),'data','asperaweb_id_dsa.openssh')

class EnaFileReport:
    def __init__(self, file_paths, md5sums):
        self.file_paths = file_paths
        self.md5sums = md5sums

class EnaDownloader:
    def get_ftp_download_urls(self, run_id):
        # Get the textual representation of the run. We specifically need the
        # fastq_ftp bit, and the MD5
        logging.info("Querying ENA for FTP paths for {}..".format(run_id))
        query_url = "https://www.ebi.ac.uk/ena/portal/api/filereport?accession={}&" \
            "result=read_run&fields=fastq_ftp,fastq_md5".format(
            run_id)
        logging.debug("Querying '{}'".format(query_url))
        text = extern.run("curl --silent '{}'".format(query_url))

        header = True
        logging.debug("Found text from ENA API: {}".format(text))

        df = pd.read_csv(StringIO(text), sep='\t', header=0, index_col=False)

        # Expect just 1 row
        if len(df) == 0:
            # One (current) example of this is DRR086621
            logging.error(
                "No FTP download URLs found for run {}, cannot continue".format(
                    run_id))
            return False
        elif len(df) != 1:
            logging.error("Expected 1 row from ENA API for accession {}, got {}".format(run_id, len(df)))
            return False

        for _, row in df.iterrows():
            # e.g. ERR1346134 at time of writing. See https://github.com/wwood/kingfisher-download/issues/25
            if isinstance(float("nan"), type(row['fastq_ftp'])):
                logging.error("No ENA FTP download URLs found for run {}, cannot continue".format(run_id))
                return False
            ftp_urls = row['fastq_ftp'].split(';')
            md5sums = row['fastq_md5'].split(';')
            logging.debug("Found {} FTP URLs for download: {}".format(
                len(ftp_urls), ", ".join(ftp_urls)))

        return EnaFileReport(ftp_urls, md5sums)

    def _clean_incomplete_files(self, paths):
        for path in paths:
            if os.path.exists(path):
                logging.info("Removing file that is either incomplete or part of an incomplete pair: {}".format(path))
                os.remove(path)

    def download_with_aspera(self, run_id, output_directory, quiet=False, ascp_args='', ssh_key=None, check_md5sums=False):
        if ssh_key is None:
            logging.debug("Attempting to find aspera ssh key file at {}".format(DEFAULT_LINUX_ASPERA_SSH_KEY_LOCATION))
            if os.path.exists(DEFAULT_LINUX_ASPERA_SSH_KEY_LOCATION):
                ssh_key_file = DEFAULT_LINUX_ASPERA_SSH_KEY_LOCATION
            else:
                raise Exception("Cannot find aspera ssh key file, please specify with --aspera-ssh-key")
        else:
            ssh_key_file = ssh_key
        logging.info("Using aspera ssh key file: {}".format(ssh_key_file))

        report = self.get_ftp_download_urls(run_id)
        if report is False:
            return False
        ftp_urls = report.file_paths
        md5sums = report.md5sums

        logging.info("Downloading {} FTP read set(s): {}".format(
            len(ftp_urls), ", ".join(ftp_urls)))

        aspera_commands = []
        output_files = []
        for url, md5 in zip(ftp_urls, md5sums):
            quiet_args = ''
            if quiet:
                quiet_args = ' -Q'
            output_file = os.path.join(output_directory, os.path.basename(url))
            logging.debug("Getting output file {}".format(output_file))
            cmd = "ascp{} -T -l 300m -P33001 {} -i {} era-fasp@fasp.sra.ebi.ac.uk:{} {}".format(
                quiet_args,
                ascp_args,
                ssh_key_file,
                url.replace('ftp.sra.ebi.ac.uk', ''),
                output_directory)
            logging.info("Running command: {}".format(cmd))
            try:
                extern.run(cmd)
            except Exception as e:
                logging.warn("Error downloading from ENA with ASCP: {}".format(e))
                self._clean_incomplete_files(output_files+[output_file])
                return False
            if check_md5sums:
                if MD5.check_md5sum(output_file, md5):
                    logging.info("MD5sum OK for {}".format(output_file))
                else:
                    logging.error("MD5sum failed for {}".format(output_file))
                    self._clean_incomplete_files(output_files+[output_file])
                    return False
            output_files.append(output_file)
        return output_files

    def download_with_curl(self, run_id, num_threads, check_md5sums=False):
        report = self.get_ftp_download_urls(run_id)
        if report is False:
            return False
        ftp_urls = report.file_paths
        md5sums = report.md5sums

        downloaded = []
        for url, md5 in zip(ftp_urls, md5sums):
            logging.info("Downloading {} ..".format(url))
            output_file = os.path.basename(url)
            if num_threads > 1:
                cmd = "aria2c -x{} -o {} 'ftp://{}'".format(
                    num_threads, output_file, url)
            else:
                cmd = "curl -L '{}' -o {}".format(url, output_file)
            try:
                subprocess.check_call(cmd, shell=True)
            except subprocess.CalledProcessError as e:
                logging.warning("Method ena-ftp failed, error was {}".format(e))
                self._clean_incomplete_files(downloaded+[output_file])
                return False
            
            if check_md5sums:
                if MD5.check_md5sum(output_file, md5):
                    logging.info("MD5sum OK for {}".format(output_file))
                else:
                    logging.error("MD5sum failed for {}".format(output_file))
                    self._clean_incomplete_files(downloaded+[output_file])
                    return False
            downloaded.append(output_file)
        return downloaded

