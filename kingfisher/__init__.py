from .version import __version__

import logging
import json
import os
import subprocess
import sys
import gzip

import extern
from extern import ExternCalledProcessError

from .ena import EnaDownloader
from .location import Location, NcbiLocationJson
from .exception import DownloadMethodFailed
from .sra_metadata import *
from .md5sum import MD5

DEFAULT_ASPERA_SSH_KEY = 'linux'
DEFAULT_OUTPUT_FORMAT_POSSIBILITIES = ['fastq','fastq.gz']
DEFAULT_THREADS = 8
DEFAULT_DOWNLOAD_THREADS = DEFAULT_THREADS
DEFAULT_ASCP_ARGS = '-k 2'

def download_and_extract(**kwargs):
    '''download an public sequence dataset and extract if necessary. kwargs
    here are largely the same as the arguments to the kingfisher executable.
    '''
    run_identifiers = kwargs.pop('run_identifiers')
    run_identifiers_file = kwargs.pop('run_identifiers_file')
    bioproject_accession = kwargs.pop('bioproject_accession')
    num_inputs = 0
    if run_identifiers is not None: num_inputs += 1
    if run_identifiers_file is not None: num_inputs += 1
    if bioproject_accession is not None: num_inputs += 1
    if num_inputs != 1:
        raise Exception("Must specify exactly one input type: --run-identifiers, --bioproject_accession or --run-identifiers-list")

    if bioproject_accession is not None:
        run_identifiers = SraMetadata().fetch_runs_from_bioproject(bioproject_accession)
        logging.debug("Found {} run(s) to annotate".format(len(run_identifiers)))
    if run_identifiers_file is not None:
        with open(run_identifiers_file) as f:
            run_identifiers = list([r.strip() for r in f.readlines()])

    for run in run_identifiers:
        download_and_extract_one_run(run, **kwargs)

def download_and_extract_one_run(run_identifier, **kwargs):
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
    guess_aws_location = kwargs.pop('guess_aws_location', False)
    ascp_ssh_key = kwargs.pop('ascp_ssh_key', DEFAULT_ASPERA_SSH_KEY)
    ascp_args = kwargs.pop('ascp_args', DEFAULT_ASCP_ARGS)
    download_threads = kwargs.pop('download_threads', DEFAULT_DOWNLOAD_THREADS)
    extraction_threads = kwargs.pop('extraction_threads', DEFAULT_THREADS)
    hide_download_progress = kwargs.pop('hide_download_progress', False)
    prefetch_max_size = kwargs.pop('prefetch_max_size',None)
    check_md5sums = kwargs.pop('check_md5sums', False)
    

    if len(kwargs) > 0:
        raise Exception("Unexpected arguments detected: %s" % kwargs)

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

    if stdout and not unsorted:
        raise Exception("Currently --stdout must be used with --unsorted")

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
            logging.info("Attempting download method {} for run {} ..".format(method, run_identifier))
            if method == 'prefetch':
                output_path = '{}.sra'.format(run_identifier)
                try:
                    if prefetch_max_size is None:
                        prefetch_max_size_argument = '--max-size 0G'
                    else:
                        prefetch_max_size_argument = '--max-size {}'.format(prefetch_max_size)
                    extern.run("prefetch {} -o {} {}".format(
                        prefetch_max_size_argument, output_path, run_identifier))
                    downloaded_files = [output_path]
                except ExternCalledProcessError as e:
                    logging.warning("Method {} failed: Error was: {}".format(method, e))
                    if os.path.exists(output_path):
                        logging.info("Removing file {} because download failed ..".format(output_path))
                        os.remove(f)
                
            elif method == 'aws-http':
                def download_from_aws(odp_link, run_identifier, download_threads, method):
                    output_path = '{}.sra'.format(run_identifier)
                    try:
                        if download_threads > 1:
                            logging.info(
                                "Downloading .SRA file from AWS Open Data Program HTTP link using aria2c ..")
                            verbosity_flag = '--quiet' if hide_download_progress else ''
                            # Redirect aria2c stdout to stderr so all logging of kingfisher is on stderr
                            cmd = "aria2c {} -x{} -o {} '{}' 1>&2".format(
                                verbosity_flag, download_threads, output_path, odp_link)
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
                            os.remove(f)
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
                output_path = '{}.sra'.format(run_identifier)

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
                                os.remove(f)
                else:
                    logging.warning("Method {} failed: No S3 location could be found".format(method))
                    if os.path.exists(output_path):
                        logging.info("Removing file {} because download failed ..".format(output_path))
                        os.remove(f)

            elif method == 'gcp-cp':
                output_path = '{}.sra'.format(run_identifier)
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
                                        os.remove(f)
                    else:
                        logging.warning("Method {} failed: No GCP location could be found".format(method))
                else:
                    logging.warning("Not using method gcp-cp as --allow-paid was not specified")

            elif method == 'ena-ascp':
                result = EnaDownloader().download_with_aspera(run_identifier, '.',
                    ascp_args=ascp_args,
                    ssh_key=ascp_ssh_key,
                    check_md5sums=check_md5sums)
                if result is not False:
                    downloaded_files = result

            elif method == 'ena-ftp':
                result = EnaDownloader().download_with_curl(
                    run_identifier,
                    download_threads,
                    check_md5sums=check_md5sums)
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
            if stdout:
                raise Exception("--stdout currently must be via download of a .sra format file, rather than a download from ENA. I imagine this will be fixed in future.")
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

    if stdout and not unsorted:
        raise Exception("Currently --stdout must be used with --unsorted")

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
    
    if unsorted and stdout:
        format = output_format_possibilities[0]
        if format == 'fasta':
            logging.info("Extracting unsorted .sra file to STDOUT in FASTA format ..")
            cmd = "sracat {}".format(os.path.abspath(sra_file))
        elif format == 'fasta.gz':
            logging.info("Extracting unsorted .sra file to STDOUT in FASTA.GZ format ..")
            cmd = "sracat {} |pigz -p {} -c".format(os.path.abspath(sra_file), threads)
        elif format == 'fastq':
            logging.info("Extracting unsorted .sra file to STDOUT in FASTQ format ..")
            cmd = "sracat --qual {}".format(os.path.abspath(sra_file))
        elif format == 'fastq.gz':
            logging.info("Extracting unsorted .sra file to STDOUT in FASTQ.GZ format ..")
            cmd = "sracat --qual {} |pigz -p {} -c".format(os.path.abspath(sra_file), threads)
        else:
            raise Exception("Cannot extract with --stdout --unsorted format {}".format(format))
        logging.debug("Running command {}".format(cmd))
        try:
            subprocess.check_call(cmd, shell=True, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            raise Exception("Extraction of .sra to fasta format failed. Command run was '{}'. STDERR was '{}'".format(
                cmd, e.stderr
            ))
            
    elif unsorted and not stdout:
        def run_command(cmd):
            logging.debug("Running command {}".format(cmd))
            try:
                subprocess.check_call(cmd, shell=True, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                raise Exception(f"Extraction of .sra to format unsorted {format} failed. Command run was '{cmd}'. STDERR was '{e.stderr}'")

        # By default, we want separate outputs for forward and reverse.
        format = output_format_possibilities[0]
        if format == 'fasta':
            logging.info("Extracting .sra file to file(s) in unsorted FASTA format ..")
            cmd = f"sracat -o {run_identifier} {os.path.abspath(sra_file)}"
            run_command(cmd)
            for name in ['x_1.fna','x_2.fna','x.fna']:
                f = name.replace('x',run_identifier)
                if os.path.exists(f):
                    new_name = f.replace('.fna','.fasta')
                    os.rename(f, new_name)
                    output_files.append(new_name)
        elif format == 'fasta.gz':
            logging.info("Extracting .sra file to file(s) in unsorted FASTA.GZ format ..")
            cmd = f"sracat -o {run_identifier} {os.path.abspath(sra_file)}"

            # Make FIFOs so that we can use pigz instead of the slower built-in sracat -z.
            logging.debug("Creating FIFOs ..")
            os.mkfifo(f'{run_identifier}_1.fna')
            os.mkfifo(f'{run_identifier}_2.fna')
            os.mkfifo(f'{run_identifier}.fna')
            # Spawn pigz to read FIFOs.
            def spawn_pigz_it(in_name, out_name, threads):
                return subprocess.Popen(['bash','-c',f'pigz -c -p {threads} {in_name} > {out_name}'])
            pigz_commands = []
            for name in ['x_1.fna','x_2.fna','x.fna']:
                f = name.replace('x',run_identifier)
                output = f.replace('.fna','.fasta.gz')
                pigz_commands.append([f, output, spawn_pigz_it(f'{f}', f"{output}", threads)])
            run_command(cmd)
            for (fifo, output, c) in pigz_commands:
                logging.debug(f"Waiting for pigz command {c.args} ..")

                # If sracat doesn't write to a fifo, then the pigz reading it
                # never finishes. So run another echo on top so at least 1 EOF
                # arrives to terminate the pigz process.
                logging.debug("Running echo to make sure at least one EOF arrived on the pipe")
                subprocess.Popen(['bash','-c',f'cat {fifo} > /dev/null'])
                extern.run(f'echo -n >> {fifo}')
                
                ret = c.wait()
                if ret != 0:
                    raise subprocess.SubprocessError(f"Command {c.args} returned with non-zero exitstatus {ret}")
                logging.debug("Process finished")
                os.remove(fifo)

                # Open the gzip file. If there is anything inside, keep it,
                # otherwise remove it as sracat never read it.
                remove_it = False
                with gzip.open(output) as f:
                    some = f.read(10)
                    if len(some) == 0:
                        logging.debug(f"Compressed file {output} is empty, removing")
                        remove_it = True
                if remove_it:
                    os.remove(output)

            for name in ['x_1.fasta.gz','x_2.fasta.gz','x.fasta.gz']:
                f = name.replace('x',run_identifier)
                if os.path.exists(f):
                    output_files.append(f)
        elif format == 'fastq':
            logging.info("Extracting .sra file to file(s) in unsorted FASTQ format ..")
            cmd = f"sracat --qual -o {run_identifier} {os.path.abspath(sra_file)}"
            run_command(cmd)
            for name in ['x_1.fastq','x_2.fastq','x.fastq']:
                f = name.replace('x',run_identifier)
                if os.path.exists(f):
                    output_files.append(f)
        elif format == 'fastq.gz':
            logging.info("Extracting .sra file to file(s) in unsorted FASTQ.GZ format ..")
            cmd = f"sracat -z --qual -o {run_identifier} {os.path.abspath(sra_file)}"
            run_command(cmd)
            for name in ['x_1.fastq.gz','x_2.fastq.gz','x.fastq.gz']:
                f = name.replace('x',run_identifier)
                if os.path.exists(f):
                    output_files.append(f)
        else:
            raise Exception("Cannot extract with --unsorted format {}".format(format))

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
                            extern.run("awk '{{print \">\" substr($0,2);getline;print;getline;getline}}' {} |pigz -p {} >{}".format(
                                f, threads, out_here
                            ))
                            os.remove(f)
                            output_files.append(out_here)
                        elif 'fastq.gz' in output_format_possibilities:
                            logging.info("Compressing {} with pigz ..".format(f))
                            extern.run("pigz -p {} {}".format(threads, f))
                            output_files.append("{}.gz".format(f))
                        else:
                            raise Exception("Programming error")
            else:
                for fq in ['x_1.fastq','x_2.fastq','x.fastq']:
                    f = fq.replace('x',run_identifier)
                    if os.path.exists(f):
                        output_files.append(f)

    return output_files

def annotate(**kwargs):
    run_identifiers = kwargs.pop('run_identifiers')
    run_identifiers_file = kwargs.pop('run_identifiers_file')
    bioproject_accession = kwargs.pop('bioproject_accession')
    output_file = kwargs.pop('output_file')
    output_format = kwargs.pop('output_format')
    all_columns = kwargs.pop('all_columns')

    num_inputs = 0
    if run_identifiers is not None: num_inputs += 1
    if run_identifiers_file is not None: num_inputs += 1
    if bioproject_accession is not None: num_inputs += 1
    if num_inputs != 1:
        raise Exception("Must specify exactly one input type: --run-identifiers, --bioproject_accession or --run-identifiers-list")
    
    if bioproject_accession is not None:
        run_identifiers = SraMetadata().fetch_runs_from_bioproject(bioproject_accession)
        logging.debug("Found {} run(s) to annotate".format(len(run_identifiers)))
    if run_identifiers_file is not None:
        with open(run_identifiers_file) as f:
            run_identifiers = list([r.strip() for r in f.readlines()])
        
    if len(kwargs) > 0:
        raise Exception("Unexpected arguments detected: %s" % kwargs)

    metadata = SraMetadata().efetch_sra_from_accessions(run_identifiers)
    if metadata is None:
        logging.error("No runs to annotate")
        sys.exit(1)
    _output_formatted_metadata(metadata, output_file, output_format, all_columns)


def _output_formatted_metadata(metadata, output_file, output_format, all_columns):
    # default_columns = ['Run','SRAStudy','Gbp','LibraryStrategy','LibrarySelection','Model','SampleName','ScientificName']
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
        metadata_sorted = pd.concat(
            [
                metadata_sorted,
                pd.DataFrame({'Gbp': [
                    round(bases/1e9, 3) if bases is not None else None for bases in metadata_sorted[BASES_KEY]]})
            ],
            axis=1)
        if all_columns:
            # Re-order columns to be consistent with human format output
            column_order = default_columns + [c for c in metadata_sorted.columns if c not in default_columns]
            return metadata_sorted[column_order]
        else:
            metadata_sorted = metadata_sorted[default_columns]
            return metadata_sorted

    output_path = sys.stdout if output_file is None else output_file

    if output_format == 'human':
        to_print = []
        for value in metadata[RUN_ACCESSION_KEY]:
            to_print.append({RUN_ACCESSION_KEY: value})
        for i, value in enumerate(metadata[STUDY_ACCESSION_KEY]):
            to_print[i][STUDY_ACCESSION_KEY] = value
        for i, value in enumerate(metadata[BASES_KEY]):
            to_print[i]['Gbp'] = "%.3f" % (value/1e9) if value is not None else None
        # for column in ['LibraryStrategy','LibrarySelection','Model','SampleName','ScientificName']:
        for column in ['library_strategy','library_selection','model',SAMPLE_NAME_KEY,'taxon_name']:
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