---
title: Kingfisher extract
---
# kingfisher extract

# DESCRIPTION

extract .sra format files

# OPTIONS

# EXTRACTION OPTIONS

**\--sra** *SRA*

  Extract this SRA file [required]

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

**-t**, **\--threads** *THREADS*

  Number of threads to use for extraction [default: 8]

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

\\fB\$ kingfisher extract \--sra ERR1739691.sra -t 16 -f fastq.gz\\fR

  
