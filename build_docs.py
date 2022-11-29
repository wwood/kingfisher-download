#!/usr/bin/env python3

import extern
import logging
import argparse
import os

def remove_before(marker, string_to_process):
    splitter = '\n' + marker + '\n'
    return splitter+string_to_process.split(splitter)[1]

if __name__ == '__main__':
    parent_parser = argparse.ArgumentParser(add_help=False)
    # parent_parser.add_argument('--debug', help='output debug information', action="store_true")
    #parent_parser.add_argument('--version', help='output version information and quit',  action='version', version=repeatm.__version__)
    parent_parser.add_argument('--quiet', help='only output errors', action="store_true")

    args = parent_parser.parse_args()

    # Setup logging
    debug = True
    if args.quiet:
        loglevel = logging.ERROR
    else:
        loglevel = logging.DEBUG
    logging.basicConfig(level=loglevel, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

    for subcommand in ['get','extract','annotate']:
        cmd_stub = "bin/kingfisher {} --full-help-roff |pandoc - -t markdown-multiline_tables-simple_tables-grid_tables -f man |sed 's/\\\\\\[/[/g; s/\\\\\\]/]/g; s/^: //'".format(subcommand)
        man_usage = extern.run(cmd_stub)

        subcommand_prelude = 'docs/usage/{}_prelude.md'.format(subcommand)
        if os.path.exists(subcommand_prelude):
            # Remove everything before the options section
            splitters = {
                'pipe': 'COMMON OPTIONS',
                'data': 'OPTIONS',
                'summarise': 'INPUT',
                'makedb': 'REQUIRED ARGUMENTS',
                'appraise': 'INPUT OTU TABLE OPTIONS',
            }
            man_usage = remove_before(splitters[subcommand], man_usage)

            with open('docs/usage/{}.md'.format(subcommand),'w') as f:
                f.write('---\n')
                f.write('title: Kingfisher {}\n'.format(subcommand))
                f.write('---\n')
                f.write('# kingfisher {}\n'.format(subcommand))

                with open(subcommand_prelude) as f2:
                    f.write(f2.read())

                f.write(man_usage)
        else:
            man_usage = remove_before('DESCRIPTION', man_usage)
            with open('docs/usage/{}.md'.format(subcommand),'w') as f:
                f.write('---\n')
                f.write('title: Kingfisher {}\n'.format(subcommand))
                f.write('---\n')
                f.write('# kingfisher {}\n'.format(subcommand))

                f.write(man_usage)

    extern.run("doctave build")