import os
import time
import requests
import xml.etree.ElementTree as ET
import logging

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import pandas as pd

from bird_tool_utils import iterable_chunks

class SraMetadata:
    def fetch_runs_from_bioproject(self, bioproject_accession):
        retmax = 10000
        res = requests.get(
            url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", 
            params={
                "db": "sra",
                "term": "{}[BioProject]".format(bioproject_accession),
                "tool": "kingfisher", 
                "email": "kingfisher@github.com",
                "retmax": retmax,
                },
            )
        root = ET.fromstring(res.text)
        sra_ids = list([c.text for c in root.find('IdList').getchildren()])
        if len(sra_ids) == retmax:
            logging.warning("Unexpectedly found the maximum number of results for this query, possibly some results will be missing")

        # Now convert the IDs into runs
        metadata = self.efetch_metadata_from_ids(sra_ids)
        return metadata['Run'].to_list()

    def efetch_metadata_from_ids(self, sra_ids):
        blocks = []
        for chunk in iterable_chunks(sra_ids, 50):
            chunk_sras = list([c for c in chunk if c is not None])
            res = requests.get(
                url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi", 
                params={
                    "db": "sra",
                    "id": ",".join(chunk_sras),
                    "tool": "kingfisher", 
                    "email": "kingfisher@github.com",
                    "rettype": "runinfo", 
                    "retmode": "text",                
                    },
                )
            df = pd.read_csv(StringIO(res.text.strip()))
            blocks.append(df)
            if len(df) != len(chunk_sras):
                logging.warning("Unexpectedly found discordant number of Id hits: Expected {}, found {}".format(len(chunk_sras), len(df)))
        return pd.concat(blocks)


    def efetch_sra_from_accessions(self, accessions):
        sra_ids = []
        
        # Iterate 100 at a time so that if many results are returned, that can
        # be detected
        for chunk in iterable_chunks(accessions, 500):
            retmax = 1000
            chunk_accessions = list([a for a in accessions if a is not None])
            res = requests.get(
                url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", 
                params={
                    "db": "sra",
                    "term": " OR ".join(["{}[accn]".format(a) for a in chunk_accessions]),
                    "tool": "kingfisher", 
                    "email": "kingfisher@github.com",
                    "retmax": retmax,
                    },
                )
            root = ET.fromstring(res.text)
            ids = list([c.text for c in root.find('IdList').getchildren()])
            if len(ids) != len(chunk_accessions):
                logging.warning("Unexpectedly found a discordant number of results for this query (expected {}, found {})". \
                    format(len(chunk_accessions), len(chunk_accessions)))
            sra_ids += ids

        if not sra_ids:
            raise Exception(
                "No SRA samples found in {}"
                .format(accessions))

        metadata = self.efetch_metadata_from_ids(sra_ids)

        # Ensure all hits are found
        not_found_accessions = list([a for a in accessions if a not in metadata['Run'].values])
        if len(not_found_accessions) > 0:
            raise Exception("Unable to find accession(s): {}".format(not_found_accessions))
        if len(metadata) != len(accessions):
            raise Exception("Found discordant number of results during esearch, not sure what is going on")

        return metadata
