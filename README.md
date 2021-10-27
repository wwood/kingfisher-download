<img src="images/kingfisher_logo.png" alt="Kingfisher logo" width="600"/>

- [Kingfisher](#kingfisher)
  - [Installation](#installation)
  - [Usage](#usage)
    - ['get' mode: Download and optionally convert sequence data](#get-mode-download-and-optionally-convert-sequence-data)
    - ['extract' mode: Convert sequence data from .sra format](#extract-mode-convert-sequence-data-from-sra-format)
    - ['annotate' mode: Get a table of metadata](#annotate-mode-get-a-table-of-metadata)
  - [Method details](#method-details)
  - [Near parity with ena-fast-download](#near-parity-with-ena-fast-download)
  - [FAQ](#faq)
    - [ascp: not found](#ascp-not-found)
    - [Failed to authenticate with ascp](#failed-to-authenticate-with-ascp)
    - [API rate limit exceeded](#api-rate-limit-exceeded)
  - [License](#license)

# Kingfisher

Kingfisher is a fast and flexible program for procurement of sequence files (and
their annotations) from public data sources, including the European Nucleotide
Archive (ENA), NCBI SRA, Amazon AWS and Google Cloud. It's input is one or more
"Run" accessions e.g. DRR001970, or a BioProject accessions e.g. PRJNA621514 or
SRP260223.

It attempts to download data from a series of sources, which it attempts in
order until one works. Then the downloaded data is converted to an output SRA /
FASTQ / FASTA / GZIP file format as required. Both download and extraction
phases are usually quicker than using the NCBI's SRA toolkit.

This software was originally known as `ena-fast-download`. Kingfisher implements
almost all of that tool's functionality, but also handles data sources other
than ENA. See the [Usage](#usage) section for the equivalent invocation.

## Installation

Kingfisher can be installed by installing its conda dependencies as follows. We
are working towards a proper PyPI/conda release, but are not there yet - our
apologies.

```
git clone https://github.com/wwood/kingfisher-download
cd kingfisher-download
conda env create -n kingfisher -f kingfisher.yml
conda activate kingfisher
cd bin
export PATH=$PWD:$PATH
kingfisher -h
```

Optionally, to use the `ena-ascp` method, an Aspera connect client is also required.
See https://www.ibm.com/aspera/connect/ or https://www.biostars.org/p/325010/

## Usage

For all modes, a full run-down of the functionality is available using the
`--full-help` flag e.g. `kingfisher get --full-help`.

### 'get' mode: Download and optionally convert sequence data

```
$ kingfisher get -r ERR1739691 -m ena-ascp aws-http prefetch
```
This will download `.fastq.gz` files of the run ERR1739691 from the ENA, or
failing that, downloads an .sra file from the Amazon AWA Open Data Program and
then converts to FASTQ, or failing that use NCBI prefetch to download and
convert that to FASTQ. Kingfisher will do the least effort to convert a
downloaded file into one of the formats specified in
`--output-format-possibilities` which is `fastq fastq.gz` by default.

Output files are put into the current working directory. There are many options
for output formats, different download methods etc. Check 'Method details' below
and the full help for more details.

### 'extract' mode: Convert sequence data from .sra format

```
$ kingfisher extract --sra ERR1739691.sra -t 16 -f fastq.gz
```
This will extract the file ERR1739691.sra using 16 threads and convert it to
fastq.gz file(s). Since this run has paired sequencing data in it, it will
create two files `ERR1739691_1.fastq.gz` and `ERR1739691_2.fastq.gz`.

### 'annotate' mode: Get a table of metadata

```
$ kingfisher annotate -r ERR1739691
Run        | SRAStudy  | Gbp   | LibraryStrategy | LibrarySelection | Model               | SampleName   | ScientificName
---------- | --------- | ----- | --------------- | ---------------- | ------------------- | ------------ | --------------
ERR1739691 | ERP017539 | 2.382 | WGS             | RANDOM           | Illumina HiSeq 2500 | SAMEA4497179 | metagenome    
```
A fuller set of information is available with `--all-columns` and the table can
also be output as comma- or tab- separated values using the `-f` flag.

## Method details

In `get` mode, there are several ways to procure the data:

|__method__ |__description__ |
| --- | --- |
|`ena-ascp`|Download `.fastq.gz` files from ENA using Aspera, which can then be further converted. This is the fastest method since no `fasterq-dump` is required.|
|`ena-ftp`|Download `.fastq.gz` files from ENA using `curl`, which can then be further converted. This is relatively fast since no `fasterq-dump` is required.|
|`prefetch`|Download .SRA file using NCBI's prefetch from sra-tools, which is then extracted with `fasterq-dump`.|
|`aws-http`|Download .SRA file from AWS Open Data Program using `aria2c` with multiple connection threads, which is then extracted with `fasterq-dump`.|
|`aws-cp`|Download .SRA file from AWS using `aws s3 cp`, which is then extracted with fasterq-dump. May require payment, probably not.|
|`gcp-cp`|Download .SRA file from Google Cloud `gsutil`, which is then extracted with fasterq-dump. Requires payment.|

The `ena-ascp` method of this tool was built based on the very helpful bio-stars
thread https://www.biostars.org/p/325010/ written by @ATpoint. To find run
identifiers to be used as input to kingfisher, you might find the [SRA
explorer](https://ewels.github.io/sra-explorer/) site helpful.

## Near parity with ena-fast-download

Ena-fast-download was the original name for this tool. To imitate that tool's
functionality:

```
kingfisher get -r ERR1739691 -m ena-ascp
```

## FAQ

### ascp: not found
If you see this error `/bin/sh: 1: ascp: not found` as below:
```
$ kingfisher get -r ERR3357550 -m ena-ascp
05/04/2021 05:13:45 AM INFO: Attempting download method ena-ascp ..
05/04/2021 05:13:45 AM INFO: Using aspera ssh key file: $HOME/.aspera/connect/etc/asperaweb_id_dsa.openssh
05/04/2021 05:13:45 AM INFO: Querying ENA for FTP paths for ERR3357550..
05/04/2021 05:13:49 AM INFO: Downloading 2 FTP read set(s): ftp.sra.ebi.ac.uk/vol1/fastq/ERR335/000/ERR3357550/ERR3357550_1.fastq.gz, ftp.sra.ebi.ac.uk/vol1/fastq/ERR335/000/ERR3357550/ERR3357550_2.fastq.gz
05/04/2021 05:13:49 AM INFO: Running command: ascp -T -l 300m -P33001  -i $HOME/.aspera/connect/etc/asperaweb_id_dsa.openssh era-fasp@fasp.sra.ebi.ac.uk:/vol1/fastq/ERR335/000/ERR3357550/ERR3357550_1.fastq.gz .
/bin/sh: 1: ascp: not found
05/04/2021 05:13:49 AM WARNING: Error downloading from ENA with ASCP: Command 'ascp -T -l 300m -P33001  -i $HOME/.aspera/connect/etc/asperaweb_id_dsa.openssh era-fasp@fasp.sra.ebi.ac.uk:/vol1/fastq/ERR335/000/ERR3357550/ERR3357550_1.fastq.gz .' returned non-zero exit status 127.
05/04/2021 05:13:49 AM WARNING: Method ena-ascp failed
Traceback (most recent call last):
  File "./bin/kingfisher", line 330, in <module>
    raise Exception("No more specified download methods, cannot continue")
Exception: No more specified download methods, cannot continue
```
then you have not installed the Aspera client correctly. See the [Installation](#installation) section of this document.

### Failed to authenticate with ascp
This error manifests like this
```
$ kingfisher get -r SRR5005053 -m ena-ascp
10/26/2021 11:24:21 PM INFO: Kingfisher v0.0.1-dev
10/26/2021 11:24:21 PM INFO: Attempting download method ena-ascp ..
10/26/2021 11:24:21 PM INFO: Using aspera ssh key file: $HOME/.aspera/connect/etc/asperaweb_id_dsa.openssh
10/26/2021 11:24:21 PM INFO: Querying ENA for FTP paths for SRR5005053..
10/26/2021 11:24:33 PM INFO: Downloading 2 FTP read set(s): ftp.sra.ebi.ac.uk/vol1/fastq/SRR500/003/SRR5005053/SRR5005053_1.fastq.gz, ftp.sra.ebi.ac.uk/vol1/fastq/SRR500/003/SRR5005053/SRR5005053_2.fastq.gz
10/26/2021 11:24:33 PM INFO: Running command: ascp -T -l 300m -P33001 -k 2 -i $HOME/.aspera/connect/etc/asperaweb_id_dsa.openssh era-fasp@fasp.sra.ebi.ac.uk:/vol1/fastq/SRR500/003/SRR5005053/SRR5005053_1.fastq.gz .
10/26/2021 11:24:45 PM WARNING: Error downloading from ENA with ASCP: Command ascp -T -l 300m -P33001 -k 2 -i $HOME/.aspera/connect/etc/asperaweb_id_dsa.openssh era-fasp@fasp.sra.ebi.ac.uk:/vol1/fastq/SRR500/003/SRR5005053/SRR5005053_1.fastq.gz . returned non-zero exit status 1.
STDERR was: b'ascp: failed to authenticate, exiting.\n'STDOUT was: b'\r\nSession Stop  (Error: failed to authenticate)\n'
10/26/2021 11:24:45 PM WARNING: Method ena-ascp failed
Traceback (most recent call last):
  File "/analysis2/software/kingfisher-download/bin/kingfisher", line 280, in <module>
    main()
  File "/analysis2/software/kingfisher-download/bin/kingfisher", line 232, in main
    kingfisher.download_and_extract(
  File "/analysis2/software/kingfisher-download/bin/../kingfisher/__init__.py", line 37, in download_and_extract
    download_and_extract_one_run(run, **kwargs)
  File "/analysis2/software/kingfisher-download/bin/../kingfisher/__init__.py", line 276, in download_and_extract_one_run
    raise Exception("No more specified download methods, cannot continue")
Exception: No more specified download methods, cannot continue
```
This could be caused by (1) your being on a network that interferes with ascp operation, or (2) a temporary downtime at ENA. You may try moving to a different network or following the instructions at the [Aspera support](https://www.ibm.com/support/pages/error-code-19-failed-authenticate) or checking the [log files](https://www.ibm.com/support/pages/node/747513) to see if that helps diagnose the error.

### API rate limit exceeded
Using `kingfisher annotate` repeatedly and in parallel can mean that the default
allowable rate of requests (3 per second) is exceeded. To get around this error,
you can generate an [NCBI API
key](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/)
and then set the environment variable `NCBI_API_KEY` before running kingfisher.
This key will then be used in all requests.

## License

Copyright Ben Woodcroft 2019-2021. Licensed under GPL3+. See LICENSE.txt.
