from .version import __version__

import logging
import json
import os
import subprocess
import sys
import shutil
import re
import tempfile
import gzip

import extern
from extern import ExternCalledProcessError
import bird_tool_utils

from .ena import EnaDownloader
from .ngdc import NgdcDownloader, fetch_ngdc_metadata
from .location import Location, NcbiLocationJson
from .exception import DownloadMethodFailed, KingfisherException
from .sra_metadata import *
from .md5sum import MD5
from .read_layouts import (
    apply_read_layout,
    possible_read_names,
    require_technical_reads_for_sra,
    semantic_filename,
    validate_read_layout_options,
    validate_read_name_style,
    validate_safe_name,
)

DEFAULT_ASPERA_SSH_KEY = 'linux'
DEFAULT_OUTPUT_FORMAT_POSSIBILITIES = ['fastq', 'fastq.gz']
DEFAULT_THREADS = 8
DEFAULT_DOWNLOAD_THREADS = DEFAULT_THREADS
DEFAULT_ASCP_ARGS = '-k 2' # resume criterion.

class OutputLocation:
    def __init__(self, output_directory):
        self.output_directory = os.path.abspath(output_directory)

        # Check to make sure the directory exists, or create it if is only 1 directory to be created.
        if not os.path.exists(self.output_directory):
            if not os.path.exists(os.path.dirname(self.output_directory)):
                raise Exception("The parent directory of the output directory specified '{}' does not exist. Kingfisher will create 1 directory if required, but not 2 or more. If you really want to output to that directory, you could try using 'mkdir -p '{}'".format(
                    self.output_directory,
                    self.output_directory))
            else:
                logging.info("Creating output directory {}".format(self.output_directory))
                os.mkdir(self.output_directory)

    def output_stem(self, run_identifier):
        return os.path.join(self.output_directory, run_identifier)


def find_numbered_read_files(run_identifier, extension, directory='.'):
    """Find <run>_<N>.<extension> files, sorted by numeric read number."""
    pattern = re.compile(r'^{}_(\d+)\.{}$'.format(
        re.escape(run_identifier), re.escape(extension)))
    numbered = []
    if not os.path.isdir(directory):
        return []
    for filename in os.listdir(directory):
        match = pattern.match(filename)
        if match:
            numbered.append((int(match.group(1)), os.path.join(directory, filename)))
    return [path for _, path in sorted(numbered, key=lambda item: item[0])]


def download_and_extract(**kwargs):
    '''download an public sequence dataset and extract if necessary. kwargs
    here are largely the same as the arguments to the kingfisher executable.
    '''
    run_identifiers = kwargs.pop('run_identifiers')
    run_identifiers_file = kwargs.pop('run_identifiers_file')
    bioproject_accession = kwargs.pop('bioproject_accession', None)  # kept for API stability
    bioproject_accessions = kwargs.pop('bioproject_accessions', None)

    if bioproject_accession and bioproject_accessions is None:
        bioproject_accessions = [bioproject_accession]

    num_inputs = 0
    if run_identifiers is not None: num_inputs += 1
    if run_identifiers_file is not None: num_inputs += 1
    if bioproject_accessions is not None: num_inputs += 1
    if num_inputs != 1:
        raise Exception("Must specify exactly one input type: --run-identifiers, --bioproject-accessions or --run-identifiers-list")

    if bioproject_accessions is not None:
        run_identifiers = SraMetadata().fetch_runs_from_bioprojects(bioproject_accessions)
        logging.debug("Found {} run(s) to annotate".format(len(run_identifiers)))
    if run_identifiers_file is not None:
        with open(run_identifiers_file) as f:
            run_identifiers = list([r.strip() for r in f.readlines()])

    if any(r.startswith('CRR') for r in run_identifiers):
        logging.warning("Support for NGDC/GSA CRR accessions is experimental")

    for run in run_identifiers:
        download_and_extract_one_run(run, **kwargs)

def download_and_extract_one_run(run_identifier, **kwargs):
    logging.debug("kwargs in download_and_extract_one_run: {}".format(kwargs))
    download_methods = kwargs.pop('download_methods')
    output_format_possibilities = kwargs.pop('output_format_possibilities',
        DEFAULT_OUTPUT_FORMAT_POSSIBILITIES)
    force = kwargs.pop('force', False)
    unsorted = kwargs.pop('unsorted', False)
    spot_sorted = kwargs.pop('spot_sorted', False)
    include_technical = kwargs.pop('include_technical', False)
    read_layout = kwargs.pop('read_layout', 'sra')
    read_names = kwargs.pop('read_names', None)
    read_name_style = kwargs.pop('read_name_style', 'simple')
    sample_name = kwargs.pop('sample_name', None)
    stdout = kwargs.pop('stdout', False)
    gcp_project = kwargs.pop('gcp_project', None)
    gcp_user_key_file = kwargs.pop('gcp_user_key_file', None)
    aws_user_key_id = kwargs.pop('aws_user_key_id', None)
    aws_user_key_secret = kwargs.pop('aws_user_key_secret', None)
    allow_paid = kwargs.pop('allow_paid', None)
    allow_paid_from_gcp = kwargs.pop('allow_paid_from_gcp', None)
    allow_paid_from_aws = kwargs.pop('allow_paid_from_aws', None)
    guess_aws_location = kwargs.pop('guess_aws_location', False)
    ascp_ssh_key = kwargs.pop('ascp_ssh_key', DEFAULT_ASPERA_SSH_KEY)
    ascp_args = kwargs.pop('ascp_args', DEFAULT_ASCP_ARGS)
    download_threads = kwargs.pop('download_threads', DEFAULT_DOWNLOAD_THREADS)
    extraction_threads = kwargs.pop('extraction_threads', DEFAULT_THREADS)
    hide_download_progress = kwargs.pop('hide_download_progress', False)
    prefetch_max_size = kwargs.pop('prefetch_max_size',None)
    check_md5sums = kwargs.pop('check_md5sums', False)
    output_directory = kwargs.pop('output_directory', '.')
    cra_accession = kwargs.pop('cra_accession', None)
    link_finding_method = kwargs.pop('link_finding_method', 'html')

    if len(kwargs) > 0:
        raise Exception("Unexpected arguments detected: %s" % kwargs)

    validate_read_layout_options(read_layout, read_names, sample_name)
    validate_read_name_style(read_name_style)
    if read_layout != 'sra':
        validate_safe_name(sample_name or run_identifier, 'sample name')

    if guess_aws_location and check_md5sums:
        logging.warning("Guessing AWS location is not compatible with checking md5sums. Not carrying out md5sum checks for downloads from AWS.")

    if allow_paid:
        allowable_sources = ['s3', 'gcp']
    else:
        allowable_sources = []
    if allow_paid or allow_paid_from_gcp:
        if 'gcp-cp' not in download_methods:
            logging.warning("Allowing download from requester-pays GCP buckets, "\
                "but gcp-cp is not specified download method, so --allow-paid and --allow-paid-from-gcp have no effect")
        allowable_sources.append('gcp')
    if allow_paid_from_aws:
        if 'aws-cp' not in download_methods:
            logging.warning("Allowing download from requester-pays AWS buckets, "\
                "but aws-cp is not specified download method, so --allow-paid-from-aws has no effect")
        allowable_sources.append('s3')
        
    logging.debug("Allowing non-NCBI sources for download: {}".format(allowable_sources))

    if gcp_project and gcp_user_key_file:
        raise Exception("--gcp-project is incompatible with --gcp-user-key-file. The project specified in the key file will be used when gcp_project is not specified.")

    if stdout and (spot_sorted or include_technical):
        raise Exception("--stdout cannot be combined with --spot-sorted or --include-technical")

    output_location_factory = OutputLocation(output_directory)
    output_files = []
    ncbi_locations = None

    # Checking for already existing files
    if stdout:
        skip_download_and_extraction, output_files = False, []
    else:
        skip_download_and_extraction, output_files = _check_for_existing_files(
            output_location_factory, run_identifier, output_format_possibilities, force,
            read_layout, read_names, read_name_style, sample_name
        )

    # If every requested output format is FASTA, base quality scores are
    # discarded during extraction anyway, so prefetch can fetch the smaller
    # SRA Lite file (simplified qualities) via --eliminate-quals.
    fasta_only_output = len(output_format_possibilities) > 0 and all(
        fmt in ('fasta', 'fasta.gz') for fmt in output_format_possibilities)

    downloaded_files = None
    if not skip_download_and_extraction:
        # Download phase
        worked = False
        for method in download_methods:
            if (method in ('prefetch', 'aws-http', 'aws-cp', 'gcp-cp') and
                    'sra' not in output_format_possibilities):
                require_technical_reads_for_sra(read_layout, include_technical)
            logging.info("Attempting download method {} for run {} ..".format(method, run_identifier))
            if method == 'prefetch':
                output_path = output_location_factory.output_stem('{}.sra'.format(run_identifier))
                try:
                    if prefetch_max_size is None:
                        prefetch_max_size_argument = '--max-size 0G'
                    else:
                        prefetch_max_size_argument = '--max-size {}'.format(prefetch_max_size)
                    # prefetch --output-file is deprecated apparently, so use --output-directory instead.
                    output_dir = os.path.dirname(output_path)
                    # For FASTA-only output, prefer the smaller SRA Lite file via
                    # --eliminate-quals. Not every run has an SRA Lite version
                    # (prefetch then fails), so fall back to a normal download.
                    prefetch_arg_variants = []
                    if fasta_only_output:
                        prefetch_arg_variants.append('--eliminate-quals ')
                    prefetch_arg_variants.append('')
                    prefetch_error = None
                    for extra_args in prefetch_arg_variants:
                        try:
                            extern.run("prefetch {}{} --output-directory {} {}".format(
                                extra_args, prefetch_max_size_argument, output_dir, run_identifier))
                            prefetch_error = None
                            break
                        except ExternCalledProcessError as e:
                            prefetch_error = e
                            # Clean up any partial download before the next attempt.
                            partial_run_dir = os.path.join(output_dir, run_identifier)
                            if os.path.isdir(partial_run_dir):
                                shutil.rmtree(partial_run_dir)
                            if extra_args:
                                logging.info(
                                    "SRA Lite download (--eliminate-quals) not available for {}: {}. "
                                    "Retrying prefetch with the full base-quality file ..".format(
                                        run_identifier, e))
                    if prefetch_error is not None:
                        raise prefetch_error
                    # prefetch --output-directory writes to a subdirectory named
                    # after the run, i.e. <dir>/<run>/<run>.sra, so move the file
                    # to the expected flat location. When --eliminate-quals is
                    # used (or a run is only available as SRA Lite), prefetch
                    # instead writes <dir>/<run>/<run>.sralite; treat that the
                    # same by renaming it to the .sra output path.
                    prefetch_run_dir = os.path.join(output_dir, run_identifier)
                    prefetch_output_path = os.path.join(
                        prefetch_run_dir, '{}.sra'.format(run_identifier))
                    prefetch_sralite_path = os.path.join(
                        prefetch_run_dir, '{}.sralite'.format(run_identifier))
                    if os.path.exists(prefetch_output_path):
                        shutil.move(prefetch_output_path, output_path)
                    elif os.path.exists(prefetch_sralite_path):
                        logging.info(
                            "Renaming downloaded .sralite (SRA Lite) file for {} to .sra ..".format(
                                run_identifier))
                        shutil.move(prefetch_sralite_path, output_path)
                    # Remove the run subdirectory once the main file has been
                    # moved out. For reference-compressed runs prefetch also
                    # downloads reference sequences into this directory, so use
                    # rmtree rather than rmdir; the references are re-fetched on
                    # demand during extraction if needed.
                    if os.path.isdir(prefetch_run_dir):
                        shutil.rmtree(prefetch_run_dir)
                    if os.path.exists(output_path):
                        downloaded_files = [output_path]
                    else:
                        logging.warning("Method {} failed: Prefetch did not create file {}".format(method, output_path))
                except ExternCalledProcessError as e:
                    logging.warning("Method {} failed: Error was: {}".format(method, e))
                    if os.path.exists(output_path):
                        logging.info("Removing file {} because download failed ..".format(output_path))
                        os.remove(output_path)
                
            elif method == 'aws-http':
                def download_from_aws(odp_link, run_identifier, download_threads, method):
                    output_path = output_location_factory.output_stem('{}.sra'.format(run_identifier))
                    try:
                        if download_threads > 1:
                            logging.info(
                                "Downloading .SRA file from AWS Open Data Program HTTP link using aria2c ..")
                            verbosity_flag = '--quiet' if hide_download_progress else ''
                            # Redirect aria2c stdout to stderr so all logging of kingfisher is on stderr.
                            # aria2c does not handle absolute paths properly, so we have to use a relative path.
                            cmd = "aria2c {} -x{} -o {} '{}' 1>&2".format(
                                verbosity_flag, download_threads, os.path.relpath(output_path), odp_link)
                            subprocess.check_call(cmd, shell=True)
                        else:
                            logging.info(
                                "Downloading .SRA file from AWS Open Data Program HTTP link using curl ..")
                            verbosity_flag = '--silent --show-error' if hide_download_progress else ''
                            cmd = "curl {} -o {} '{}'".format(verbosity_flag, output_path, odp_link)
                            subprocess.check_call(cmd, shell=True)
                        logging.info("Download finished, validating ..")
                        # A download with curl of a bad AWS address does not
                        # result in a non-zero exitstatus. Instead an XML
                        # document is returned. If it is XML, then download has
                        # failed.
                        with open(output_path,'rb') as f:
                            aws_failed = (f.read(8) != b'NCBI.sra')

                        if aws_failed:
                            logging.info("The file downloaded from AWS appears not to be a .sra file, deleting it, this download method failed")
                            os.remove(output_path)
                            return None
                        else:
                            return [output_path]
                    except subprocess.CalledProcessError as e:
                        logging.warning("Method {} failed when downloading from {}: Error was: {}".format(method, odp_link, e))
                        if os.path.exists(output_path):
                            logging.info("Removing file {} because download failed ..".format(output_path))
                            os.remove(output_path)
                        return None

                if guess_aws_location:
                    # e.g. https://sra-pub-run-odp.s3.amazonaws.com/sra/SRR12118866/SRR12118866
                    guessed_location = 'https://sra-pub-run-odp.s3.amazonaws.com/sra/{}/{}'.format(run_identifier, run_identifier)
                    logging.info("Guessing AWS-ODP link to be: {}".format(guessed_location))
                    downloaded_files = download_from_aws(guessed_location, run_identifier, download_threads, method)
                else:
                    if ncbi_locations is None:
                        ncbi_locations = Location.get_ncbi_locations(run_identifier)
                    odp_http_locations = ncbi_locations.object_locations(
                        NcbiLocationJson.OBJECT_TYPE_SRA, NcbiLocationJson.AWS_SERVICE, False
                    )

                    if len(odp_http_locations) > 0:
                        for odp_http_location in odp_http_locations:
                            logging.debug("Found ODP link {}".format(odp_http_location))
                            logging.info("Found ODP link {}".format(odp_http_location.link()))
                            odp_link = odp_http_location.link()
                            downloaded_files = download_from_aws(odp_link, run_identifier, download_threads, method)
                            if downloaded_files is not None and check_md5sums:
                                for downloaded_file in downloaded_files:
                                    # Is there always just 1 .sra file? There is only 1 md5sum
                                    logging.info("Checking md5sum of downloaded file {} ..".format(downloaded_file))
                                    if MD5.check_md5sum(downloaded_file, odp_http_location.md5sum()):
                                        logging.info("MD5sum OK for {}".format(downloaded_file))
                                    else:
                                        logging.warning("MD5sum check failed for {}".format(downloaded_file))
                    else:
                        logging.warning("Method {} failed: No ODP URL could be found".format(method))

            elif method == 'aws-cp':
                if ncbi_locations is None:
                    ncbi_locations = Location.get_ncbi_locations(run_identifier)

                s3_locations = ncbi_locations.object_locations(
                    NcbiLocationJson.OBJECT_TYPE_SRA,
                    NcbiLocationJson.AWS_SERVICE,
                    's3' in allowable_sources
                )

                # TODO: Sort so unpaid are first
                output_path = output_location_factory.output_stem('{}.sra'.format(run_identifier))

                if len(s3_locations) > 0:
                    for s3_location in s3_locations:
                        logging.info("Found s3 link {}".format(s3_location.link()))

                        try:
                            command = '{} {}'.format(
                                s3_location.s3_command_prefix(run_identifier), output_path
                            )
                            if aws_user_key_id:
                                os.environ['AWS_ACCESS_KEY_ID'] = aws_user_key_id
                            if aws_user_key_id:
                                os.environ['AWS_SECRET_ACCESS_KEY'] = aws_user_key_secret
                            logging.info("Downloading from S3..")
                            try:
                                extern.run(command)
                                downloaded_files = [output_path]
                            except ExternCalledProcessError as e:
                                logging.warning("Method {} failed: Error was: {}".format(method, e))
                        except DownloadMethodFailed as e:
                            logging.warning("Method {} failed, error was {}".format(
                                method, e
                            ))
                            if os.path.exists(output_path):
                                logging.info("Removing file {} because download failed ..".format(output_path))
                                os.remove(output_path)
                else:
                    logging.warning("Method {} failed: No S3 location could be found".format(method))
                    if os.path.exists(output_path):
                        logging.info("Removing file {} because download failed ..".format(output_path))
                        os.remove(output_path)

            elif method == 'gcp-cp':
                output_path = output_location_factory.output_stem('{}.sra'.format(run_identifier))
                if 'gcp' in allowable_sources:
                    if ncbi_locations is None:
                        ncbi_locations = Location.get_ncbi_locations(run_identifier)
                    locations = ncbi_locations.object_locations(
                        NcbiLocationJson.OBJECT_TYPE_SRA, NcbiLocationJson.GCP_SERVICE, True
                    )
                    if len(locations) > 0:
                        for loc in locations:
                            command = 'gsutil'
                            gcp_project = gcp_project
                            if gcp_user_key_file:
                                with open(gcp_user_key_file) as f:
                                    j = json.load(f)
                                    if 'project_id' not in j:
                                        raise Exception("Unexpectedly could not find project_id in GCP user key JSON file")
                                    gcp_project = j['project_id']
                                extern.run('gcloud auth activate-service-account --key-file={}'.format(gcp_user_key_file))

                            failed = False
                            if gcp_project:
                                command = command + " -u {}".format(gcp_project)
                            else:
                                logging.info("Finding Google cloud project to charge")
                                project_id = extern.run('gcloud config get-value project').strip()
                                if project_id == '':
                                    logging.warning("Method gcp-cp failed: Could not find a GCP project to charge, cannot continue. "\
                                        "Expected a project from 'gcloud config get-value project' or specified with --gcp-user-key-file or --gcp-project")
                                    failed = True
                                else:
                                    logging.info("Charging to project \'{}\'".format(project_id))
                                    command = command + " -u {}".format(project_id)
                            if not failed:
                                try:
                                    gs_path = loc.gs_path()
                                    command += ' cp {} {}'.format(
                                        gs_path, output_path
                                    )
                                    logging.info("Downloading from GCP..")
                                    try:
                                        extern.run(command)
                                        downloaded_files = [output_path]
                                    except ExternCalledProcessError as e:
                                        logging.warning("Method {} failed: Error was: {}".format(method, e))
                                        
                                except DownloadMethodFailed as e:
                                    logging.warning("Method {} failed, error was {}".format(
                                        method, e
                                    ))
                                    if os.path.exists(output_path):
                                        logging.info("Removing file {} because download failed ..".format(output_path))
                                        os.remove(output_path)
                    else:
                        logging.warning("Method {} failed: No GCP location could be found".format(method))
                else:
                    logging.warning("Not using method gcp-cp as --allow-paid was not specified")

            elif method == 'ena-ascp':
                result = EnaDownloader().download_with_aspera(run_identifier, output_directory,
                    ascp_args=ascp_args,
                    ssh_key=ascp_ssh_key,
                    check_md5sums=check_md5sums)
                if result is not False:
                    gzip_test_files(result)
                    downloaded_files = result

            elif method == 'ena-ftp':
                result = EnaDownloader().download_with_curl(
                    run_identifier,
                    download_threads,
                    output_directory,
                    check_md5sums=check_md5sums)
                if result is not False:
                    gzip_test_files(result)
                    downloaded_files = result

            elif method == 'ngdc-ascp':
                result = NgdcDownloader().download_with_aspera(
                    run_identifier, output_directory,
                    ascp_args=ascp_args,
                    ssh_key=ascp_ssh_key,
                    known_cra_accession=cra_accession)
                if result is not False:
                    gzip_test_files([f for f in result if f.endswith('.gz')])
                    downloaded_files = result

            elif method == 'ngdc-http':
                result = NgdcDownloader().download_with_ftp(
                    run_identifier,
                    download_threads,
                    output_directory,
                    known_cra_accession=cra_accession,
                    link_finding_method=link_finding_method)
                if result is not False:
                    gzip_test_files([f for f in result if f.endswith('.gz')])
                    downloaded_files = result

            else:
                raise Exception("Unknown method: {}".format(method))
            
            if downloaded_files is not None:
                logging.info("Method {} worked.".format(method))
                break
            else:
                logging.warning("Method {} failed".format(method))

        if downloaded_files is None:
            raise Exception("No more specified download methods, cannot continue")

    # Extraction/conversion phase
    if not skip_download_and_extraction:
        if downloaded_files == [output_location_factory.output_stem('{}.sra'.format(run_identifier))]:
            sra_file = downloaded_files[0]
            if 'sra' not in output_format_possibilities:
                output_files = extract(
                    sra_file = sra_file,
                    output_format_possibilities = output_format_possibilities,
                    unsorted = unsorted,
                    spot_sorted = spot_sorted,
                    include_technical = include_technical,
                    read_layout = read_layout,
                    read_names = read_names,
                    read_name_style = read_name_style,
                    sample_name = sample_name,
                    stdout = stdout,
                    threads = extraction_threads,
                    output_directory = output_directory,
                )
                os.remove(sra_file)
            else:
                output_files.append(sra_file)
        else:
            if stdout:
                raise Exception("--stdout currently must be via download of a .sra format file, rather than a download from ENA. I imagine this will be fixed in future.")
            if 'fastq.gz' in output_format_possibilities:
                output_files = downloaded_files
            else:
                # Check for files with standard ENA naming or NGDC naming
                candidate_files = find_numbered_read_files(
                    run_identifier, 'fastq.gz', output_location_factory.output_directory)
                single = output_location_factory.output_stem('{}.fastq.gz'.format(run_identifier))
                if os.path.exists(single):
                    candidate_files.append(single)
                # Also check for NGDC-style naming (CRR######_f1.fastq.gz, CRR######_r2.fastq.gz)
                for fq in ['x_f1.fastq.gz','x_r2.fastq.gz']:
                    f = output_location_factory.output_stem(fq.replace('x',run_identifier))
                    if os.path.exists(f):
                        candidate_files.append(f)
                # Fall back to whatever was downloaded if no standard names match
                if not candidate_files:
                    candidate_files = [f for f in downloaded_files if os.path.exists(f)]
                for f in candidate_files:
                    # Do the least work, currently we have FASTQ.gz
                    try:
                        if 'fasta' in output_format_possibilities:
                            logging.info("Converting {} to FASTA ..".format(f))
                            out_here = f.replace('.fastq.gz','.fasta')
                            extern.run("pigz -p {} -cd {} |awk '{{print \">\" substr($0,2);getline;print;getline;getline}}' >{}".format(
                                extraction_threads, f, out_here
                            ))
                            os.remove(f)
                            output_files.append(out_here)
                        elif 'fasta.gz' in output_format_possibilities:
                            logging.info("Converting {} to FASTA and compressing with pigz ..".format(f))
                            out_here = f.replace('.fastq.gz','.fasta.gz')
                            extern.run("pigz -cd {} |awk '{{print \">\" substr($0,2);getline;print;getline;getline}}' |pigz -p {} >{}".format(
                                f, extraction_threads, out_here
                            ))
                            os.remove(f)
                            output_files.append(out_here)
                        elif 'fastq' in output_format_possibilities:
                            logging.info("Decompressing {} with pigz ..".format(f))
                            extern.run("pigz -p {} -d {}".format(extraction_threads, f))
                            output_files.append(f.replace('.fastq.gz','.fastq'))
                        else:
                            raise Exception("Programming error")
                    except ExternCalledProcessError as e:
                        raise KingfisherException(
                            "Format conversion failed for '{}'".format(f), inner=e)

            output_files = apply_read_layout(
                output_files, run_identifier, read_layout, read_names,
                read_name_style, sample_name, force)
                
    if not stdout and len(output_files) == 0:
        raise Exception("No output files found, something went amiss, unsure what.")

    logging.info("Output files: {}".format(', '.join(output_files)))

    
def extract(**kwargs):
    sra_file = kwargs.pop('sra_file')
    output_format_possibilities = kwargs.pop('output_format_possibilities',
        DEFAULT_OUTPUT_FORMAT_POSSIBILITIES)
    force = kwargs.pop('force', False)
    unsorted = kwargs.pop('unsorted', False)
    spot_sorted = kwargs.pop('spot_sorted', False)
    include_technical = kwargs.pop('include_technical', False)
    read_layout = kwargs.pop('read_layout', 'sra')
    read_names = kwargs.pop('read_names', None)
    read_name_style = kwargs.pop('read_name_style', 'simple')
    sample_name = kwargs.pop('sample_name', None)
    stdout = kwargs.pop('stdout', False)
    threads = kwargs.pop('threads',DEFAULT_THREADS)
    output_directory = kwargs.pop('output_directory', '.')

    if len(kwargs) > 0:
        raise Exception("Unexpected arguments detected: %s" % kwargs)

    validate_read_layout_options(read_layout, read_names, sample_name)
    validate_read_name_style(read_name_style)
    require_technical_reads_for_sra(read_layout, include_technical)

    if stdout and (spot_sorted or include_technical):
        raise Exception("--stdout cannot be combined with --spot-sorted or --include-technical")

    run_identifier = os.path.basename(sra_file)
    if sra_file.endswith(".sra"):
        run_identifier = run_identifier[:-4]
    logging.debug("Using run identifier {}".format(run_identifier))
    if read_layout != 'sra':
        validate_safe_name(sample_name or run_identifier, 'sample name')

    output_location_factory = OutputLocation(output_directory)

    # Checking for already existing files
    if stdout:
        skip_download_and_extraction, output_files = False, []
    else:
        skip_download_and_extraction, output_files = _check_for_existing_files(
            output_location_factory, run_identifier, output_format_possibilities, force,
            read_layout, read_names, read_name_style, sample_name
        )
    
    if stdout:
        format = output_format_possibilities[0]
        sra_file_abs = os.path.abspath(sra_file)
        # --accept-singles streams pairs and any single/orphan reads to stdout as
        # one intact stream, so single-end runs work too. (Don't route singles
        # via --single-out /dev/stdout: sracat-rs opens that as a separate,
        # truncating file with its own offset, corrupting output when stdout is
        # redirected to a regular file.)
        if format == 'fasta':
            logging.info("Extracting unsorted .sra file to STDOUT in FASTA format ..")
            cmd = "sracat-rs --accept-singles {}".format(sra_file_abs)
        elif format == 'fasta.gz':
            logging.info("Extracting unsorted .sra file to STDOUT in FASTA.GZ format ..")
            cmd = "sracat-rs --accept-singles {} |pigz -p {} -c".format(sra_file_abs, threads)
        elif format == 'fastq':
            logging.info("Extracting unsorted .sra file to STDOUT in FASTQ format ..")
            cmd = "sracat-rs --qual --accept-singles {}".format(sra_file_abs)
        elif format == 'fastq.gz':
            logging.info("Extracting unsorted .sra file to STDOUT in FASTQ.GZ format ..")
            cmd = "sracat-rs --qual --accept-singles {} |pigz -p {} -c".format(sra_file_abs, threads)
        else:
            raise Exception("Cannot extract with --stdout --unsorted format {}".format(format))
        logging.debug("Running command {}".format(cmd))
        try:
            subprocess.check_call(cmd, shell=True, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            raise KingfisherException(
                "Extraction of .sra file failed. Command run was '{}'. STDERR was '{}'".format(cmd, e.stderr),
                inner=e)
            
    else:
        if not skip_download_and_extraction:
            # Change directory to the output directory using a "with", so that the
            # extractor outputs there, not here.
            sra_file_abs = os.path.abspath(sra_file)
            with bird_tool_utils.in_working_directory(output_directory):
                if spot_sorted or include_technical:
                    # fasterq-dump emits reads in spot (submission) order, writing
                    # numbered split files and, where relevant, {run}.fastq. It
                    # only produces uncompressed FASTQ, so convert/compress later.
                    try:
                        reason = "technical reads" if include_technical else "spot-sorted"
                        logging.info("Extracting .sra file with fasterq-dump ({}) ..".format(reason))
                        extra_args = "--include-technical --split-files " if include_technical else ""
                        extern.run("fasterq-dump --threads {} {}{}".format(
                            threads, extra_args, sra_file_abs))
                    except ExternCalledProcessError as e:
                        raise KingfisherException(
                            "Extraction of .sra file failed for '{}'".format(sra_file), inner=e)

                    fastq_files = find_numbered_read_files(run_identifier, 'fastq')
                    single = '{}.fastq'.format(run_identifier)
                    if os.path.exists(single):
                        fastq_files.append(single)

                    # Drop empty split files before further processing.
                    for f in list(fastq_files):
                        if os.path.exists(f) and os.path.getsize(f) == 0:
                            os.remove(f)
                            fastq_files.remove(f)

                    if 'fastq' not in output_format_possibilities:
                        for f in fastq_files:
                            try:
                                # Do least work; current format is FASTQ.
                                if 'fasta' in output_format_possibilities:
                                    logging.info("Converting {} to FASTA ..".format(f))
                                    out_here = os.path.abspath(re.sub(r'\.fastq$', '.fasta', f))
                                    extern.run("awk '{{print \">\" substr($0,2);getline;print;getline;getline}}' {} >{}".format(f, out_here))
                                elif 'fasta.gz' in output_format_possibilities:
                                    logging.info("Converting {} to FASTA and compressing with pigz ..".format(f))
                                    out_here = os.path.abspath(re.sub(r'\.fastq$', '.fasta.gz', f))
                                    extern.run("awk '{{print \">\" substr($0,2);getline;print;getline;getline}}' {} |pigz -p {} >{}".format(f, threads, out_here))
                                elif 'fastq.gz' in output_format_possibilities:
                                    out_here = os.path.abspath('{}.gz'.format(f))
                                    logging.info("Compressing {} with pigz into {} ..".format(f, out_here))
                                    extern.run("pigz -c -p {} {} > {}".format(threads, f, out_here))
                                else:
                                    raise Exception("Programming error")
                                os.remove(f)
                                output_files.append(out_here)
                            except ExternCalledProcessError as e:
                                raise KingfisherException(
                                    "Format conversion failed for '{}'".format(f), inner=e)
                    else:
                        output_files.extend(fastq_files)
                else:
                    # sracat-rs emits reads in storage order (the default). Extract
                    # straight to the requested format, piping into pigz for
                    # compressed outputs so no intermediate FASTQ/FASTA is written.
                    # Priority mirrors the conversion order above: do the least work.
                    if 'fastq' in output_format_possibilities:
                        target_format = 'fastq'
                    elif 'fasta' in output_format_possibilities:
                        target_format = 'fasta'
                    elif 'fasta.gz' in output_format_possibilities:
                        target_format = 'fasta.gz'
                    elif 'fastq.gz' in output_format_possibilities:
                        target_format = 'fastq.gz'
                    else:
                        raise Exception("Programming error")
                    output_files = _extract_with_sracat(
                        sra_file_abs, run_identifier, target_format, threads)

    if not stdout and not skip_download_and_extraction:
        output_files = apply_read_layout(
            output_files, run_identifier, read_layout, read_names,
            read_name_style, sample_name, force)
    return output_files


def _stream_has_no_reads(path, compressed):
    """Return True if the extraction output at `path` contains no reads. For a
    compressed (.gz) file that means an empty decompressed stream (pigz still
    writes a ~20-byte gzip container even when its FIFO carries nothing); for an
    uncompressed file it means zero bytes."""
    if compressed:
        with gzip.open(path, 'rb') as fh:
            return fh.read(1) == b''
    return os.path.getsize(path) == 0


def _extract_with_sracat(sra_file_abs, run_identifier, target_format, threads):
    """Extract an .sra file with sracat-rs into files named after run_identifier
    in the current working directory, in the requested target_format ('fastq',
    'fasta', 'fastq.gz' or 'fasta.gz'). Compressed formats are produced by piping
    sracat-rs directly into pigz through FIFOs, avoiding an intermediate
    uncompressed file. Returns the list of non-empty output files (absolute
    paths). sracat-rs emits reads in storage order (the default)."""
    qual = target_format.startswith('fastq')
    compress = target_format.endswith('.gz')
    sracat_qual = '--qual ' if qual else ''

    out1 = os.path.abspath('{}_1.{}'.format(run_identifier, target_format))
    out2 = os.path.abspath('{}_2.{}'.format(run_identifier, target_format))
    outs = os.path.abspath('{}.{}'.format(run_identifier, target_format))
    outputs = [out1, out2, outs]

    logging.info("Extracting .sra file with sracat-rs ..")
    if compress:
        # Route each of sracat-rs's three outputs (forward, reverse, single/orphan)
        # through its own FIFO into a dedicated pigz. --eager-open-output ensures
        # the single/orphan FIFO always gets a writer (and thus its pigz reader a
        # clean EOF) even for cleanly-paired runs that emit no orphans, so the
        # reader never blocks forever on open().
        fifo_dir = tempfile.mkdtemp(prefix='kingfisher_sracat_')
        fifos = [os.path.join(fifo_dir, n) for n in ('read1', 'read2', 'single')]
        pigz_procs = []
        extraction_ok = False
        try:
            for fifo, out in zip(fifos, outputs):
                os.mkfifo(fifo)
                pigz_procs.append(subprocess.Popen(
                    "pigz -p {} -c < '{}' > '{}'".format(threads, fifo, out),
                    shell=True))
            cmd = "sracat-rs {}--threads {} --eager-open-output -1 '{}' -2 '{}' --single '{}' '{}'".format(
                sracat_qual, threads, fifos[0], fifos[1], fifos[2], sra_file_abs)
            logging.debug("Running command {}".format(cmd))
            # Capture stderr (rather than letting it inherit the terminal) so
            # sracat-rs's summary stays quiet on success and its error message is
            # available to report on failure.
            result = subprocess.run(cmd, shell=True, stderr=subprocess.PIPE)
            if result.returncode != 0:
                raise KingfisherException(
                    "Extraction of .sra file failed for '{}'. STDERR was '{}'".format(
                        sra_file_abs, result.stderr.decode()))
            # Reap every pigz before reporting a failure, so none are left
            # unwaited even when one of them exits non-zero.
            pigz_failed = False
            for p in pigz_procs:
                if p.wait() != 0:
                    pigz_failed = True
            if pigz_failed:
                raise KingfisherException(
                    "Compression with pigz failed during extraction of '{}'".format(sra_file_abs))
            extraction_ok = True
        finally:
            if not extraction_ok:
                # On any failure (a non-zero sracat-rs/pigz exit, or an exception
                # such as os.mkfifo/Popen raising mid-setup) sracat-rs may never
                # have opened the FIFOs, leaving pigz readers blocked on open().
                # Kill and reap every pigz so none are orphaned, then remove the
                # partial .gz files the pigz '> out' redirect created up front so
                # a later run doesn't mistake them for completed output.
                for p in pigz_procs:
                    if p.poll() is None:
                        p.kill()
                    p.wait()
                for out in outputs:
                    if os.path.exists(out):
                        os.remove(out)
            shutil.rmtree(fifo_dir, ignore_errors=True)
    else:
        cmd = "sracat-rs {}--threads {} -1 '{}' -2 '{}' --single '{}' '{}'".format(
            sracat_qual, threads, out1, out2, outs, sra_file_abs)
        logging.debug("Running command {}".format(cmd))
        # extern.run captures stdout/stderr, keeping sracat-rs's summary off the
        # terminal on success and surfacing it in the error on failure.
        try:
            extern.run(cmd)
        except ExternCalledProcessError as e:
            raise KingfisherException(
                "Extraction of .sra file failed for '{}'".format(sra_file_abs), inner=e)

    # sracat-rs (with --eager-open-output plus pigz) can leave empty split files
    # for a single-end or cleanly-paired run; drop any that carry no reads.
    kept = []
    for f in outputs:
        if not os.path.exists(f):
            continue
        if _stream_has_no_reads(f, compress):
            os.remove(f)
        else:
            kept.append(f)
    return kept

def gzip_test_files(gzip_files):
    """
    Run "pigz -t" on each result file, to check that it is a valid gzip file.

    Assumes the input is a list of paths of gzip files
    """
    for f in gzip_files:
        logging.info("Verifying gzip file {} ..".format(f))
        try:
            extern.run("pigz -t '{}'".format(f))
        except ExternCalledProcessError as e:
            raise KingfisherException(
                "Download verification failed for '{}': pigz -t returned non-zero exit status".format(f),
                inner=e)


def annotate(**kwargs):
    run_identifiers = kwargs.pop('run_identifiers')
    run_identifiers_file = kwargs.pop('run_identifiers_file')
    bioproject_accessions = kwargs.pop('bioproject_accessions', None)  # kept for API stability
    bioproject_accession = kwargs.pop('bioproject_accession', None)
    output_file = kwargs.pop('output_file')
    output_format = kwargs.pop('output_format')
    all_columns = kwargs.pop('all_columns')

    if bioproject_accession and bioproject_accessions is None:
        bioproject_accessions = [bioproject_accession]

    num_inputs = 0
    if run_identifiers is not None: num_inputs += 1
    if run_identifiers_file is not None: num_inputs += 1
    if bioproject_accessions is not None: num_inputs += 1
    if num_inputs != 1:
        raise Exception("Must specify exactly one input type: --run-identifiers, --bioproject-accessions or --run-identifiers-list")
    
    if bioproject_accessions is not None:
        run_identifiers = SraMetadata().fetch_runs_from_bioprojects(bioproject_accessions)
        logging.debug("Found {} run(s) to annotate".format(len(run_identifiers)))
    if run_identifiers_file is not None:
        with open(run_identifiers_file) as f:
            run_identifiers = list([r.strip() for r in f.readlines()])
        
    if len(kwargs) > 0:
        raise Exception("Unexpected arguments detected: %s" % kwargs)

    # Split accessions into NGDC (CRR) and SRA types
    ngdc_accessions = [r for r in run_identifiers if r.startswith('CRR')]
    if ngdc_accessions:
        logging.warning("Support for NGDC/GSA CRR accessions is experimental")
    sra_accessions = [r for r in run_identifiers if not r.startswith('CRR')]

    metadata_parts = []
    if sra_accessions:
        metadata = SraMetadata().efetch_sra_from_accessions(sra_accessions)
        if metadata is not None:
            metadata_parts.append(metadata)
    if ngdc_accessions:
        ngdc_metadata = fetch_ngdc_metadata(ngdc_accessions)
        if ngdc_metadata is not None and len(ngdc_metadata) > 0:
            metadata_parts.append(ngdc_metadata)

    if not metadata_parts:
        logging.error("No runs to annotate")
        sys.exit(1)

    import pandas as pd
    metadata = pd.concat(metadata_parts, ignore_index=True)
    _output_formatted_metadata(metadata, output_file, output_format, all_columns)


def _output_formatted_metadata(metadata, output_file, output_format, all_columns):
    # NOTE: If changing this default set, also need to change the default set in human readable output below too.
    default_columns = [RUN_ACCESSION_KEY,BIOPROJECT_ACCESSION_KEY,'Gbp','library_strategy','library_selection','model',SAMPLE_NAME_KEY,'taxon_name']

    def prepare_for_tsv_csv(metadata, default_columns, all_columns):
        metadata_sorted = metadata.sort_values(RUN_ACCESSION_KEY)
        # For very large data frames, pandas throws an error 'InvalidIndexError:
        # Reindexing only valid with uniquely valued Index objects' when doing
        # the pd.concat() below. We have to do that concat because a simple
        # metadata_sorted['Gbp'] = ... gives a Performance warning. To get
        # around this, we reset the index to a RangeIndex, which does not
        # contain duplicates.
        metadata_sorted.reset_index(drop=True, inplace=True)
        if BASES_KEY in metadata_sorted.columns:
            metadata_sorted = pd.concat(
                [
                    metadata_sorted,
                    pd.DataFrame({'Gbp': [
                        round(bases/1e9, 3) if bases is not None else None for bases in metadata_sorted[BASES_KEY]]})
                ],
                axis=1)
        if all_columns:
            # Re-order columns to be consistent with human format output
            available_defaults = [c for c in default_columns if c in metadata_sorted.columns]
            column_order = available_defaults + [c for c in metadata_sorted.columns if c not in available_defaults]
            return metadata_sorted[column_order]
        else:
            available_defaults = [c for c in default_columns if c in metadata_sorted.columns]
            metadata_sorted = metadata_sorted[available_defaults]
            return metadata_sorted

    output_path = sys.stdout if output_file is None else output_file

    if output_format == 'human':
        to_print = []
        for value in metadata[RUN_ACCESSION_KEY]:
            to_print.append({RUN_ACCESSION_KEY: value})
        if BIOPROJECT_ACCESSION_KEY in metadata.columns:
            for i, value in enumerate(metadata[BIOPROJECT_ACCESSION_KEY]):
                to_print[i][BIOPROJECT_ACCESSION_KEY] = value
        if BASES_KEY in metadata.columns:
            for i, value in enumerate(metadata[BASES_KEY]):
                to_print[i]['Gbp'] = "%.3f" % (value/1e9) if value is not None else None
        for column in ['library_strategy','library_selection','model',SAMPLE_NAME_KEY,'taxon_name']:
            if column in metadata.columns:
                for i, value in enumerate(metadata[column]):
                    to_print[i][column] = value
        if all_columns:
            for col in metadata.columns:
                if col not in default_columns:
                    for i, value in enumerate(metadata[col]):
                        to_print[i][col] = value
        to_print = sorted(to_print, key=lambda x: x[RUN_ACCESSION_KEY])
        if output_path == sys.stdout:
            _printTable(sys.stdout, to_print)
        else:
            with open(output_path, 'w') as f:
                _printTable(f, to_print)
    elif output_format == 'csv':
        metadata_sorted = prepare_for_tsv_csv(metadata, default_columns, all_columns)
        metadata_sorted.to_csv(output_path, index=False)
    elif output_format == 'tsv':
        metadata_sorted = prepare_for_tsv_csv(metadata, default_columns, all_columns)
        metadata_sorted.to_csv(output_path, sep='\t', index=False)
    elif output_format == 'json':
        metadata_sorted = prepare_for_tsv_csv(metadata, default_columns, all_columns)
        metadata_sorted.to_json(output_path, orient='records', indent=2)
    elif output_format == 'feather':
        metadata_sorted = prepare_for_tsv_csv(metadata, default_columns, all_columns)
        with open(output_file,'wb') as f:
            metadata_sorted.to_feather(f)
    elif output_format == 'parquet':
        metadata_sorted = prepare_for_tsv_csv(metadata, default_columns, all_columns)
        with open(output_file,'wb') as f:
            metadata_sorted.to_parquet(f, index=False)
    else:
        raise Exception("Unexpected output format: {}".format(output_format))

def _printTable(output_stream, myDict, colList=None):
   if not colList: colList = list(myDict[0].keys() if myDict else [])
   myList = [colList] # 1st row = header
   for item in myDict: myList.append([str(item[col] if item[col] is not None else '') for col in colList])
   colSize = [max(map(len,col)) for col in zip(*myList)]
   formatStr = ' | '.join(["{{:<{}}}".format(i) for i in colSize])
   myList.insert(1, ['-' * i for i in colSize]) # Seperating line
   for item in myList: print(formatStr.format(*item), file=output_stream)

def _check_for_existing_files(output_location_factory, run_identifier,
                              output_format_possibilities, force,
                              read_layout='sra', read_names=None,
                              read_name_style='simple', sample_name=None):
    skip_download_and_extraction = False
    output_files = []

    def maybe_skip_or_force(path, output_files, force):
        skip_download_and_extraction = False
        final_path = output_location_factory.output_stem(path)
        if os.path.exists(final_path):
            if force:
                logging.warn("Removing previous file {}".format(final_path))
                os.remove(final_path)
            else:
                skip_download_and_extraction = True
                output_files.append(final_path)
                logging.info(
                    "Skipping download/extraction of {} as an output file already appears to exist, as file {}".format(run_identifier, final_path))
        return skip_download_and_extraction, output_files

    # SRA itself never receives semantic naming.
    if 'sra' in output_format_possibilities:
        skip, output_files = maybe_skip_or_force(
            '{}.sra'.format(run_identifier), output_files, force)
        if skip:
            return True, output_files

    if read_layout != 'sra':
        sample = sample_name or run_identifier
        partial_targets = []
        for file_type in output_format_possibilities:
            if file_type == 'sra':
                continue
            name_sets = possible_read_names(read_layout, read_names)
            target_sets = []
            for names in name_sets:
                target_sets.append([
                    output_location_factory.output_stem(
                        semantic_filename(sample, name, file_type, read_name_style))
                    for name in names
                ])

            existing = []
            for targets in target_sets:
                for target in targets:
                    if os.path.exists(target) and target not in existing:
                        existing.append(target)
            if force:
                for target in existing:
                    logging.warning("Removing previous file {}".format(target))
                    os.remove(target)
                continue

            # Flexible layouts are ordered largest-first. Prefer complete set
            # with most streams when multiple mappings share names.
            for targets in target_sets:
                if targets and all(os.path.exists(target) for target in targets):
                    logging.info(
                        "Skipping download/extraction of {} as semantic output files already exist".format(
                            run_identifier))
                    return True, targets
            partial_targets.extend(existing)

        if partial_targets:
            raise KingfisherException(
                "Incomplete existing output for read layout '{}'; refusing to overwrite: {}".format(
                    read_layout, ', '.join(partial_targets)))
        return False, []

    for file_type in output_format_possibilities:
        if file_type == 'sra':
            continue
        elif file_type in ('fastq', 'fastq.gz', 'fasta', 'fasta.gz'):
            directory = output_location_factory.output_directory
            numbered = find_numbered_read_files(run_identifier, file_type, directory)
            legacy = [
                output_location_factory.output_stem('{}.{}'.format(run_identifier, file_type)),
                output_location_factory.output_stem('{}_f1.{}'.format(run_identifier, file_type)),
                output_location_factory.output_stem('{}_r2.{}'.format(run_identifier, file_type)),
            ]
            for final_path in numbered + legacy:
                if not os.path.exists(final_path):
                    continue
                relative_path = os.path.relpath(final_path, directory)
                skip, output_files = maybe_skip_or_force(relative_path, output_files, force)
                if skip: skip_download_and_extraction = True
        else:
            raise Exception("Programming error")

    return skip_download_and_extraction, output_files

def authorship(**kwargs):
    '''Try to attribute authorship / publications of SRA runs
    '''
    run_identifiers = kwargs.pop('run_identifiers')
    run_identifiers_file = kwargs.pop('run_identifiers_file')

    num_inputs = 0
    if run_identifiers is not None: num_inputs += 1
    if run_identifiers_file is not None: num_inputs += 1
    if num_inputs != 1:
        raise Exception("Must specify exactly one input type: --run-identifiers or --run-identifiers-list")

    if run_identifiers_file is not None:
        with open(run_identifiers_file) as f:
            run_identifiers = list([r.strip() for r in f.readlines()])

    logging.info("Finding associated authorship / publications for {} run(s)".format(len(run_identifiers)))  

    # SRR7051058 is a good example of a run with GOLD authorship info

    final_result = []

    for run in run_identifiers:
        logging.debug("Looking up authorship for run {}".format(run))

        # ERR1914274 has a pubmed ID associated
        # <STUDY_LINKS>
        # <STUDY_LINK>
        # <XREF_LINK>
        # <DB>PUBMED</DB>
        # <ID>29669589</ID>

        # Get the metadata for the run
        metadata = SraMetadata().efetch_sra_from_accessions([run])
        # TODO: Do a single esearch and don't assume a result returned
        m = metadata.iloc[0,:].to_dict()
        # TODO: Account for multiple IDs in the same DB - not sure of an example tho
        
        to_print = {
            'Run': run,
        }
        if 'study_links' in m:
            study_links_json = m['study_links']
            study_links = json.loads(study_links_json)
            for link in study_links:
                if 'db' in link:
                    db = link['db']
                    del link['db']
                elif 'label' in link:
                    db = link['label']
                    del link['label']
                else:
                    if 'Other study links in list' not in to_print:
                        to_print['Other study links in list'] = []
                    to_print['Other study links in list'].append(link)

                if db == 'pubmed':
                    to_print['PubMed ID'] = link['id']
                elif db == 'GOLD':
                    to_print['GOLD ID'] = link['url']
                else:
                    if 'Other study links' not in to_print:
                        to_print['Other study links'] = {}
                    content_name = list(link.keys())[0]
                    to_print['Other study links'][db] = link[content_name]

        # Search PubMed for a title the same as the project name
        # e.g. Characterisation of a sponge microbiome using an integrative genome-centric approach
        # SRR9841429
        study_title = m['study_title']
        logging.debug("Searching PubMed for title '{}'".format(study_title))
        pubmeds_from_title = SraMetadata().fetch_pubmed_ids_from_term(study_title)
        if pubmeds_from_title:
            to_print['PubMed IDs from title'] = ','.join(pubmeds_from_title)

        logging.debug("Searching EuropePMC for title '{}'".format(study_title))
        # TODO: The search for 'Characterisation of a sponge microbiome using an
        # integrative genome-centric approach' gives poor results - better at
        # PubMed. However, searching for 'sponge microbiome using an integrative
        # genome-centric approach' does work. So maybe need to filter out common
        # words?
        citations_from_europe_pmc_title = SraMetadata().fetch_citations_from_query_title(study_title)
        # TODO: Account for papers without a DOI?
        dois = [c['doi'] for c in citations_from_europe_pmc_title]
        if len(dois) > 0:
            to_print['DOIs from EuropePMC title search'] = ','.join(dois)
        
        final_result.append(to_print)

        # Search by bioproject accession e.g. for PRJEB22302 / ERR2108709
        bioproject = m['bioproject']
        logging.debug("Searching EuropePMC for bioproject accession '{}'".format(bioproject))
        citations_from_europe_pmc_bioproject = SraMetadata().fetch_citations_from_query_bioproject(bioproject)
        dois = [c['doi'] for c in citations_from_europe_pmc_bioproject]
        if len(dois) > 0:
            to_print['DOIs from EuropePMC bioproject search'] = ','.join(dois)


    # Write out table as CSV
    final = pd.DataFrame(final_result)
    final.to_csv(sys.stdout, index=False)
