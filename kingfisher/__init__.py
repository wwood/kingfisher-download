from .version import __version__

import logging
import json
import os
import subprocess

import extern
from extern import ExternCalledProcessError

from .ena import EnaDownloader
from .location import Location, NcbiLocationJson
from .exception import DownloadMethodFailed

DEFAULT_ASPERA_SSH_KEY = 'linux'
DEFAULT_OUTPUT_FORMAT_POSSIBILITIES = ['fastq','fastq.gz']
DEFAULT_DOWNLOAD_THREADS = 1 # until aria2c is properly packaged in conda-forge (needs movement from bioconda)
DEFAULT_THREADS = 8

def download_and_extract(**kwargs):
    '''download an public sequence dataset and extract if necessary. kwargs
    here are largely the same as the arguments to the kingfisher executable.
    '''
    run_identifier = kwargs.pop('run_identifier')
    download_methods = kwargs.pop('download_methods')
    output_format_possibilities = kwargs.pop('output_format_possibilities',
        DEFAULT_OUTPUT_FORMAT_POSSIBILITIES)
    force = kwargs.pop('force', False)
    unsorted = kwargs.pop('unsorted', False)
    stdout = kwargs.pop('stdout', False)
    gcp_project = kwargs.pop('gcp_project', None)
    gcp_user_key_file = kwargs.pop('gcp_user_key_file', None)
    aws_user_key_id = kwargs.pop('aws_user_key_id', None)
    aws_user_key_secret = kwargs.pop('aws_user_key_secret', None)
    allow_paid = kwargs.pop('allow_paid', None)
    allow_paid_from_gcp = kwargs.pop('allow_paid_from_gcp', None)
    allow_paid_from_aws = kwargs.pop('allow_paid_from_aws', None)
    ascp_ssh_key = kwargs.pop('ascp_ssh_key', DEFAULT_ASPERA_SSH_KEY)
    ascp_args = kwargs.pop('ascp_args', '')
    download_threads = kwargs.pop('download_threads', DEFAULT_DOWNLOAD_THREADS)
    extraction_threads = kwargs.pop('extraction_threads', DEFAULT_THREADS)

    if len(kwargs) > 0:
        raise Exception("Unexpected arguments detected: %s" % kwargs)

    if allow_paid:
        allowable_sources = ['s3', 'gcp']
    else:
        allowable_sources = []
    if allow_paid_from_gcp:
        if 'gcp-cp' not in download_methods:
            logging.warning("Allowing download from requester-pays GCP buckets, "\
                "but gcp-cp is not specified download method, so --allow-paid-from-gcp has no effect")
        allowable_sources.append('gcp')
    if allow_paid_from_aws:
        if 'aws-cp' not in download_methods:
            logging.warning("Allowing download from requester-pays AWS buckets, "\
                "but aws-cp is not specified download method, so --allow-paid-from-aws has no effect")
        allowable_sources.append('s3')
    logging.debug("Allowing non-NCBI sources for download: {}".format(allowable_sources))

    if gcp_project and gcp_user_key_file:
        raise Exception("--gcp-project is incompatible with --gcp-user-key-file. The project specified in the key file will be used when gcp_project is not specified.")

    if stdout or unsorted:
        if not (stdout and unsorted and output_format_possibilities == ['fasta']):
            raise Exception("Currently --stdout and --unsorted must be specified together and with --output-format-possibilities fasta")

    output_files = []
    ncbi_locations = None

    # Checking for already existing files
    if stdout:
        skip_download_and_extraction, output_files = False, []
    else:
        skip_download_and_extraction, output_files = _check_for_existing_files(
            run_identifier, output_format_possibilities, force
        )

    downloaded_files = None
    if not skip_download_and_extraction:
        # Download phase
        worked = False
        for method in download_methods:
            logging.info("Attempting download method {} ..".format(method))
            if method == 'prefetch':
                try:
                    extern.run("prefetch -o {}.sra {}".format(
                        run_identifier, run_identifier))
                    downloaded_files = ['{}.sra'.format(run_identifier)]
                except ExternCalledProcessError as e:
                    logging.warning("Method {} failed: Error was: {}".format(method, e))
                
            elif method == 'aws-http':
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

                        try:
                            if download_threads > 1:
                                logging.info(
                                    "Downloading .SRA file from AWS Open Data Program HTTP link using aria2c ..")
                                cmd = "aria2c -x{} -o {}.sra '{}'".format(
                                    download_threads, run_identifier, odp_link)
                                subprocess.check_call(cmd, shell=True)
                            else:
                                logging.info(
                                    "Downloading .SRA file from AWS Open Data Program HTTP link using curl ..")
                                cmd = "curl -o {}.sra '{}'".format(run_identifier, odp_link)
                                subprocess.check_call(cmd, shell=True)
                            logging.info("Download finished")
                            downloaded_files = ['{}.sra'.format(run_identifier)]
                        except CalledProcessError as e:
                            logging.warning("Method {} failed when downloading from {}: Error was: {}".format(method, odp_link, e))
                else:
                    logging.warning("Method {} failed: No ODP URL could be found".format(method))

            elif method == 'aws-cp':
                if ncbi_locations is None:
                    ncbi_locations = Location.get_ncbi_locations(run_identifier)

                s3_locations = ncbi_locations.object_locations(
                    NcbiLocationJson.OBJECT_TYPE_SRA,
                    NcbiLocationJson.AWS_SERVICE,
                    'aws' in allowable_sources
                )

                # TODO: Sort so unpaid are first

                if len(s3_locations) > 0:
                    for s3_location in s3_locations:
                        logging.info("Found s3 link {}".format(s3_location.link()))

                        command = '{} {}.sra'.format(
                            s3_location.s3_command_prefix(run_identifier), run_identifier
                        )
                        if aws_user_key_id:
                            os.environ['AWS_ACCESS_KEY_ID'] = aws_user_key_id
                        if aws_user_key_id:
                            os.environ['AWS_SECRET_ACCESS_KEY'] = aws_user_key_secret
                        logging.info("Downloading from S3..")
                        try:
                            extern.run(command)
                            downloaded_files = ['{}.sra'.format(run_identifier)]
                        except ExternCalledProcessError as e:
                            logging.warning("Method {} failed: Error was: {}".format(method, e))
                else:
                    logging.warning("Method {} failed: No S3 location could be found".format(method))

            elif method == 'gcp-cp':
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
                                    command += ' cp {} {}.sra'.format(
                                        gs_path, run_identifier
                                    )
                                    logging.info("Downloading from GCP..")
                                    try:
                                        extern.run(command)
                                        downloaded_files = ['{}.sra'.format(run_identifier)]
                                    except ExternCalledProcessError as e:
                                        logging.warning("Method {} failed: Error was: {}".format(method, e))
                                except DownloadMethodFailed as e:
                                    logging.warning("Method {} failed, error was {}".format(
                                        method, e
                                    ))
                    else:
                        logging.warning("Method {} failed: No GCP location could be found".format(method))
                else:
                    logging.warning("Not using method gcp-cp as --allow-paid was not specified")

            elif method == 'ena-ascp':
                result = EnaDownloader().download_with_aspera(run_identifier, '.',
                    ascp_args=ascp_args,
                    ssh_key=ascp_ssh_key)
                if result is not False:
                    downloaded_files = result

            elif method == 'ena-ftp':
                result = EnaDownloader().download_with_curl(run_identifier, download_threads)
                if result is not False:
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
        if downloaded_files == ['{}.sra'.format(run_identifier)]:
            if 'sra' not in output_format_possibilities:
                sra_file = downloaded_files[0]
                output_files = extract(
                    sra_file = sra_file,
                    output_format_possibilities = output_format_possibilities,
                    unsorted = unsorted,
                    stdout = stdout,
                    threads = extraction_threads,
                )
                os.remove(sra_file)
            else:
                output_files.append("{}.sra".format(run_identifier))
        else:
            if unsorted or stdout:
                raise Exception("--unsorted and --stdout currently must be via download of a .sra format file, rather than a download from ENA. I imagine this will be fixed in future.")
            if 'fastq.gz' not in output_format_possibilities:
                for fq in ['x_1.fastq.gz','x_2.fastq.gz','x.fastq.gz']:
                    f = fq.replace('x',run_identifier)
                    if os.path.exists(f):
                        # Do the least work, currently we have FASTQ.gz
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

            else:
                output_files = downloaded_files

    logging.info("Output files: {}".format(', '.join(output_files)))

    
def extract(**kwargs):
    sra_file = kwargs.pop('sra_file')
    output_format_possibilities = kwargs.pop('output_format_possibilities',
        DEFAULT_OUTPUT_FORMAT_POSSIBILITIES)
    force = kwargs.pop('force', False)
    unsorted = kwargs.pop('unsorted', False)
    stdout = kwargs.pop('stdout', False)
    threads = kwargs.pop('threads',DEFAULT_THREADS)

    if len(kwargs) > 0:
        raise Exception("Unexpected arguments detected: %s" % kwargs)

    if stdout or unsorted:
        if not (stdout and unsorted and output_format_possibilities == ['fasta']):
            raise Exception("Currently --stdout and --unsorted must be specified together and with --output-format-possibilities fasta")

    run_identifier = os.path.basename(sra_file)
    if sra_file.endswith(".sra"):
        run_identifier = run_identifier[:-4]
    logging.debug("Using run identifier {}".format(run_identifier))

    # Checking for already existing files
    if stdout:
        skip_download_and_extraction, output_files = False, []
    else:
        skip_download_and_extraction, output_files = _check_for_existing_files(
            run_identifier, output_format_possibilities, force
        )
    
    if unsorted and stdout and 'fasta' in output_format_possibilities:
        logging.info("Extracting unsorted .sra file to STDOUT in FASTA format ..")
        cmd = "vdb-dump -f fasta {}".format(os.path.abspath(sra_file))
        logging.debug("Running command {}".format(cmd))
        try:
            subprocess.check_call(cmd, shell=True, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            #TODO: vdb-dump doesn't fail with non-zero status when
            #something is amiss. Fix by using NCBI API instead of
            #vdb-dump.
            raise Exception("Extraction of .sra to fasta format failed. Command run was '{}'. STDERR was '{}'".format(
                cmd, e.stderr
            ))
    else:
        if not skip_download_and_extraction:
            logging.info("Extracting .sra file with fasterq-dump ..")
            extern.run("fasterq-dump --threads {} {}".format(threads, os.path.abspath(sra_file)))

            if 'fastq' not in output_format_possibilities:
                for fq in ['x_1.fastq','x_2.fastq','x.fastq']:
                    f = fq.replace('x',run_identifier)
                    if os.path.exists(f):
                        # Do the least work, currently we have FASTQ.
                        if 'fasta' in output_format_possibilities:
                            logging.info("Converting {} to FASTA ..".format(f))
                            out_here = f.replace('.fastq','.fasta')
                            extern.run("awk '{{print \">\" substr($0,2);getline;print;getline;getline}}' {} >{}".format(
                                f, out_here
                            ))
                            os.remove(f)
                            output_files.append(out_here)
                        elif 'fasta.gz' in output_format_possibilities:
                            logging.info("Converting {} to FASTA and compressing with pigz ..".format(f))
                            out_here = f.replace('.fastq','.fasta.gz')
                            extern.run("awk '{{print \">\" substr($0,2);getline;print;getline;getline}}' {} |pigz >{}".format(
                                f, out_here
                            ))
                            os.remove(f)
                            output_files.append(out_here)
                        elif 'fastq.gz' in output_format_possibilities:
                            logging.info("Compressing {} with pigz ..".format(f))
                            extern.run("pigz {}".format(f))
                            output_files.append("{}.gz".format(f))
                        else:
                            raise Exception("Programming error")
            else:
                for fq in ['x_1.fastq','x_2.fastq','x.fastq']:
                    f = fq.replace('x',run_identifier)
                    if os.path.exists(f):
                        output_files.append(f)

    return output_files


def _check_for_existing_files(run_identifier, output_format_possibilities, force):
    skip_download_and_extraction = False
    output_files = []

    def maybe_skip_or_force(path, output_files, force):
        skip_download_and_extraction = False
        if os.path.exists(path):
            if force:
                logging.warn("Removing previous file {}".format(path))
                os.remove(path)
            else:
                skip_download_and_extraction = True
                output_files.append(path)
                logging.info(
                    "Skipping download/extraction of {} as an output file already appears to exist, as file {}".format(run_identifier, path))
        return skip_download_and_extraction, output_files

    for file_type in output_format_possibilities:
        if file_type == 'sra':
            path = "{}.{}".format(run_identifier, file_type)
            skip, output_files = maybe_skip_or_force(path, output_files, force)
            if skip: skip_download_and_extraction = True
        elif file_type == 'fastq':
            possibilities = ['x.fastq','x_1.fastq','x_2.fastq']
            for path in possibilities:
                skip, output_files = maybe_skip_or_force(path.replace('x',run_identifier), output_files, force)
                if skip: skip_download_and_extraction = True
        elif file_type == 'fastq.gz':
            possibilities = ['x.fastq.gz','x_1.fastq.gz','x_2.fastq.gz']
            for path in possibilities:
                skip, output_files = maybe_skip_or_force(path.replace('x',run_identifier), output_files, force)
                if skip: skip_download_and_extraction = True
        elif file_type == 'fasta':
            possibilities = ['x.fasta','x_1.fasta','x_2.fasta']
            for path in possibilities:
                skip, output_files = maybe_skip_or_force(path.replace('x',run_identifier), output_files, force)
                if skip: skip_download_and_extraction = True
        elif file_type == 'fasta.gz':
            possibilities = ['x.fasta.gz','x_1.fasta.gz','x_2.fasta.gz']
            for path in possibilities:
                skip, output_files = maybe_skip_or_force(path.replace('x',run_identifier), output_files, force)
                if skip: skip_download_and_extraction = True
        else:
            raise Exception("Programming error")

    return skip_download_and_extraction, output_files