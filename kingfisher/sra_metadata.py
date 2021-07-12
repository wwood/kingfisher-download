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
        sra_ids = []
        for accession in accessions:
            # SRA IDs from the SRP 
            res = requests.get(
                url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", 
                params={
                    "db": "sra",
                    "term": accession,
                    "tool": "kingfisher", 
                    "email": "kingfisher@github.com",
                    "retmax": 1000,
                    },
                )
            root = ET.fromstring(res.text)
            sra_ids += list([child.text for child in root.iter('Id')])
            if not sra_ids:
                raise Exception(
                    "No SRA samples found in {}"
                    .format(accessions))

        blocks = []
        for block in range(0, len(sra_ids), 25):
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

        return pd.concat(blocks)


