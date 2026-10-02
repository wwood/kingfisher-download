# Changelog

## Unreleased

### Bug fixes and improvements

* Fixed `--check-md5sums` never detecting corrupt files: the MD5 check returned the file's digest before comparing it, so every file passed and "MD5sum OK" was always logged. It now returns true only when the digest matches the expected MD5 (present in v0.5.0, introduced in c7d0cf15)
* With `--check-md5sums`, the `aws-http` method now logs an error, deletes the file and fails (so the next method is tried, or kingfisher exits non-zero) when a download does not match its expected MD5, instead of only logging a warning and keeping the corrupt file. It also stops at the first location that downloads and verifies correctly, rather than re-downloading from the remaining locations

## v0.5.0

### New features

* Added *experimental* NGDC/GSA support for CRR accessions with two new download methods: `ngdc-ascp` and `ngdc-http` ([#e490182](https://github.com/wwood/kingfisher-download/commit/e490182))
* Added *experimental* NGDC metadata support in `annotate` mode - CRR accessions are automatically routed to NGDC while other accessions use NCBI as before
* Added `--cra-accession` option to skip NGDC binary search when the CRA accession is already known ([#7890d12](https://github.com/wwood/kingfisher-download/commit/7890d12))
* Added *experimental* `authorship` experimental mode ([#94449e8](https://github.com/wwood/kingfisher-download/commit/94449e8))
* Added `--spot-sorted`, which extracts reads in spot (submission) order via fasterq-dump instead of the default sracat-rs storage order

### Bug fixes and improvements

* Deprecated `--unsorted`: it now has no effect, since extraction is in storage order by default. `--stdout` no longer requires `--unsorted`
* When extracting to compressed output (`fasta.gz`/`fastq.gz`), sracat-rs now streams directly into `pigz` via FIFOs instead of writing an intermediate uncompressed FASTQ/FASTA file to disk
* Stream `--stdout` extraction with sracat-rs `--accept-singles` instead of `--single-out /dev/stdout`, which could truncate/overwrite the output when stdout is redirected to a regular file and the run contains single/orphan reads
* For FASTA-only output, download the smaller SRA Lite file in the `prefetch` method (`--eliminate-quals`), since base qualities are discarded anyway, falling back to a full download when no SRA Lite file is available
* Support `.sralite` files in the `prefetch` method by renaming the downloaded `.sralite` file to `.sra`, and clean up any reference sequences prefetch downloads alongside reference-compressed runs
* Cleaner error reporting: users now see readable error messages instead of Python stack traces; use `--debug` for full tracebacks (fixes [#45](https://github.com/wwood/kingfisher-download/issues/45))
* Handle malformed ENA file-report responses gracefully ([#567635e](https://github.com/wwood/kingfisher-download/commit/567635e))
* Search `~/.aspera` for ascp binary instead of using a hardcoded path ([#7aad273](https://github.com/wwood/kingfisher-download/commit/7aad273))
* Limit the maximum number of download threads ([#cb76cfb](https://github.com/wwood/kingfisher-download/commit/cb76cfb))
* Increased logging around SRA metadata retries ([#81372e6](https://github.com/wwood/kingfisher-download/commit/81372e6))

### Internal / packaging

* Require sracat-rs >=0.2.0, which fixes an intermittent double-free crash during multi-threaded (`--threads` >1) extraction
* Migrated from conda to pixi
* Use `entry_points` rather than `scripts` in setup.py
* Use bioconda-packaged ascp

## v0.4.1

## v0.4.0

## v0.3.1

## v0.3.0

## v0.2.2

## v0.2.1

## v0.2.0

## v0.1.2

## v0.1.1

## v0.1.0

## v0.0.2

## v0.0.1
