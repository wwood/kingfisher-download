import subprocess
import logging
import os

import extern

DEFAULT_LINUX_ASPERA_SSH_KEY_LOCATION = '$HOME/.aspera/connect/etc/asperaweb_id_dsa.openssh'
DEFAULT_OSX_ASPERA_SSH_KEY_LOCATION = '$HOME/Applications/Aspera Connect.app/Contents/\
                Resources/asperaweb_id_dsa.openssh'

class EnaDownloader:
    def get_ftp_download_urls(self, run_id):
        # Get the textual representation of the run. We specifically need the
        # fastq_ftp bit
        logging.info("Querying ENA for FTP paths for {}..".format(run_id))
        query_url = "https://www.ebi.ac.uk/ena/portal/api/filereport?accession={}&" \
            "result=read_run&fields=fastq_ftp".format(
            run_id)
        logging.debug("Querying '{}'".format(query_url))
        text = extern.run("curl --silent '{}'".format(query_url))

        ftp_urls = []
        header = True
        logging.debug("Found text from ENA API: {}".format(text))
        for line in text.split('\n'):
            logging.debug("Parsing line: {}".format(line))
            if header:
                header = False
            else:
                if line == '':
                    continue
                fastq_ftp = line.split('\t')[1]
                for url in fastq_ftp.split(';'):
                    if url.strip() != '':
                        ftp_urls.append(url.strip())
        if len(ftp_urls) == 0:
            # One (current) example of this is DRR086621
            logging.error(
                "No FTP download URLs found for run {}, cannot continue".format(
                    run_id))
            return False
        else:
            logging.debug("Found {} FTP URLs for download: {}".format(
                len(ftp_urls), ", ".join(ftp_urls)))
        return ftp_urls

    def download_with_aspera(self, run_id, output_directory, quiet=False, ascp_args='', ssh_key='linux'):
        if ssh_key == 'linux':
            ssh_key_file = DEFAULT_LINUX_ASPERA_SSH_KEY_LOCATION
        elif ssh_key == 'osx':
            ssh_key_file = DEFAULT_OSX_ASPERA_SSH_KEY_LOCATION
        else:
            ssh_key_file = ssh_key
        logging.info("Using aspera ssh key file: {}".format(ssh_key_file))

        ftp_urls = self.get_ftp_download_urls(run_id)
        if ftp_urls is False:
            return False

        logging.info("Downloading {} FTP read set(s): {}".format(
            len(ftp_urls), ", ".join(ftp_urls)))

        aspera_commands = []
        output_files = []
        for url in ftp_urls:
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
                return False
            output_files.append(output_file)
        return output_files

    def download_with_curl(self, run_id, num_threads):
        ftp_urls = self.get_ftp_download_urls(run_id)
        if ftp_urls is False:
            return False

        downloaded = []
        for e in ftp_urls:
            logging.info("Downloading {} ..".format(e))
            outname = os.path.basename(e)
            if num_threads > 1:
                cmd = "aria2c -x{} -o {} 'ftp://{}'".format(
                    num_threads, outname, e)
            else:
                cmd = "curl -L '{}' -o {}".format(e, outname)
            try:
                subprocess.check_call(cmd, shell=True)
            except subprocess.CalledProcessError as e:
                logging.warning("Method ena-ftp failed, error was {}".format(e))
                return False
            downloaded.append(outname)
        return downloaded

