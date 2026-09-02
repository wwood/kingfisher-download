from io import StringIO
import json
import subprocess
import shutil
import logging
import os
import pandas as pd

import extern
import bird_tool_utils

from .md5sum import MD5

DEFAULT_LINUX_ASPERA_SSH_KEY_LOCATION = os.path.join(os.path.dirname(os.path.realpath(__file__)),'data','asperaweb_id_dsa.openssh')

# ENA deprecated the old DSA key (asperaweb_id_dsa.openssh) in favour of this
# RSA key, which is distributed as part of the Aspera SDK/transferd e.g. by
# `ascli conf ascp install`. See
# https://github.com/wwood/kingfisher-download/issues/54
ASPERA_BYPASS_RSA_KEY_NAME = 'aspera_bypass_rsa.pem'

# Sentinel values that historically meant "use the key bundled with Kingfisher"
AUTOMATIC_SSH_KEY_SPECIFICATIONS = (None, 'linux', 'osx')


class EnaFileReport:
    def __init__(self, file_paths, md5sums):
        self.file_paths = file_paths
        self.md5sums = md5sums

def _aspera_home():
    return os.path.expanduser('~/.aspera')

def _find_ascp_in_aspera():
    """Search ~/.aspera for an ascp binary."""
    aspera_dir = _aspera_home()
    if os.path.isdir(aspera_dir):
        for root, dirs, files in os.walk(aspera_dir):
            if 'ascp' in files:
                path = os.path.join(root, 'ascp')
                if os.access(path, os.X_OK):
                    return path
    return None

def _resolve_ascp():
    if shutil.which('ascp') is not None:
        return 'ascp'
    found = _find_ascp_in_aspera()
    if found is not None:
        logging.warning("ascp not found in PATH; using {}".format(found))
        return found
    raise Exception("ascp not found in PATH or under ~/.aspera")

def _find_key_in_aspera_home(key_name):
    """Search ~/.aspera for a key file e.g. the one installed by `ascli conf ascp install`."""
    aspera_dir = _aspera_home()
    if os.path.isdir(aspera_dir):
        for root, dirs, files in sorted(os.walk(aspera_dir)):
            if key_name in files:
                return os.path.join(root, key_name)
    return None

def _find_key_near_ascp(key_name):
    """Search the directories an ascp installation usually keeps its keys in."""
    try:
        ascp_bin = _resolve_ascp()
    except Exception:
        return None
    ascp_path = shutil.which(ascp_bin) if os.path.dirname(ascp_bin) == '' else ascp_bin
    if ascp_path is None:
        return None
    bin_dir = os.path.dirname(os.path.realpath(ascp_path))
    parent_dir = os.path.dirname(bin_dir)
    for candidate in (
            os.path.join(bin_dir, key_name),
            os.path.join(bin_dir, 'etc', key_name),
            os.path.join(parent_dir, 'etc', key_name),
            os.path.join(parent_dir, 'var', key_name)):
        if os.path.exists(candidate):
            return candidate
    return None

def _extract_key_path_from_ascli_output(output):
    """Pull a key path out of the (JSON or plain text) output of ascli."""
    output = output.strip()
    if output == '':
        return None
    try:
        parsed = json.loads(output)
    except ValueError:
        parsed = None
    if isinstance(parsed, str):
        return parsed
    elif isinstance(parsed, dict):
        # Either {"ssh_private_rsa": "/path"} or {"field": .., "value": ..}
        if 'ssh_private_rsa' in parsed:
            return parsed['ssh_private_rsa']
        if parsed.get('field') == 'ssh_private_rsa' or parsed.get('key') == 'ssh_private_rsa':
            return parsed.get('value')
        return None
    elif isinstance(parsed, list):
        for entry in parsed:
            key = _extract_key_path_from_ascli_output(json.dumps(entry))
            if key is not None:
                return key
        return None
    # Not JSON, so pick out a path from the plain text / table output of e.g.
    # `ascli conf ascp info --fields=ssh_private_rsa`
    for line in reversed(output.split('\n')):
        for token in line.split():
            if os.path.isabs(token) and os.path.exists(token):
                return token
    return None

def _find_key_via_ascli(key_name):
    """Ask the IBM Aspera CLI (ascli) where it installed the RSA bypass key."""
    if shutil.which('ascli') is None:
        return None
    base_cmd = ['ascli', 'conf', 'ascp', 'info', '--fields=ssh_private_rsa']
    for cmd in (base_cmd + ['--format=json'], base_cmd):
        logging.debug("Running command: {}".format(' '.join(cmd)))
        try:
            process = subprocess.run(
                cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
        except Exception as e:
            logging.debug("Failed to run ascli to find the aspera ssh key: {}".format(e))
            return None
        if process.returncode != 0:
            logging.debug("ascli returned exit status {} when asked for the aspera ssh key: {}".format(
                process.returncode, process.stderr.strip()))
            continue
        key = _extract_key_path_from_ascli_output(process.stdout)
        if key is not None and os.path.exists(key):
            return key
    logging.debug("ascli did not report a usable {} path".format(key_name))
    return None

def resolve_ena_ssh_key(ssh_key=None):
    """Return the path of the ssh key to authenticate to the ENA aspera server with.

    ENA no longer accepts the DSA key that used to be handed out with the
    Aspera Connect client, and instead requires the RSA bypass key that comes
    with the Aspera SDK. Since that key cannot be redistributed with Kingfisher,
    find it in the usual places, or fall back to the bundled (deprecated) DSA
    key.
    """
    if ssh_key not in AUTOMATIC_SSH_KEY_SPECIFICATIONS:
        if not os.path.exists(ssh_key):
            raise Exception("Specified aspera ssh key file does not exist: {}".format(ssh_key))
        return ssh_key

    logging.debug("Searching for the aspera RSA key {} ..".format(ASPERA_BYPASS_RSA_KEY_NAME))
    for finder in (_find_key_in_aspera_home, _find_key_near_ascp, _find_key_via_ascli):
        found = finder(ASPERA_BYPASS_RSA_KEY_NAME)
        if found is not None:
            logging.debug("Found aspera RSA key via {}".format(finder.__name__))
            return found

    if os.path.exists(DEFAULT_LINUX_ASPERA_SSH_KEY_LOCATION):
        logging.warning(
            "Could not find the aspera RSA key {}, so falling back to the deprecated DSA key "
            "bundled with Kingfisher. ENA now requires the RSA key, so downloads are likely to "
            "fail asking for a password. Install the key with `ascli conf ascp install` (from "
            "the aspera-cli package), or specify it with --ascp-ssh-key.".format(
                ASPERA_BYPASS_RSA_KEY_NAME))
        return DEFAULT_LINUX_ASPERA_SSH_KEY_LOCATION
    raise Exception(
        "Cannot find an aspera ssh key. ENA requires the RSA key {}, which can be installed with "
        "`ascli conf ascp install` (from the aspera-cli package), or specified with "
        "--ascp-ssh-key.".format(ASPERA_BYPASS_RSA_KEY_NAME))


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

        try:
            df = pd.read_csv(StringIO(text), sep='\t', header=0, index_col=False)
        except (pd.errors.ParserError, pd.errors.EmptyDataError) as e:
            logging.error("Unexpected ENA API response for accession {}: {}".format(run_id, e))
            return False

        required_columns = ['fastq_ftp', 'fastq_md5']
        if any(column not in df.columns for column in required_columns):
            logging.error(
                "Unexpected ENA API response for accession {}: missing one or more required columns ({})".format(
                    run_id, ', '.join(required_columns)))
            return False

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
            if pd.isna(row['fastq_ftp']) or row['fastq_ftp'] == '':
                logging.error("No ENA FTP download URLs found for run {}, cannot continue".format(run_id))
                return False
            if pd.isna(row['fastq_md5']) or row['fastq_md5'] == '':
                logging.error("No ENA FTP MD5 checksums found for run {}, cannot continue".format(run_id))
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
        try:
            ssh_key_file = resolve_ena_ssh_key(ssh_key)
        except Exception as e:
            # Returning False rather than raising so that any further download
            # methods e.g. ena-ftp are still attempted
            logging.warning("Cannot download from ENA with ASCP: {}".format(e))
            return False
        logging.info("Using aspera ssh key file: {}".format(ssh_key_file))

        report = self.get_ftp_download_urls(run_id)
        if report is False:
            return False
        ftp_urls = report.file_paths
        md5sums = report.md5sums

        logging.info("Downloading {} FTP read set(s): {}".format(
            len(ftp_urls), ", ".join(ftp_urls)))

        output_files = []
        for url, md5 in zip(ftp_urls, md5sums):
            quiet_args = ''
            if quiet:
                quiet_args = ' -Q'
            output_file = os.path.join(output_directory, os.path.basename(url))
            logging.debug("Getting output file {}".format(output_file))
            ascp_bin = _resolve_ascp()
            cmd = "{}{} -T -l 300m -P33001 {} -i {} era-fasp@fasp.sra.ebi.ac.uk:{} {}".format(
                ascp_bin,
                quiet_args,
                ascp_args,
                ssh_key_file,
                url.replace('ftp.sra.ebi.ac.uk', ''),
                output_directory)
            logging.info("Running command: {}".format(cmd))
            try:
                # An empty stdin is given so that ascp fails immediately
                # rather than hanging on a "Password:" prompt when the key is
                # not accepted.
                extern.run(cmd, stdin='')
            except Exception as e:
                logging.warning("Error downloading from ENA with ASCP: {}".format(e))
                if ssh_key_file == DEFAULT_LINUX_ASPERA_SSH_KEY_LOCATION:
                    logging.warning(
                        "The DSA key bundled with Kingfisher was used, which ENA no longer accepts. "
                        "Install the RSA key {} with `ascli conf ascp install` (from the aspera-cli "
                        "package), or pass it to --ascp-ssh-key.".format(ASPERA_BYPASS_RSA_KEY_NAME))
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

    def download_with_curl(self, run_id, num_threads, output_directory, check_md5sums=False):
        with bird_tool_utils.in_working_directory(output_directory):
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
                    if num_threads > 16:
                        logging.warn("Limited the number of download threads to 16, the max for aria2c")
                        num_threads = 16
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
                downloaded.append(os.path.join(output_directory, output_file))
        return downloaded
