import logging
import os
import re
import subprocess
import shutil
import xml.etree.ElementTree as ET

import requests

from .ena import _resolve_ascp, _find_ascp_in_aspera, DEFAULT_LINUX_ASPERA_SSH_KEY_LOCATION
from .md5sum import MD5


NGDC_HTTPS_DOWNLOAD_BASE = 'https://download.cncb.ac.cn/gsa'
NGDC_FTP_DOWNLOAD_BASE = 'ftp://download.big.ac.cn/gsa'
NGDC_ASPERA_HOST = 'aspera01@download.cncb.ac.cn'
# Some projects are under /gsa2/ instead of /gsa/
NGDC_HTTPS_DOWNLOAD_BASES = [
    'https://download.cncb.ac.cn/gsa',
    'https://download.cncb.ac.cn/gsa2',
]


class NgdcRunInfo:
    """Parsed metadata for a single CRR run from NGDC/GSA."""
    def __init__(self, crr_accession, cra_accession, filenames, gsa_base=None):
        self.crr_accession = crr_accession
        self.cra_accession = cra_accession
        self.filenames = filenames  # e.g. ['CRR302577_f1.fastq.gz', 'CRR302577_r2.fastq.gz']
        # Which base URL prefix to use (gsa vs gsa2)
        self.gsa_base = gsa_base or NGDC_HTTPS_DOWNLOAD_BASES[0]


def _find_cra_for_crr(crr_accession):
    """Find the CRA accession for a CRR run by searching the download server
    directory listings.

    The download server at download.cncb.ac.cn has directory listings enabled.
    CRR numbers are sequential within a CRA, and CRA numbers are sequential,
    so we can binary search the CRA listing to find which one contains our CRR.
    In practice, we fetch the top-level listing once and scan it.
    """
    for base_url in NGDC_HTTPS_DOWNLOAD_BASES:
        logging.debug("Searching {} for {}".format(base_url, crr_accession))
        res = requests.get(base_url + '/', timeout=60)
        if not res.ok:
            logging.debug("Failed to fetch directory listing from {}: {}".format(base_url, res.status_code))
            continue

        # Extract all CRA accessions from the directory listing
        cra_accessions = re.findall(r'href="(CRA\d+)/"', res.text)
        if not cra_accessions:
            continue

        # Check each CRA in reverse order (newer projects have higher CRR numbers)
        for cra in reversed(cra_accessions):
            cra_url = '{}/{}/'.format(base_url, cra)
            cra_res = requests.get(cra_url, timeout=60)
            if not cra_res.ok:
                continue
            if crr_accession in cra_res.text:
                return cra, base_url

    return None, None


def _find_cra_for_crr_smart(crr_accession):
    """Find the CRA accession for a CRR run using a narrowed search.

    CRR numbers are roughly sequential within CRA projects, and CRA projects
    are listed in order. We use binary search to narrow down which CRA
    contains the target CRR.
    """
    for base_url in NGDC_HTTPS_DOWNLOAD_BASES:
        logging.debug("Searching {} for {}".format(base_url, crr_accession))
        res = requests.get(base_url + '/', timeout=60)
        if not res.ok:
            continue

        cra_accessions = re.findall(r'href="(CRA\d+)/"', res.text)
        if not cra_accessions:
            continue

        # Binary search: for each candidate CRA, check if it contains CRR
        # numbers in the right range. We check the first CRR in each CRA
        # directory to narrow down.
        target_num = int(re.search(r'\d+', crr_accession).group())

        lo, hi = 0, len(cra_accessions) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            cra = cra_accessions[mid]
            cra_url = '{}/{}/'.format(base_url, cra)
            cra_res = requests.get(cra_url, timeout=60)
            if not cra_res.ok:
                # Can't read this CRA, try linear from here
                break

            crr_nums = [int(x) for x in re.findall(r'href="CRR(\d+)/"', cra_res.text)]
            if not crr_nums:
                break

            min_crr = min(crr_nums)
            max_crr = max(crr_nums)

            if min_crr <= target_num <= max_crr:
                # Found it - verify the exact CRR is present
                if crr_accession in cra_res.text:
                    return cra, base_url
                else:
                    break
            elif target_num < min_crr:
                hi = mid - 1
            else:
                lo = mid + 1

        # Binary search didn't find it exactly, check neighbors
        for offset in range(-2, 3):
            idx = (lo + hi) // 2 + offset
            if 0 <= idx < len(cra_accessions):
                cra = cra_accessions[idx]
                cra_url = '{}/{}/'.format(base_url, cra)
                cra_res = requests.get(cra_url, timeout=60)
                if cra_res.ok and crr_accession in cra_res.text:
                    return cra, base_url

    return None, None


def _get_filenames_from_download_server(crr_accession, cra_accession, base_url):
    """Get the list of data files for a CRR run from the download server."""
    url = '{}/{}/{}/'.format(base_url, cra_accession, crr_accession)
    logging.debug("Fetching file listing from {}".format(url))
    res = requests.get(url, timeout=60)
    if not res.ok:
        return []

    # Match data files (fastq.gz, fq.gz, sra, bam) but not .xml or other metadata
    filenames = re.findall(
        r'href="({}[^\s"]*\.(?:fastq\.gz|fq\.gz|sra|bam))"'.format(re.escape(crr_accession)),
        res.text
    )
    return filenames


def fetch_ngdc_run_info(crr_accession):
    """Look up a CRR accession on NGDC and return an NgdcRunInfo.

    Uses the download server (download.cncb.ac.cn) directory listings to
    resolve the CRA accession and file listing, which is more reliable than
    the NGDC web application.
    """
    if not re.match(r'^CRR\d+$', crr_accession):
        raise Exception("Invalid NGDC run accession: {}".format(crr_accession))

    logging.info("Looking up CRA accession for {} on NGDC download server ..".format(crr_accession))
    cra_accession, base_url = _find_cra_for_crr_smart(crr_accession)

    if cra_accession is None:
        raise Exception("Could not find CRA accession for {} on NGDC download server".format(crr_accession))

    logging.info("Found {} in {}".format(crr_accession, cra_accession))

    filenames = _get_filenames_from_download_server(crr_accession, cra_accession, base_url)
    if not filenames:
        raise Exception("No data files found for {} in {}/{} on NGDC download server".format(
            crr_accession, cra_accession, crr_accession))

    return NgdcRunInfo(
        crr_accession=crr_accession,
        cra_accession=cra_accession,
        filenames=filenames,
        gsa_base=base_url,
    )


class NgdcDownloader:
    def download_with_ftp(self, run_id, num_threads, output_directory):
        """Download files from NGDC via FTP/HTTPS using curl or aria2c."""
        try:
            info = fetch_ngdc_run_info(run_id)
        except Exception as e:
            logging.warning("Failed to look up run info for {} on NGDC: {}".format(run_id, e))
            return False

        output_files = []
        for filename in info.filenames:
            url = '{}/{}/{}/{}'.format(
                info.gsa_base, info.cra_accession, run_id, filename)
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
        try:
            info = fetch_ngdc_run_info(run_id)
        except Exception as e:
            logging.warning("Failed to look up run info for {} on NGDC: {}".format(run_id, e))
            return False

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

        try:
            ascp_bin = _resolve_ascp()
        except Exception as e:
            logging.warning("Method ngdc-ascp failed: {}".format(e))
            return False

        # Determine the aspera path prefix (gsa or gsa2)
        gsa_path = info.gsa_base.split('/')[-1]  # 'gsa' or 'gsa2'

        output_files = []
        for filename in info.filenames:
            remote_path = '/{}/{}/{}/{}'.format(gsa_path, info.cra_accession, run_id, filename)
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


def _fetch_run_stats_xml(info):
    """Fetch and parse the _sta.xml stats file from the download server.

    Returns a dict of metadata extracted from the XML, or an empty dict on failure.
    """
    xml_filename = '{}_sta.xml'.format(info.crr_accession)
    url = '{}/{}/{}/{}'.format(info.gsa_base, info.cra_accession, info.crr_accession, xml_filename)
    logging.debug("Fetching run stats XML from {}".format(url))
    try:
        res = requests.get(url, timeout=30)
        if not res.ok:
            return {}
        # The XML from NGDC is often malformed (e.g. <GC-Content="53.95%"/>)
        # Fix known issues before parsing
        xml_text = re.sub(r'<GC-Content="([^"]*)"/?>', r'<GC_Content value="\1"/>', res.text)
        root = ET.fromstring(xml_text)
        result = {}
        base_count = root.attrib.get('base_count')
        if base_count:
            result['bases'] = int(base_count)
        spot_count = root.attrib.get('spot_count')
        if spot_count:
            result['spots'] = int(spot_count)

        stats = root.find('Statistics')
        if stats is not None:
            nreads = stats.attrib.get('nreads')
            if nreads:
                result['nreads'] = int(nreads)
            for read in stats.findall('Read'):
                idx = int(read.attrib.get('index', 0)) + 1
                result['read{}_length_average'.format(idx)] = read.attrib.get('average')
                result['read{}_length_stdev'.format(idx)] = read.attrib.get('stdev')
            # Infer layout from number of reads
            if nreads and int(nreads) == 2:
                result['library_layout'] = 'PAIRED'
            elif nreads and int(nreads) == 1:
                result['library_layout'] = 'SINGLE'

        gc = root.find('GC-Content')
        if gc is not None:
            result['gc_content'] = gc.text
        else:
            # Try attribute form: <GC-Content="53.95%"/>
            # This is malformed XML but NGDC uses it; ET parses it as a tag
            for elem in root:
                if elem.tag.startswith('GC-Content'):
                    # The tag itself contains the value as GC-Content="53.95%"
                    # which ET parses with the value in the tag name
                    pass

        return result
    except Exception as e:
        logging.debug("Could not fetch/parse stats XML for {}: {}".format(info.crr_accession, e))
        return {}


def fetch_ngdc_metadata(crr_accessions):
    """Fetch metadata for a list of CRR accessions from NGDC.

    Returns a pandas DataFrame with metadata fields. Uses the download server
    for CRA resolution and the per-run _sta.xml for sequencing stats. Falls
    back to the NGDC web application for richer metadata when available.
    """
    import pandas as pd

    records = []
    for acc in crr_accessions:
        logging.info("Fetching NGDC metadata for {} ..".format(acc))
        try:
            info = fetch_ngdc_run_info(acc)

            record = {
                'run': acc,
                'cra_accession': info.cra_accession,
                'filenames': ';'.join(info.filenames),
                'bases': None,
                'sample_name': acc,
            }

            # Get stats from the _sta.xml file (always available on download server)
            stats = _fetch_run_stats_xml(info)
            record.update(stats)

            # Try to get richer metadata from the NGDC web application
            try:
                run_page_url = 'https://ngdc.cncb.ac.cn/gsa/browse/{}/{}'.format(
                    info.cra_accession, acc)
                res = requests.get(run_page_url, timeout=10)
                if res.ok:
                    html = res.text
                    record['bioproject'] = _extract_field(html, r'PRJCA\d+')
                    record['experiment_accession'] = _extract_field(html, r'CRX\d+')
                    record['sample_accession'] = _extract_field(html, r'SAMC\d+')
                    record['platform'] = _extract_meta(html, 'Platform') or _extract_meta(html, '测序平台')
                    record['model'] = record.get('platform')
                    record['library_strategy'] = _extract_meta(html, 'Library strategy') or _extract_meta(html, 'Strategy')
                    record['library_selection'] = None
                    record['library_source'] = _extract_meta(html, 'Source')
                    record.setdefault('library_layout', _extract_meta(html, 'Layout'))
                    record['taxon_name'] = _extract_meta(html, 'Species') or _extract_meta(html, '物种')
                    record['sample_name'] = _extract_meta(html, 'Alias') or acc
                    record['title'] = _extract_meta(html, 'Title')
            except Exception as e:
                logging.debug("Could not fetch rich metadata from NGDC web for {}: {}".format(acc, e))

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
    """Try to extract a metadata value following a label in HTML."""
    # Try th/td pattern
    pattern = r'(?:<th[^>]*>|<label[^>]*>)\s*{}\s*(?:</th>|</label>)\s*(?:<td[^>]*>)\s*([^<]+)'.format(
        re.escape(label))
    m = re.search(pattern, html, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Try label: value pattern
    pattern = r'{}[：:]\s*</?\w[^>]*>\s*([^<]+)'.format(re.escape(label))
    m = re.search(pattern, html, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    return None
