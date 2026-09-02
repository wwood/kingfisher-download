# Changelog

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
* Find the RSA ssh key (`aspera_bypass_rsa.pem`) that ENA now requires for `ena-ascp` downloads, searching `~/.aspera`, the directories alongside the `ascp` binary, and `ascli`, rather than always using the deprecated bundled DSA key. `ascp` is also now run with an empty stdin, so it fails immediately instead of hanging on a `Password:` prompt when the key is not accepted (fixes [#54](https://github.com/wwood/kingfisher-download/issues/54))
* Retry the bioproject `esearch` request to NCBI eutils, which was the one eutils call not going through the shared retry logic, so a transient failure such as an HTTP 429 rate limit aborted `kingfisher annotate -p` outright
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
