import logging
import os
import re
import subprocess
import shutil
from html.parser import HTMLParser

import requests

from .ena import _resolve_ascp, _find_ascp_in_aspera, DEFAULT_LINUX_ASPERA_SSH_KEY_LOCATION
from .md5sum import MD5


NGDC_SEARCH_URL = 'https://ngdc.cncb.ac.cn/gsa/search'
NGDC_HTTPS_DOWNLOAD_BASE = 'https://download.cncb.ac.cn/gsa'
NGDC_FTP_DOWNLOAD_BASE = 'ftp://download.big.ac.cn/gsa'
NGDC_ASPERA_HOST = 'aspera01@download.cncb.ac.cn'


class NgdcRunInfo:
    """Parsed metadata for a single CRR run from NGDC/GSA."""
    def __init__(self, crr_accession, cra_accession, filenames, experiment_accession=None,
                 platform=None, library_strategy=None, library_source=None,
                 library_layout=None, sample_accession=None, bioproject=None,
                 species=None, alias=None, title=None):
        self.crr_accession = crr_accession
        self.cra_accession = cra_accession
        self.filenames = filenames  # list of filenames e.g. ['CRR302577_f1.fastq.gz', 'CRR302577_r2.fastq.gz']
        self.experiment_accession = experiment_accession
        self.platform = platform
        self.library_strategy = library_strategy
        self.library_source = library_source
        self.library_layout = library_layout
        self.sample_accession = sample_accession
        self.bioproject = bioproject
        self.species = species
        self.alias = alias
        self.title = title


class _NgdcSearchParser(HTMLParser):
    """Parse the NGDC GSA search results HTML to extract run info."""

    def __init__(self):
        super().__init__()
        self.cra_accession = None
        self.filenames = []
        self.experiment_accession = None
        self.platform = None
        self.library_strategy = None
        self.library_source = None
        self.library_layout = None
        self.sample_accession = None
        self.bioproject = None
        self.species = None
        self.alias = None
        self.title = None

        # State for tracking where we are in the HTML
        self._current_tag = None
        self._current_attrs = {}
        self._capture_text = False
        self._captured_text = ''
        self._in_label = False
        self._current_label = None

    def handle_starttag(self, tag, attrs):
        self._current_tag = tag
        self._current_attrs = dict(attrs)

        if tag == 'a':
            href = self._current_attrs.get('href', '')
            # Extract CRA from links like /gsa/browse/CRA006375/CRR426631
            cra_match = re.search(r'/gsa/browse/(CRA\d+)', href)
            if cra_match and self.cra_accession is None:
                self.cra_accession = cra_match.group(1)
            # Extract experiment accession from links
            crx_match = re.search(r'/gsa/browse/CRA\d+/(CRX\d+)', href)
            if crx_match and self.experiment_accession is None:
                self.experiment_accession = crx_match.group(1)
            # Extract bioproject
            prj_match = re.search(r'/bioproject/browse/(PRJCA\d+)', href)
            if prj_match and self.bioproject is None:
                self.bioproject = prj_match.group(1)
            # Extract sample accession
            samc_match = re.search(r'/biosample/browse/(SAMC\d+)', href)
            if samc_match and self.sample_accession is None:
                self.sample_accession = samc_match.group(1)

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return

        # Detect filenames
        if re.match(r'CRR\d+[_.].*\.(fastq\.gz|fq\.gz|sra|bam)$', text):
            self.filenames.append(text)

        # Detect species
        if self._current_tag == 'i' or self._current_tag == 'em':
            # Species names are often in italic
            pass

    def handle_endtag(self, tag):
        pass


def _fetch_ngdc_search_page(crr_accession):
    """Fetch the NGDC search page for a CRR accession and return the HTML."""
    url = '{}?searchTerm={}'.format(NGDC_SEARCH_URL, crr_accession)
    logging.debug("Fetching NGDC search page: {}".format(url))
    res = requests.get(url, timeout=60)
    if not res.ok:
        raise Exception("Failed to fetch NGDC search page for {}: {} {}".format(
            crr_accession, res.status_code, res.text[:200]))
    return res.text


def _parse_ngdc_run_page(crr_accession, cra_accession):
    """Fetch the NGDC run detail page and extract file listing."""
    url = 'https://ngdc.cncb.ac.cn/gsa/browse/{}/{}'.format(cra_accession, crr_accession)
    logging.debug("Fetching NGDC run page: {}".format(url))
    res = requests.get(url, timeout=60)
    if not res.ok:
        raise Exception("Failed to fetch NGDC run page for {}: {} {}".format(
            crr_accession, res.status_code, res.text[:200]))

    filenames = re.findall(
        r'({}[_.][^\s<"\']+\.(?:fastq\.gz|fq\.gz|sra|bam))'.format(re.escape(crr_accession)),
        res.text
    )
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for f in filenames:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


def fetch_ngdc_run_info(crr_accession):
    """Look up a CRR accession on NGDC and return an NgdcRunInfo."""
    if not re.match(r'^CRR\d+$', crr_accession):
        raise Exception("Invalid NGDC run accession: {}".format(crr_accession))

    html = _fetch_ngdc_search_page(crr_accession)

    parser = _NgdcSearchParser()
    parser.feed(html)

    if parser.cra_accession is None:
        raise Exception("Could not find CRA accession for {} on NGDC".format(crr_accession))

    # Get the file listing from the run detail page
    filenames = _parse_ngdc_run_page(crr_accession, parser.cra_accession)
    if not filenames:
        # Fall back to common patterns
        logging.warning("Could not find file listing for {} on NGDC run page, "
                        "trying common filename patterns".format(crr_accession))
        filenames = ['{}_f1.fastq.gz'.format(crr_accession),
                     '{}_r2.fastq.gz'.format(crr_accession)]

    return NgdcRunInfo(
        crr_accession=crr_accession,
        cra_accession=parser.cra_accession,
        filenames=filenames,
        experiment_accession=parser.experiment_accession,
        platform=parser.platform,
        library_strategy=parser.library_strategy,
        library_source=parser.library_source,
        library_layout=parser.library_layout,
        sample_accession=parser.sample_accession,
        bioproject=parser.bioproject,
        species=parser.species,
        alias=parser.alias,
        title=parser.title,
    )


class NgdcDownloader:
    def download_with_ftp(self, run_id, num_threads, output_directory):
        """Download files from NGDC via FTP/HTTPS using curl or aria2c."""
        info = fetch_ngdc_run_info(run_id)

        output_files = []
        for filename in info.filenames:
            url = '{}/{}/{}/{}'.format(
                NGDC_HTTPS_DOWNLOAD_BASE, info.cra_accession, run_id, filename)
            output_path = os.path.join(output_directory, filename)

            logging.info("Downloading {} from NGDC ..".format(url))
            try:
                if num_threads > 1:
                    if num_threads > 16:
                        logging.warning("Limited the number of download threads to 16, the max for aria2c")
                        num_threads = 16
                    cmd = "aria2c -x{} -o {} '{}'".format(num_threads, output_path, url)
                else:
                    cmd = "curl -L -o {} '{}'".format(output_path, url)
                subprocess.check_call(cmd, shell=True)
            except subprocess.CalledProcessError as e:
                logging.warning("NGDC FTP download failed for {}: {}".format(filename, e))
                for f in output_files + [output_path]:
                    if os.path.exists(f):
                        os.remove(f)
                return False

            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                logging.warning("Downloaded file {} is missing or empty".format(output_path))
                for f in output_files + [output_path]:
                    if os.path.exists(f):
                        os.remove(f)
                return False

            output_files.append(output_path)

        return output_files

    def download_with_aspera(self, run_id, output_directory, ascp_args='', ssh_key=None):
        """Download files from NGDC via Aspera."""
        info = fetch_ngdc_run_info(run_id)

        if ssh_key is None:
            # Try the bundled key first, then look for aspera's own key
            if os.path.exists(DEFAULT_LINUX_ASPERA_SSH_KEY_LOCATION):
                ssh_key_file = DEFAULT_LINUX_ASPERA_SSH_KEY_LOCATION
            else:
                # Look for aspera's own key
                aspera_dir = os.path.expanduser('~/.aspera')
                ssh_key_file = None
                if os.path.isdir(aspera_dir):
                    for root, dirs, files in os.walk(aspera_dir):
                        for f in files:
                            if f.endswith('.openssh') or f == 'asperaweb_id_dsa.openssh':
                                ssh_key_file = os.path.join(root, f)
                                break
                        if ssh_key_file:
                            break
                if ssh_key_file is None:
                    raise Exception("Cannot find aspera ssh key file, please specify with --aspera-ssh-key")
        else:
            ssh_key_file = ssh_key
        logging.info("Using aspera ssh key file: {}".format(ssh_key_file))

        ascp_bin = _resolve_ascp()

        output_files = []
        for filename in info.filenames:
            remote_path = '/gsa/{}/{}/{}'.format(info.cra_accession, run_id, filename)
            output_path = os.path.join(output_directory, filename)

            cmd = "{} -P33001 -T -l 300m {} -i {} {}:{} {}".format(
                ascp_bin, ascp_args, ssh_key_file,
                NGDC_ASPERA_HOST, remote_path, output_directory)
            logging.info("Running command: {}".format(cmd))
            try:
                subprocess.check_call(cmd, shell=True)
            except subprocess.CalledProcessError as e:
                logging.warning("NGDC Aspera download failed for {}: {}".format(filename, e))
                for f in output_files + [output_path]:
                    if os.path.exists(f):
                        os.remove(f)
                return False

            output_files.append(output_path)

        return output_files


def fetch_ngdc_metadata(crr_accessions):
    """Fetch metadata for a list of CRR accessions from NGDC.

    Returns a list of dicts with metadata fields, suitable for conversion to a
    pandas DataFrame.
    """
    import pandas as pd

    records = []
    for acc in crr_accessions:
        logging.info("Fetching NGDC metadata for {} ..".format(acc))
        try:
            # Fetch the run detail page for richer metadata
            info = fetch_ngdc_run_info(acc)
            run_page_url = 'https://ngdc.cncb.ac.cn/gsa/browse/{}/{}'.format(
                info.cra_accession, acc)
            res = requests.get(run_page_url, timeout=60)
            html = res.text if res.ok else ''

            platform = info.platform or _extract_meta(html, 'Platform') or _extract_meta(html, '测序平台')
            species = info.species or _extract_meta(html, 'Species') or _extract_meta(html, '物种')
            alias = info.alias or _extract_meta(html, 'Alias')

            record = {
                'run': acc,
                'bioproject': info.bioproject or _extract_field(html, r'PRJCA\d+'),
                'experiment_accession': info.experiment_accession,
                'sample_accession': info.sample_accession or _extract_field(html, r'SAMC\d+'),
                'cra_accession': info.cra_accession,
                'filenames': ';'.join(info.filenames),
                'bases': None,
                'library_strategy': info.library_strategy or _extract_meta(html, 'Library strategy') or _extract_meta(html, 'Strategy'),
                'library_selection': None,
                'library_source': info.library_source or _extract_meta(html, 'Source'),
                'library_layout': info.library_layout or _extract_meta(html, 'Layout'),
                'model': platform,
                'sample_name': alias or acc,
                'taxon_name': species,
                'platform': platform,
                'title': info.title or _extract_meta(html, 'Title'),
            }

            records.append(record)
        except Exception as e:
            logging.warning("Failed to fetch metadata for {}: {}".format(acc, e))
            records.append({'run': acc})

    return pd.DataFrame(records)


def _extract_field(html, pattern):
    """Extract the first match of a regex pattern from HTML."""
    m = re.search(pattern, html)
    return m.group(0) if m else None


def _extract_meta(html, label):
    """Try to extract a metadata value following a label in HTML.

    Looks for patterns like:
        <th>Label</th><td>Value</td>
        <label>Label</label>...value...
    """
    # Try th/td pattern
    pattern = r'(?:<th[^>]*>|<label[^>]*>)\s*{}\s*(?:</th>|</label>)\s*(?:<td[^>]*>)\s*([^<]+)'.format(
        re.escape(label))
    m = re.search(pattern, html, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Try a more general pattern: label followed by a colon or value in next tag
    pattern = r'{}[：:]\s*</?\w[^>]*>\s*([^<]+)'.format(re.escape(label))
    m = re.search(pattern, html, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    return None
