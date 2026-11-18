Welcome.

Kingfisher is a fast and flexible program for procurement of sequence files (and
their metadata annotations) from public data sources, including the European Nucleotide
Archive (ENA), NCBI SRA, Amazon AWS and Google Cloud. It's input is one or more
"Run" accessions e.g. DRR001970, or a BioProject accessions e.g. PRJNA621514 or
SRP260223.

It has two main modes - the
[get](https://wwood.github.io/kingfisher-download/usage/get) mode downloads
sequence data and the
[annotate](https://wwood.github.io/kingfisher-download/usage/annotate) mode
downloads metadata.

In the `get` subcommand, kingfisher downloads data from a series of redundant
sources, which it attempts in order until one works. The downloaded data is then
converted to an output SRA / FASTQ / FASTA / GZIP file format as required. Both
download and extraction phases can be quicker than using the NCBI's SRA toolkit.
In particular, downloading from ENA means that FASTQ files are downloaded
directly, so there is no need for the extraction step.

If you are looking to download GenBank/RefSeq data instead, then you might try [NCBI datasets](https://www.ncbi.nlm.nih.gov/datasets) or [ncbi-acc-download](https://github.com/kblin/ncbi-acc-download).

In the `annotation` subcommand, metadata about the run(s) is downloaded from NCBI and output in one of several formats e.g. human-readable, CSV, TSV, JSON, feather or parquet. By default, a small amount of metadata is downloaded - more details can be output using the `--all-columns` flag.

## Installation

### Installation through bioconda

Kingfisher can be installed in the usual way through conda/bioconda e.g.

```
conda create -n kingfisher -c conda-forge -c bioconda kingfisher
conda activate kingfisher
kingfisher get -r SRR12118866 -m ena-ftp
```

Optionally, to use the `ena-ascp` method, an Aspera connect client is also required. For this, you can run `ascli config ascp install` after installing kingfisher, which will download and install the Aspera connect client for you. Alternatively, you can install the Aspera connect client yourself.

### Installation through DockerHub

A docker image generated from the conda package is available on DockerHub. After installing Docker, run the following, replacing `[RELEASE_TAG]` with a tag from [https://hub.docker.com/r/wwood/kingfisher/tags](https://hub.docker.com/r/wwood/kingfisher/tags):
```
docker pull wwood/kingfisher:[RELEASE_TAG]
```
To download data into the current directory:
```
docker run -v `pwd`:/data wwood/kingfisher:[RELEASE_TAG] get -r SRR12118866 -m ena-ftp
```

### Conda-based development environment

Kingfisher can be installed through [pixi](https://pixi.sh/), to setup a development environment, as below:

```
git clone https://github.com/wwood/kingfisher-download
cd kingfisher-download
pixi run ascli config ascp install # optional, to install ascp for the ena-ascp method
pixi run kingfisher -h
```

[currently outdated]: @MakeTheBrainHappy implemented an example installation (and usage) guide in [Google Colaboratory](https://colab.research.google.com/drive/1k3RC-WbVAAl6h8yXtfEhwqCAvCMHspzz?usp=sharing) and [Jupyter Notebook](https://github.com/MakeTheBrainHappy/kingfisher-cloud).

## Usage

For all modes, a full run-down of the functionality is available using the
`--full-help` flag e.g. `kingfisher get --full-help` or `kingfisher annotate --full-help`.

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
run        | bioproject | Gbp   | library_strategy | library_selection | model               | sample_name | taxon_name
---------- | ---------- | ----- | ---------------- | ----------------- | ------------------- | ----------- | ----------
ERR1739691 | PRJEB15706 | 2.382 | WGS              | RANDOM            | Illumina HiSeq 2500 | MM1_1       | metagenome
```
A fuller set of information is available with `--all-columns` and the table can
also be output in CSV, TSV, JSON, feather or parquet formats using the `-f` flag.

## Method details

In `get` mode, there are several ways to procure the data:

|__method__ |__description__ |
| --- | --- |
|`ena-ascp`|Download `.fastq.gz` files from ENA using Aspera, which can then be further converted. This can be the fastest method since no `sracat-rs` is required.|
|`ena-ftp`|Download `.fastq.gz` files from ENA using `curl`, which can then be further converted. This is relatively fast since no `sracat-rs` is required.|
|`prefetch`|Download .SRA file using NCBI's prefetch from sra-tools, which is then extracted with `sracat-rs`.|
|`aws-http`|Download .SRA file from AWS Open Data Program using `aria2c` with multiple connection threads, which is then extracted with `sracat-rs`.|
|`aws-cp`|Download .SRA file from AWS using `aws s3 cp`, which is then extracted with sracat-rs. Does not usually require payment or an AWS account.|
|`gcp-cp`|Download .SRA file from Google Cloud `gsutil`, which is then extracted with sracat-rs. Requires payment and a Google Cloud account.|

The `ena-ascp` method of this tool was built based on the very helpful bio-stars
[thread](https://www.biostars.org/p/325010/) written by @ATpoint. To find run
identifiers to be used as input to kingfisher, you might find the [SRA
explorer](https://ewels.github.io/sra-explorer/) site helpful.

### Read layouts and technical reads

`--include-technical` preserves sample indexes, barcodes, and other
assay-specific technical reads during SRA extraction. `--read-layout` optionally
assigns user-selected semantic filenames after extraction and format conversion.
Kingfisher does not infer biological read roles from stream count.

| Layout | Streams | Output |
| --- | ---: | --- |
| `sra` | any | `_1`, `_2`, ... |
| `illumina-se` | 1 | `R1` |
| `illumina-pe` | 2 | `R1`, `R2` |
| `illumina-se-single-index` | 2 | `R1`, `I1` |
| `illumina-se-dual-index` | 3 | `R1`, `I1`, `I2` |
| `illumina-pe-single-index` | 3 | `R1`, `I1`, `R2` |
| `illumina-pe-dual-index` | 4 | `R1`, `I1`, `I2`, `R2` |
| `10x-gex`, `10x-vdj`, `10x-spatial` | 2/3/4 | See mappings below |
| `10x-atac` | 4 | `R1`, `I1`, `I2`, `R2` |
| `10x-atac-bcl` | 4 | `R1`, `I1`, `R2`, `R3` |
| `parse-wt-single-index` | 3 | `R1`, `I1`, `R2` |
| `parse-wt-dual-index` | 4 | `R1`, `I1`, `I2`, `R2` |
| `custom` | any | User-supplied names |

The flexible `10x-gex`, `10x-vdj`, and `10x-spatial` layouts map two streams to
`R1,R2`, three streams to `R1,I1,R2`, and four streams to `R1,I1,I2,R2`.
These mappings must match the read order in the deposited archive.

For a paired-end library with two index reads, use:

```bash
kingfisher get \
    -r SRRXXXX \
    -m aws-http prefetch \
    -f fastq.gz \
    --include-technical \
    --read-layout illumina-pe-dual-index
```

To produce filenames in the Illumina style for a 10x gene-expression library, use:

```bash
kingfisher get \
    -r SRRXXXX \
    -m aws-http prefetch \
    -f fastq.gz \
    --include-technical \
    --read-layout 10x-gex \
    --read-name-style illumina
```

Four streams become `SRRXXXX_S1_R1_001.fastq.gz`,
`SRRXXXX_S1_I1_001.fastq.gz`, `SRRXXXX_S1_I2_001.fastq.gz`, and
`SRRXXXX_S1_R2_001.fastq.gz`. `10x-atac-bcl` changes filename semantics only:
its third/fourth streams become `R2`/`R3`; sequence content remains untouched.

For a Parse whole-transcriptome library deposited with two index reads, use:

```bash
kingfisher get -r SRRXXXX -m prefetch -f fastq.gz \
    --include-technical --read-layout parse-wt-dual-index
```

To assign custom names to the streams in a local SRA archive, use:

```bash
kingfisher extract --sra SRRXXXX.sra -f fastq.gz \
    --include-technical --read-layout custom \
    --read-names R1,BC1,BC2,R2
```

The default, `--read-layout sra`, retains the extractor's filenames in SRA read
order. `--sample-name` replaces the run accession in semantic filenames. `--read-name-style simple`
produces `<sample>_<read>`; `illumina` produces
`<sample>_S1_<read>_001` without adding a lane number.

Layouts containing index reads, plus flexible `10x-gex`, `10x-vdj`, and
`10x-spatial`, require `--include-technical` for SRA extraction. Stream count is
validated after extraction; mismatches fail before any rename.

#### Download-method compatibility

Technical-read preservation and non-default read layouts require extraction from
an SRA archive. For `get`, use only `prefetch`, `aws-http`, `aws-cp`, or `gcp-cp`,
including every fallback method. ENA and NGDC methods download FASTQ files
directly and do not guarantee the original SRA stream order or technical reads.
Kingfisher rejects these combinations before metadata lookup or downloading.
Alternatively, use `extract` with a local `.sra` file.

Select FASTQ or FASTA output. If `sra` appears anywhere in
`--output-format-possibilities`, Kingfisher retains the archive without extracting
it, so technical-read and non-default layout options are rejected. These options
also cannot be combined with `--stdout`, because they require separate read files.
`--read-name-style` and `--sample-name` require a non-default `--read-layout`.

Read layouts rename files only. Confirm the deposited read order against the
library protocol before selecting a layout, especially a custom layout. Technical
reads that were not deposited in SRA cannot be recovered. Extraction fails if the
number of streams does not match the selected layout; existing output files are
not overwritten unless `--force` is supplied.

#### Real-data regression tests

Run the read-layout tests with the development environment:

```bash
pixi run -e dev pytest test/test_read_layouts.py test/test_technical_reads.py \
    test/test_read_option_compatibility.py test/test_read_layouts_real_sra.py
```

These tests extract actual SRA files using `fasterq-dump` and check FASTQ content,
compression, stream counts, filenames, and repeat extraction. They use the existing
small run `DRR002803` to verify three technical streams and one biological stream,
and a bounded fixture derived from the first 100 spots of `SRR10612247`, from
[GSE141701](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE141701),
to verify paired 10x gene-expression reads. The latter has two biological streams
of 26 and 98 bases; its deposited SRA data do not contain separate index streams.
The complete run is large, so routine tests use a repacked 87 kB SRA fixture and
require no network access. See `test/data/README.md` for provenance and regeneration
commands. Synthetic unit tests remain useful for layouts and error conditions
that these deposited runs do not cover.

To test complete downloads of the 148 kB run through both `aws-http` and
`prefetch`, run the additional integration tests. These require network access:

```bash
pixi run -e dev pytest test/test_read_layouts_download.py
```

## Near parity with ena-fast-download

Ena-fast-download was the original name for this tool. To imitate that tool's
functionality:

```
kingfisher get -r ERR1739691 -m ena-ascp
```

## FAQ

### ascp: not found
If you see an error like
```
Exception: ascp not found in PATH or at /home/woodcrob/.aspera/ascli/sdk/ascp
```

then you have not installed the Aspera client correctly. See the installation section of this document.

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
This could be caused by (1) your being on a network that interferes with ascp operation, or (2) a temporary downtime at ENA. You may try moving to a different network or following the instructions at the [Aspera support](https://www.ibm.com/support/pages/error-code-19-failed-authenticate) or checking the [log files](https://www.ibm.com/support/pages/node/747513) to see if that helps diagnose the error. See [this issue](https://github.com/wwood/kingfisher-download/issues/9#issuecomment-952576784) for more information about a specific WLAN that was causing an issue.

### API rate limit exceeded
Using `kingfisher annotate` repeatedly and in parallel can mean that the default
allowable rate of requests (3 per second) is exceeded. To get around this error,
you can generate an [NCBI API
key](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/)
and then set the environment variable `NCBI_API_KEY` before running kingfisher.
This key will then be used in all requests.

## Citation

Woodcroft, B. J., Cunningham, M., Gans, J. D., Bolduc, B. B., & Hodgkins, S. B.
(2023). Kingfisher: A utility for procurement of public sequencing data.
[Computer software]. DOI: 10.5281/zenodo.10525085.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.10525086.svg)](https://doi.org/10.5281/zenodo.10525086)

## License

Copyright Ben Woodcroft 2019-2023. Licensed under GPL3+. See LICENSE.txt.

The source code is available at [https://github.com/wwood/kingfisher-download](https://github.com/wwood/kingfisher-download).
