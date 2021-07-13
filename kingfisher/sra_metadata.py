import os
import time
import requests
import xml.etree.ElementTree as ET

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import pandas as pd

class SraMetadata:
    def efetch_sra_from_accessions(self, accessions):
        # SRA IDs from the SRP 
        res = requests.get(
            url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", 
            params={
                "db": "sra",
                "term": " OR ".join(["{}[accn]".format(a) for a in accessions]),
                "tool": "kingfisher", 
                "email": "kingfisher@github.com",
                "retmax": 1000,
                },
            )
        root = ET.fromstring(res.text)
        sra_ids = list([c.text for c in root.find('IdList').getchildren()])

        if not sra_ids:
            raise Exception(
                "No SRA samples found in {}"
                .format(accessions))

        blocks = []
        for block in range(0, len(sra_ids), 50):
            res = requests.get(
                url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi", 
                params={
                    "db": "sra",
                    "id": ",".join(sra_ids[block:block + 25]),
                    "tool": "kingfisher", 
                    "email": "kingfisher@github.com",
                    "rettype": "runinfo", 
                    "retmode": "text",                
                    },
                )
            df = pd.read_csv(StringIO(res.text.strip()))
            blocks.append(df)

        metadata = pd.concat(blocks)

        # Ensure all hits are found
        not_found_accessions = list([a for a in accessions if a not in metadata['Run'].values])
        if len(not_found_accessions) > 0:
            raise Exception("Unable to find accession(s): {}".format(not_found_accessions))
        if len(metadata) != len(accessions):
            raise Exception("Found discordant number of results during esearch, not sure what is going on")

        return metadata


