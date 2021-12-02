#!/usr/bin/env python3

import logging
import os
import argparse

import extern

if __name__ == '__main__':
    parent_parser = argparse.ArgumentParser()
    parent_parser.add_argument('--debug', help='output debug information', action="store_true")
    parent_parser.add_argument('--quiet', help='only output errors', action="store_true")
    args = parent_parser.parse_args()

    # Setup logging
    if args.debug:
        loglevel = logging.DEBUG
    elif args.quiet:
        loglevel = logging.ERROR
    else:
        loglevel = logging.INFO
    logging.basicConfig(level=loglevel, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

    accessions = ['SRR12118866', 'SRR8906566', 'ERR3906046']
    # accessions = ['SRR12118866']

    methods_formats_threads = [
        ('aws-cp','sra',None,None),
        ('gcp-cp ','sra',None, '--allow-paid'),
        ('ena-ascp','fastq.gz',None,None),
        ('ena-ftp','fastq.gz',None,None),
        ('prefetch','sra',None,None),
        ('aws-http','sra',4,None)
    ]

    for replicate in [1,2,3]:
        for acc in accessions:
            for (method,form,threads,other_args) in methods_formats_threads:
                logging.info('{} on {}'.format((method,form,threads),acc))

                threads_arg = ''
                if threads is not None:
                    threads_arg = '--download-threads {}'.format(threads)
                if other_args is None:
                    other_args = ''

                stdout = extern.run("/usr/bin/time -f '%E %U' -o /tmp/kingfisher_bench1 ~/git/kingfisher-local/bin/kingfisher get {} {} -r {} -f {} -m {}".format(
                    threads_arg, other_args, acc, form, method))
                
                with open('/tmp/kingfisher_bench1', 'r') as f:
                    stdout = f.read().strip()

                logging.debug("stdout: {}".format(stdout))
                print('\t'.join(stdout.strip().split(' ')+[acc]+[method,form,str(threads)]))

                logging.info("done")
                if form=='sra':
                    os.remove(acc+'.{}'.format(form))
                else:
                    os.remove(acc+'_1.{}'.format(form))
                    os.remove(acc+'_2.{}'.format(form))