import os
import re

from .exception import KingfisherException


ILLUMINA_PE_SINGLE_INDEX = {3: ('R1', 'I1', 'R2')}
ILLUMINA_PE_DUAL_INDEX = {4: ('R1', 'I1', 'I2', 'R2')}
FLEXIBLE_10X = {
    2: ('R1', 'R2'),
    3: ('R1', 'I1', 'R2'),
    4: ('R1', 'I1', 'I2', 'R2'),
}

READ_LAYOUTS = {
    'illumina-se': {1: ('R1',)},
    'illumina-pe': {2: ('R1', 'R2')},
    'illumina-se-single-index': {2: ('R1', 'I1')},
    'illumina-se-dual-index': {3: ('R1', 'I1', 'I2')},
    'illumina-pe-single-index': ILLUMINA_PE_SINGLE_INDEX,
    'illumina-pe-dual-index': ILLUMINA_PE_DUAL_INDEX,
    '10x-gex': FLEXIBLE_10X,
    '10x-vdj': FLEXIBLE_10X,
    '10x-spatial': FLEXIBLE_10X,
    '10x-atac': ILLUMINA_PE_DUAL_INDEX,
    '10x-atac-bcl': {4: ('R1', 'I1', 'R2', 'R3')},
}

READ_LAYOUT_ALIASES = {
    'parse-wt-single-index': 'illumina-pe-single-index',
    'parse-wt-dual-index': 'illumina-pe-dual-index',
}

SUPPORTED_READ_LAYOUTS = tuple(
    ['sra'] + sorted(READ_LAYOUTS) + sorted(READ_LAYOUT_ALIASES) + ['custom'])

TECHNICAL_READ_LAYOUTS = frozenset((
    'illumina-se-single-index',
    'illumina-se-dual-index',
    'illumina-pe-single-index',
    'illumina-pe-dual-index',
    '10x-gex',
    '10x-vdj',
    '10x-spatial',
    '10x-atac',
    '10x-atac-bcl',
    'parse-wt-single-index',
    'parse-wt-dual-index',
))

SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
NUMBERED_READ_RE_TEMPLATE = r'^{}_(\d+)\.(fastq(?:\.gz)?|fasta(?:\.gz)?)$'


def validate_safe_name(value, description):
    if not value or not SAFE_NAME_RE.match(value) or '..' in value:
        raise KingfisherException(
            "Unsafe {} '{}'. Use only letters, numbers, '.', '_', and '-'; '..' is not allowed.".format(
                description, value))
    return value


def parse_custom_read_names(read_names):
    if read_names is None:
        raise KingfisherException(
            "--read-names is required when --read-layout custom is selected")
    names = tuple(name.strip() for name in read_names.split(','))
    if not names or any(not name for name in names):
        raise KingfisherException("--read-names must be a comma-separated list of non-empty names")
    for name in names:
        validate_safe_name(name, 'read name')
    if len(set(names)) != len(names):
        raise KingfisherException("--read-names values must be unique")
    return names


def canonical_read_layout(read_layout):
    return READ_LAYOUT_ALIASES.get(read_layout, read_layout)


def validate_read_layout_options(read_layout, read_names=None, sample_name=None):
    if read_layout not in SUPPORTED_READ_LAYOUTS:
        raise KingfisherException("Unknown read layout '{}'".format(read_layout))
    if read_layout == 'custom':
        parse_custom_read_names(read_names)
    elif read_names is not None:
        raise KingfisherException("--read-names can only be used with --read-layout custom")
    if sample_name is not None:
        validate_safe_name(sample_name, 'sample name')


def validate_read_name_style(read_name_style):
    if read_name_style not in ('simple', 'illumina'):
        raise KingfisherException("Unknown read name style '{}'".format(read_name_style))


def require_technical_reads_for_sra(read_layout, include_technical):
    if read_layout in TECHNICAL_READ_LAYOUTS and not include_technical:
        raise KingfisherException(
            "Read layout '{}' includes technical/index reads. Use --include-technical "
            "to preserve them during SRA extraction.".format(read_layout))


def read_names_for_layout(read_layout, stream_count, read_names=None):
    if read_layout == 'sra':
        return None
    if read_layout == 'custom':
        names = parse_custom_read_names(read_names)
        if len(names) != stream_count:
            raise KingfisherException(
                "Cannot apply read layout 'custom': expected {} read streams from "
                "--read-names but found {}.".format(len(names), stream_count))
        return names

    canonical = canonical_read_layout(read_layout)
    layouts = READ_LAYOUTS[canonical]
    if stream_count not in layouts:
        expected = ', '.join(str(count) for count in sorted(layouts))
        raise KingfisherException(
            "Cannot apply read layout '{}': expected {} read streams but found {}.".format(
                read_layout, expected, stream_count))
    return layouts[stream_count]


def possible_read_names(read_layout, read_names=None):
    if read_layout == 'sra':
        return []
    if read_layout == 'custom':
        return [parse_custom_read_names(read_names)]
    layouts = READ_LAYOUTS[canonical_read_layout(read_layout)]
    return [layouts[count] for count in sorted(layouts, reverse=True)]


def semantic_filename(sample_name, read_name, extension, read_name_style):
    if read_name_style == 'simple':
        return '{}_{}.{}'.format(sample_name, read_name, extension)
    if read_name_style == 'illumina':
        return '{}_S1_{}_001.{}'.format(sample_name, read_name, extension)
    raise KingfisherException("Unknown read name style '{}'".format(read_name_style))


def _numbered_sources(output_files, run_identifier):
    pattern = re.compile(NUMBERED_READ_RE_TEMPLATE.format(re.escape(run_identifier)))
    numbered = []
    for path in output_files:
        match = pattern.match(os.path.basename(path))
        if match:
            numbered.append((int(match.group(1)), path, match.group(2)))
    numbered.sort(key=lambda value: value[0])
    if numbered:
        expected_numbers = list(range(1, len(numbered) + 1))
        found_numbers = [number for number, _, _ in numbered]
        if found_numbers != expected_numbers:
            raise KingfisherException(
                "Cannot apply read layout: numbered streams are not contiguous from 1 (found {}).".format(
                    ', '.join(str(number) for number in found_numbers)))
        return numbered

    # sracat-rs uses RUN.<extension> for single-end output.
    single_pattern = re.compile(r'^{}\.(fastq(?:\.gz)?|fasta(?:\.gz)?)$'.format(
        re.escape(run_identifier)))
    singles = []
    for path in output_files:
        match = single_pattern.match(os.path.basename(path))
        if match:
            singles.append((1, path, match.group(1)))
    return singles


def apply_read_layout(output_files, run_identifier, read_layout='sra', read_names=None,
                      read_name_style='simple', sample_name=None, force=False):
    if read_layout == 'sra':
        return output_files

    validate_read_layout_options(read_layout, read_names, sample_name)
    validate_read_name_style(read_name_style)
    sample = validate_safe_name(sample_name or run_identifier, 'sample name')
    sources = _numbered_sources(output_files, run_identifier)
    names = read_names_for_layout(read_layout, len(sources), read_names)

    mappings = []
    for (_, source, extension), name in zip(sources, names):
        target = os.path.join(
            os.path.dirname(source),
            semantic_filename(sample, name, extension, read_name_style))
        mappings.append((source, target))

    targets = [target for _, target in mappings]
    if len(set(os.path.abspath(target) for target in targets)) != len(targets):
        raise KingfisherException("Read layout produces duplicate output filenames")

    source_paths = set(os.path.abspath(source) for source, _ in mappings)
    collisions = [target for source, target in mappings
                  if os.path.exists(target) and os.path.abspath(target) != os.path.abspath(source)]
    if collisions and not force:
        raise KingfisherException(
            "Cannot apply read layout '{}': target file(s) already exist: {}".format(
                read_layout, ', '.join(collisions)))
    if collisions and force:
        for target in collisions:
            # Never remove another source in a rename plan.
            if os.path.abspath(target) in source_paths:
                raise KingfisherException(
                    "Cannot safely rename read streams because target '{}' is also a source file".format(
                        target))
            os.remove(target)

    renamed = dict(mappings)
    for source, target in mappings:
        if os.path.abspath(source) != os.path.abspath(target):
            os.rename(source, target)
    return [renamed.get(path, path) for path in output_files]
