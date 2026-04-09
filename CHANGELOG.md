# Changelog

## v0.5.0

### New features

* Added NGDC/GSA support for CRR accessions with two new download methods: `ngdc-ascp` and `ngdc-http` ([#e490182](https://github.com/wwood/kingfisher-download/commit/e490182))
* Added NGDC metadata support in `annotate` mode - CRR accessions are automatically routed to NGDC while other accessions use NCBI as before
* Added `--cra-accession` option to skip NGDC binary search when the CRA accession is already known ([#7890d12](https://github.com/wwood/kingfisher-download/commit/7890d12))
* Added `authorship` experimental mode ([#94449e8](https://github.com/wwood/kingfisher-download/commit/94449e8))

### Bug fixes and improvements

* Cleaner error reporting: users now see readable error messages instead of Python stack traces; use `--debug` for full tracebacks (fixes [#45](https://github.com/wwood/kingfisher-download/issues/45))
* Handle malformed ENA file-report responses gracefully ([#567635e](https://github.com/wwood/kingfisher-download/commit/567635e))
* Search `~/.aspera` for ascp binary instead of using a hardcoded path ([#7aad273](https://github.com/wwood/kingfisher-download/commit/7aad273))
* Limit the maximum number of download threads ([#cb76cfb](https://github.com/wwood/kingfisher-download/commit/cb76cfb))
* Increased logging around SRA metadata retries ([#81372e6](https://github.com/wwood/kingfisher-download/commit/81372e6))

### Internal / packaging

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
