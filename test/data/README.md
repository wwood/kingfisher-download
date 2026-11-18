# Real SRA fixtures

## DRR002803.sra

This existing fixture is the complete public run
[DRR002803](https://www.ncbi.nlm.nih.gov/sra/DRR002803) (147,675 bytes;
116 spots, 454 sequencing). Its deposited read order contains three technical
streams followed by one biological stream. Tests use a custom layout to preserve
this order; Illumina read labels would not describe this library.

## SRR10612247.first100.sra

This fixture contains the first 100 spots of
[SRR10612247](https://www.ncbi.nlm.nih.gov/sra/SRR10612247), associated with
[GSE141701](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE141701),
GSM4211277, SRP235289, and PRJNA594401. The original run contains 92,344,810 spots
and two biological streams of 26 and 98 bases. The archive does not contain
separate technical/index streams. The full SRA archive is approximately 10 GB,
so it is unsuitable for routine regression tests.

The first 100 spots were exported with NCBI SRA Toolkit 3.4.1 on 18 November 2026
and repacked as a small SRA archive. Sequences, qualities, paired-read order, and
biological read types are preserved. Archive metadata and extracted headers are
regenerated; this is a derived fixture, not an unmodified copy of the original
archive. The regression tests compare sequence and quality hashes against the
original bounded FASTQ export.

To regenerate the fixture in an empty temporary directory with SRA Toolkit
installed, run:

```bash
fastq-dump SRR10612247 --split-files --minSpotId 1 --maxSpotId 100
latf-load --platform ILLUMINA --quality PHRED_33 --output repacked \
    --read1PairFiles SRR10612247_1.fastq --read2PairFiles SRR10612247_2.fastq
kar --create SRR10612247.first100.sra --directory repacked
vdb-dump ./SRR10612247.first100.sra --info
vdb-dump ./SRR10612247.first100.sra --rows 1 --columns READ_LEN,READ_TYPE
sha256sum SRR10612247.first100.sra
```

Copy the generated archive into `test/data/` after verifying that it contains
exactly 100 spots and two biological reads per spot. Regeneration requires
network access, but the fixture tests run offline. Do not use `vdb-copy --rows`
on this database as a substitute: SRA Toolkit 3.4.1 resets the row range when
copying database tables and can copy the entire run.

The checked-in archive is 86,738 bytes, with SHA-256:

```text
87110ba67bc1618d5ac02f6fea5d2e03f212861b8007d9970010973d0315f1ae
```

The archive checksum may change after regeneration because loader metadata
includes timestamps. The content checks below should remain unchanged. Each
hash covers the concatenation of each read's sequence and quality string, in
spot order, without headers, separators, or newlines:

| Stream | SHA-256 |
| --- | --- |
| R1 | `3cdbb1eeb4b4a40e69744924fee005e0eae5d57cfde8ef161c56b5f589eb439a` |
| R2 | `c61705f4b340d43cd1e79030811faa22d1c9c7877a38d4e4def21b844fb4ee7e` |
