## ena-fast-download

A simple script to download FASTQ files of reads from the European Nucleotide
Archive (ENA). This is analogous to using NCBI's `prefetch` from the [SRA
tools](https://ncbi.github.io/sra-tools/) except that FASTQ files are downloaded
rather than `.sra` format files which must be further converted to FASTQ.

This tool was built based on the very helpful bio-stars thread
https://www.biostars.org/p/325010/ written by @ATpoint.

To find run identifiers to be used as input to this script, you might find the
[SRA explorer](https://ewels.github.io/sra-explorer/) site helpful.

### Requirements

* An aspera client (see https://www.biostars.org/p/325010/ or
  https://downloads.asperasoft.com/en/downloads/8?list)
* curl, which is generally installed by default on Linux distributions (and
  OSX?)
* Python 3

All of these programs must be in your `$PATH`. This program has only been tested
on Linux, but may work on OSX too.

### Usage

Linux:
```
./ena-fast-download.py ERR1739691
```
OSX:
```
./ena-fast-download.py ERR1739691 --ssh_key osx
```

That will download the forward and reverse FASTQ file for that run into the
current directory.


### License

Copyright Ben Woodcroft 2019. Licensed under GPL3+. See LICENSE.txt.
