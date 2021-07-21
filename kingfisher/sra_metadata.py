import os
import time
import requests
import xml.etree.ElementTree as ET
import logging
import re

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
        header_regex = re.compile('\nRun,ReleaseDate.*?\n')

        # Keep the URI length short because very long URIs return 414 errors.
        # Larger values seem to return 414. 
        term_character_length_limit = 2600
        next_accession_index = 0

        while next_accession_index < len(sra_ids):
            request_term = None
            while next_accession_index < len(sra_ids):
                next_accession = sra_ids[next_accession_index]
                term_bit = next_accession
                if request_term is None:
                    request_term = term_bit
                else:
                    next_bit = '{},{}'.format(request_term, term_bit)
                    if len(next_bit) < term_character_length_limit:
                        request_term = next_bit
                    else:
                        break
                next_accession_index += 1
            
            retmax = 1000
            logging.debug("Running efetch for IDs with request term: {}".format(request_term))
            res = requests.get(
                url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi", 
                params={
                    "db": "sra",
                    "id": request_term,
                    "tool": "kingfisher", 
                    "email": "kingfisher@github.com",
                    "rettype": "runinfo", 
                    "retmode": "text",                
                    },
                )
            if not res.ok:
                raise Exception("HTTP Failure when requesting efetch from IDs: {}".format(res))

            # For unknown reasons, sometimes a header row will appear in the
            # middle of the response text's data. Remove it.
            filtered_text = header_regex.sub('\n',res.text)

            df = pd.read_csv(StringIO(filtered_text.strip()))
            blocks.append(df)

        return pd.concat(blocks)


    def efetch_sra_from_accessions(self, accessions):
        accessions = list(set(accessions))
        if len(accessions) == 0:
            return []
        logging.info("Querying NCBI esearch for {} distinct accessions e.g. {}".format(
            len(accessions), accessions[0]))
        sra_ids = []
        
        # Keep the URI length short because very long URIs return 414 errors.
        # Larger values seem to return 414. 
        term_character_length_limit = 2600
        next_accession_index = 0

        while next_accession_index < len(accessions):
            request_term = None
            while next_accession_index < len(accessions):
                next_accession = accessions[next_accession_index]
                term_bit = "{}[accn]".format(next_accession)
                if request_term is None:
                    request_term = term_bit
                else:
                    next_bit = '{} OR {}'.format(request_term, term_bit)
                    if len(next_bit) < term_character_length_limit:
                        request_term = next_bit
                    else:
                        break
                next_accession_index += 1
            
            retmax = 1000
            res = requests.get(
                url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", 
                params={
                    "db": "sra",
                    "term": request_term,
                    "tool": "kingfisher", 
                    "email": "kingfisher@github.com",
                    "retmax": retmax,
                    },
                )
            if not res.ok:
                raise Exception("HTTP Failure when requesting efetch from accessions: {}".format(res))
            root = ET.fromstring(res.text)
            id_list_node = root.find('IdList')
            ids = list(set([c.text for c in id_list_node.getchildren()]))
            sra_ids += ids

        if len(sra_ids) == 0:
            logging.warning("Unable to find any accessions, from the list: {}".format(accessions))
            return None

        logging.info("Querying NCBI efetch for {} distinct IDs e.g. {}".format(
            len(sra_ids), sra_ids[0]))
        metadata = self.efetch_metadata_from_ids(sra_ids)

        # Ensure all hits are found, and trim results to just those that are real hits
        found_accessions_metadata = metadata[metadata['Run'].isin(accessions)]

        # Sometimes duplicates are returned e.g. when querying with SRR8482198.
        # We cannot use drop_duplicates() because NaN values means equality
        # doesn't operate as we want i.e. NaN != NaN. So we groupby instead and
        # take the first. This assumes all rows are the same, which I hope to be
        # true.
        found_accessions_metadata = found_accessions_metadata.groupby('Run', as_index=False).agg('first')

        found_accessions_metadata.sort_values(['SRAStudy','Run'], inplace=True)

        if len(found_accessions_metadata) != len(accessions):
            found_runs = set(found_accessions_metadata['Run'].to_list())
            not_found = list([a for a in accessions if a not in found_runs])
            logging.warning("Unable to find all accessions. The {} missing ones were: {}".format(
                len(not_found), not_found
            ))

        return found_accessions_metadata
