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

* An Aspera connect client (see https://www.ibm.com/aspera/connect/ or https://www.biostars.org/p/325010/)
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

### FAQ
If you see this error `/bin/sh: 1: ascp: not found` as below:
```
$ ./ena-fast-download.py ERR3357550
09/14/2020 09:33:42 AM INFO: Using aspera ssh key file: $HOME/.aspera/connect/etc/asperaweb_id_dsa.openssh
09/14/2020 09:33:42 AM INFO: Querying ENA for FTP paths for ERR3357550..
09/14/2020 09:33:47 AM INFO: Downloading 2 FTP read set(s): ftp.sra.ebi.ac.uk/vol1/fastq/ERR335/000/ERR3357550/ERR3357550_1.fastq.gz, ftp.sra.ebi.ac.uk/vol1/fastq/ERR335/000/ERR3357550/ERR3357550_2.fastq.gz
09/14/2020 09:33:47 AM INFO: Running command: ascp -T -l 300m -P33001  -i $HOME/.aspera/connect/etc/asperaweb_id_dsa.openssh era-fasp@fasp.sra.ebi.ac.uk:/vol1/fastq/ERR335/000/ERR3357550/ERR3357550_1.fastq.gz .
/bin/sh: 1: ascp: not found
Traceback (most recent call last):
  File "/home/ben/git/ena-fast-download-local/ena-fast-download.py", line 115, in <module>
    subprocess.check_call(cmd,shell=True)
  File "/home/ben/miniconda3/lib/python3.7/subprocess.py", line 363, in check_call
    raise CalledProcessError(retcode, cmd)
subprocess.CalledProcessError: Command 'ascp -T -l 300m -P33001  -i $HOME/.aspera/connect/etc/asperaweb_id_dsa.openssh era-fasp@fasp.sra.ebi.ac.uk:/vol1/fastq/ERR335/000/ERR3357550/ERR3357550_1.fastq.gz .' returned non-zero exit status 127.
```
then you have not installed the Aspera client correctly. See the dependencies section of this document.


### License

Copyright Ben Woodcroft 2019. Licensed under GPL3+. See LICENSE.txt.
