import os
import time
import requests
import xml.etree.ElementTree as ET
import logging
import re
import collections

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import pandas as pd

from bird_tool_utils import iterable_chunks

# Define these constants so that they can be referred to in other classes
# without index errors.
STUDY_ACCESSION_KEY = 'study_accession'
RUN_ACCESSION_KEY = 'run'
BASES_KEY = 'bases'
SAMPLE_NAME_KEY = 'sample_name'

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
                "usehistory": "y",
                },
            )
        if not res.ok:
            raise Exception("HTTP Failure when requesting search from bioproject: {}: {}".format(res, res.text))
        root = ET.fromstring(res.text)
        sra_ids = list([c.text for c in root.find('IdList')])
        if len(sra_ids) == retmax:
            logging.warning("Unexpectedly found the maximum number of results for this query, possibly some results will be missing")
        webenv = root.find('WebEnv').text

        # Now convert the IDs into runs
        metadata = self.efetch_metadata_from_ids(webenv, accessions, len(sra_ids))
        return metadata[RUN_ACCESSION_KEY].to_list()

    def efetch_metadata_from_ids(self, webenv, accessions, num_ids):
        data_frames = []

        retmax = num_ids+10
        logging.debug("Running efetch ..")
        res = requests.get(
            url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={
                "db": "sra",
                "tool": "kingfisher",
                "email": "kingfisher@github.com",
                "webenv": webenv,
                "query_key": 1
                },
            )
        if not res.ok:
            raise Exception("HTTP Failure when requesting efetch from IDs: {}: {}".format(res, res.text))

        root = ET.fromstring(res.text)

        def try_get(func):
            try:
                return func()
            except AttributeError:
                return ''

        if root.find("ERROR") is not None:
            logging.error("Error when fetching metadata: {}".format(root.find("ERROR").text))

        # Some samples such as SAMN13241871 are linked to multiple runs e.g. SRR10489833
        accessions_set = set(accessions)

        for pkg in root.findall('EXPERIMENT_PACKAGE'):
            d = collections.OrderedDict()
            d['experiment_accession'] = try_get(lambda: pkg.find('./EXPERIMENT').attrib['accession'])
            d['experiment_title'] = try_get(lambda: pkg.find('./EXPERIMENT/TITLE').text)
            l = pkg.find('./EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR')
            d['library_name'] = try_get(lambda: l.find('LIBRARY_NAME').text)
            d['library_strategy'] = try_get(lambda: l.find('LIBRARY_STRATEGY').text)
            d['library_source'] = try_get(lambda: l.find('LIBRARY_SOURCE').text)
            d['library_selection'] = try_get(lambda: l.find('LIBRARY_SELECTION').text)
            d['model'] = try_get(lambda: pkg.find('./EXPERIMENT/PLATFORM/')[0].text)
            d['submitter'] = ''
            for k, v in pkg.find('./SUBMISSION').attrib.items():
                if k not in ('accession','alias'):
                    if d['submitter'] == '':
                        d['submitter'] = v
                    else:
                        d['submitter'] = "{}, {}".format(d['submitter'], v)
            d[STUDY_ACCESSION_KEY] = try_get(lambda: pkg.find('./STUDY').attrib['accession'])
            d['study_alias'] = try_get(lambda: pkg.find('./STUDY').attrib['alias'])
            d['study_centre_project_name'] = try_get(lambda: pkg.find('./STUDY/DESCRIPTOR/CENTER_PROJECT_NAME').text)
            d['sample_alias'] = try_get(lambda: pkg.find('./SAMPLE').attrib['alias'])
            d['sample_accession'] = try_get(lambda: pkg.find('./SAMPLE').attrib['accession'])
            d['taxon_name'] = try_get(lambda: pkg.find('./SAMPLE/SAMPLE_NAME/SCIENTIFIC_NAME').text)
            d['sample_description'] = try_get(lambda: pkg.find('./SAMPLE/DESCRIPTION').text)
            d[SAMPLE_NAME_KEY] = d['library_name'] #default, maybe there's always a title though?
            if pkg.find('./SAMPLE/SAMPLE_ATTRIBUTES'):
                for attr in pkg.find('./SAMPLE/SAMPLE_ATTRIBUTES'):
                    tag = attr.find('TAG').text
                    value = attr.find('VALUE').text
                    if tag == 'Title':
                        d[SAMPLE_NAME_KEY] = value
                    else:
                        d[tag] = value
            d['study_title'] = try_get(lambda: pkg.find('./STUDY/DESCRIPTOR/STUDY_TITLE').text)
            d['design_description'] = try_get(lambda: pkg.find('./EXPERIMENT/DESIGN/DESIGN_DESCRIPTION').text)
            d['study_abstract'] = try_get(lambda: pkg.find('./STUDY/DESCRIPTOR/STUDY_ABSTRACT').text)
            
            # Account for the fact that multiple runs may be associated with
            # this sample
            d['number_of_runs_for_sample'] = len(pkg.findall('./RUN_SET/RUN'))

            for run in pkg.findall('./RUN_SET/RUN'):
                accession_here = run.attrib['accession']
                if accession_here in accessions:
                    d2 = d.copy()
                    d2['spots'] = try_get(lambda: int(run.attrib['total_spots']))
                    d2[BASES_KEY] = try_get(lambda: int(run.attrib['total_bases']))
                    d2['run_size'] = try_get(lambda: int(run.attrib['size']))
                    d2[RUN_ACCESSION_KEY] = try_get(lambda: run.attrib['accession'])
                    d2['published'] = try_get(lambda: run.attrib['published'])
                    stats = run.find('Statistics')
                    if stats is not None:
                        for (i, r) in enumerate(stats):
                            d2['read{}_length_average'.format(i+1)] = r.attrib['average']
                            d2['read{}_length_stdev'.format(i+1)] = r.attrib['stdev']
                    data_frames.append(d2)

        return pd.DataFrame(data_frames)

    def _print_xml(self, element, prefix):
        if prefix is None or prefix == '':
            p2 = ""
        else:
            p2 = "{}_".format(prefix)
        for k, v in element.attrib.items():
            print("\t".join(['{}{}'.format(p2,k),v]))
        if element.text:
            print("\t".join(['{}{}'.format(p2, element.tag), element.text]))
        for e in element:
            self.print_xml(e, '{}{}'.format(p2, e.tag))

    def efetch_sra_from_accessions(self, accessions):
        accessions = list(set(accessions))
        if len(accessions) == 0:
            return []
        logging.info("Querying NCBI esearch for {} distinct accessions e.g. {}".format(
            len(accessions), accessions[0]))
        sra_ids = []

        webenv = None
        request_term = ' OR '.join(["{}[accn]".format(acc) for acc in accessions])

        retmax = len(accessions)+10
        params={
            "db": "sra",
            "term": request_term,
            "tool": "kingfisher",
            "email": "kingfisher@github.com",
            "retmax": retmax,
            "usehistory": "y",
            }
        if webenv is None:
            params['WebEnv'] = webenv
        res = requests.post(
            url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            data=params)
        if not res.ok:
            raise Exception("HTTP Failure when requesting esearch from accessions: {}: {}".format(res, res.text))
        root = ET.fromstring(res.text)
        if webenv is None:
            webenv = root.find('WebEnv').text
        id_list_node = root.find('IdList')
        sra_ids = list(set([c.text for c in id_list_node]))

        if len(sra_ids) == 0:
            logging.warning("Unable to find any accessions, from the list: {}".format(accessions))
            return None

        logging.info("Querying NCBI efetch for {} distinct IDs e.g. {}".format(
            len(sra_ids), sra_ids[0]))
        metadata = self.efetch_metadata_from_ids(webenv, accessions, len(sra_ids))

        # Ensure all hits are found, and trim results to just those that are real hits
        if RUN_ACCESSION_KEY not in metadata.columns:
            raise Exception("No metadata could be retrieved")

        metadata.sort_values([STUDY_ACCESSION_KEY,RUN_ACCESSION_KEY], inplace=True)

        if len(metadata) != len(accessions):
            found_runs = set(metadata[RUN_ACCESSION_KEY].to_list())
            not_found = list([a for a in accessions if a not in found_runs])
            logging.warning("Unable to find all accessions. The {} missing ones were: {}".format(
                len(not_found), not_found
            ))

        return metadata
