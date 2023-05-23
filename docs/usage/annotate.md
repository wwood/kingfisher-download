---
title: Kingfisher annotate
---
# kingfisher annotate

# DESCRIPTION

annotate runs by their metadata

# OPTIONS

**-r**, **\--run-identifiers** *RUN_IDENTIFIERS* [*RUN_IDENTIFIERS* \...]

  Run number to download/extract e.g. ERR1739691

**\--run-identifiers-list** *RUN_IDENTIFIERS_LIST*

  Text file containing a newline-separated list of run identifiers
    i.e. a 1 column CSV file.

**-p**, **\--bioproject** *BIOPROJECT*

  BioProject IDs number(s) to download/extract from e.g. PRJNA621514
    or SRP260223

**-o**, **\--output-file** *OUTPUT_FILE*

  Output file to write to [default: stdout]

**-f**, **\--output-format** {human,csv,tsv,json,feather,parquet}

  Output format

**-a**, **\--all-columns**

  Print all metadata columns [default: Print only a few select ones]

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
