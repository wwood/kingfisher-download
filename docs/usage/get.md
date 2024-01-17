---
title: Kingfisher get
---
# kingfisher get

# DESCRIPTION

Download and extract sequence data from SRA or ENA

# OPTIONS

# COMMON OPTIONS

**-r**, **\--run-identifiers** *RUN_IDENTIFIERS* [*RUN_IDENTIFIERS* \...]

  Run number(s) to download/extract e.g. ERR1739691

**\--run-identifiers-list** *RUN_IDENTIFIERS_LIST*

  Text file containing a newline-separated list of run identifiers
    i.e. a 1 column CSV file.

**-p**, **\--bioprojects** *BIOPROJECTS* [*BIOPROJECTS* \...]

  BioProject IDs number(s) to download/extract from e.g. PRJNA621514
    or SRP260223

**-m**, **\--download-methods** {aws-http,prefetch,aws-cp,gcp-cp,ena-ascp,ena-ftp} [{aws-http,prefetch,aws-cp,gcp-cp,ena-ascp,ena-ftp} \...]

  How to download .sra file. If multiple are specified, each is tried
    in turn until one works [required].

| Method   | Description                                                                                                                                        |
|:---------|:---------------------------------------------------------------------------------------------------------------------------------------------------|
| ena-ascp | Download .fastq.gz files from ENA using Aspera, which can then be further converted. This is the fastest method since no fasterq-dump is required. |
| ena-ftp  | Download .fastq.gz files from ENA using curl, which can then be further converted. This is relatively fast since no fasterq-dump is required.      |
| prefetch | Download .SRA file using NCBI prefetch from sra-tools, which is then extracted with fasterq-dump.                                                  |
| aws-http | Download .SRA file from AWS Open Data Program using \`aria2c\` with multiple connection threads, which is then extracted with \`fasterq-dump\`.    |
| aws-cp   | Download .SRA file from AWS using aws s3 cp, which is then extracted with fasterq-dump. Does not usually require payment or an AWS account.        |
| gcp-cp   | Download .SRA file from Google Cloud gsutil, which is then extracted with fasterq-dump. Requires payment and a Google Cloud account.               |

**\--output-directory** *OUTPUT_DIRECTORY*

  Output directory to write to [default: current working directory]

# FURTHER DOWNLOAD OPTIONS

**\--download-threads** *DOWNLOAD_THREADS*

  Number of connection threads to use when downloading data. When \>1
    aria2 is used rather than curl [default: 8]

**\--hide-download-progress**

  Do not show progressbar during download [default: unset i.e. show
    progress]

**\--ascp-ssh-key** *ASCP_SSH_KEY*

  a path to the openssh key to used for aspera (i.e. the -i flag of
    ascp) [default: Use the one bundled with Kingfisher]

**\--ascp-args** *ASCP_ARGS*

  extra arguments to pass to ascp e.g. \'-k 2\' to resume with a
    sparse file checksum [default: \'-k 2\']

**\--allow-paid**

  Allow downloading from retriever-pays s3 and GCP buckets [default:
    Do not]

**\--allow-paid-from-aws**

  Allow downloading from retriever-pays AWS buckets [default: Do
    not]

**\--aws-user-key-id** *AWS_USER_KEY_ID*

  Downloading from AWS requester pays buckets requires a key ID and
    secret key [default: not used]

**\--aws-user-key-secret** *AWS_USER_KEY_SECRET*

  Downloading from AWS requester pays buckets requires a key ID and
    secret key [default: not used]

**\--guess-aws-location**

  Instead of using the NCBI location API, guess the address of the
    file in AWS [default: not used]

**\--allow-paid-from-gcp**

  Allow downloading from retriever-pays GCP buckets [default: Do
    not]

**\--gcp-project** *GCP_PROJECT*

  Downloading from Google Cloud buckets require a Google project to
    charge (they are requester-pays) e.g. \'my-project\'. This can
    alternately be set beforehand using \'gcloud config set project
    PROJECT_ID\' [default: value of \`gcloud config get-value project\`
    command]

**\--gcp-user-key-file** *GCP_USER_KEY_FILE*

  Downloading from Google Cloud buckets requires a Google user to be
    setup. Use this option to specify a JSON-formatted service account
    key, as per
    https://cloud.google.com/iam/docs/creating-managing-service-account-keys
    [default: not used]

**\--prefetch-max-size** *PREFETCH_MAX_SIZE*

  Downloading with prefetch has a default limit of 20G file size.
    Kingfisher disables this. Use this option to reinstate this file
    size limit e.g. \--prefetch-max-size \"1G\" for a 1 GB limit
    [default: not used]

**\--check-md5sums**

  Check md5sums of downloaded files. This is only implemented for
    ena-ftp, ena-ascp and aws-http download methods. The prefetch,
    aws-cp and gcp-cp methods calculate checksums as part of the
    download process. [default: not used]

# FURTHER EXTRACTION OPTIONS

**-f**, **\--output-format-possibilities** {sra,fastq,fastq.gz,fasta,fasta.gz} [{sra,fastq,fastq.gz,fasta,fasta.gz} \...]

  Allowable output formats. If more than one is specified, downloaded
    data will processed as little as possible [default: \"fastq
    fastq.gz\"]

**\--force**

  Re-download / extract files even if they already exist [default: Do
    not].

**\--unsorted**

  Output the sequences in arbitrary order, usually the order that they
    appear in the .sra file. Even pairs of reads may be in the usual
    order, but it is possible to tell which pair is which, and which is
    a forward and which is a reverse read from the name [default: Do
    not].

Currently requires download from NCBI rather than ENA.

**\--stdout**

  Output sequences to STDOUT. Currently requires \--unsorted
    [default: Do not].

**-t**, **\--extraction-threads** *EXTRACTION_THREADS*

  Number of threads to use when extracting .sra files. Ignored when
    \--unsorted is specified. [default: 8]

# OTHER GENERAL OPTIONS

**\--debug**

  output debug information

**\--version**

  output version information and quit

**\--quiet**

  only output errors

**\--full-help**

  print longer help message

**\--full-help-roff**

  print longer help message in ROFF (manpage) format

# AUTHOR

>     Ben J. Woodcroft, Centre for Microbiome Research, School of Biomedical Sciences, Faculty of Health, Queensland University of Technology <benjwoodcroft near gmail.com>

# EXAMPLES

Download .fastq.gz files of the run ERR1739691 from the ENA, or failing that, download an .sra file from the Amazon AWA Open Data Program and then convert to FASTQ (not FASTQ.GZ), or failing that use NCBI prefetch to download and convert that to FASTQ. Output files are put into the current working directory.

  **\$ kingfisher get -r ERR1739691 -m ena-ascp aws-http prefetch**

Download a .sra from GCP using a service account key with \"gcp cp\". Payment is required.

  **\$ kingfisher get -r ERR1739691 -m gcp-cp -f sra
    \--gcp-user-key-file sa-private-key.json \--allow-paid**

Download a .sra from the free AWS open data program using 8 threads for download and extraction, coverting to FASTA.

  **\$ kingfisher get -r ERR1739691 -m aws-http -f fasta
    \--download-threads 8**
