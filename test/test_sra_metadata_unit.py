#!/usr/bin/env python3

import os.path
import sys
import unittest
from unittest import mock

sys.path = [os.path.join(os.path.dirname(os.path.realpath(__file__)),'..')] + sys.path

import pandas as pd

import kingfisher.sra_metadata
from kingfisher.sra_metadata import RUN_ACCESSION_KEY, SraMetadata


ESEARCH_RESULT = '<eSearchResult><Count>1</Count><WebEnv>WE1</WebEnv>' \
    '<QueryKey>1</QueryKey></eSearchResult>'


class FakeResponse:
    def __init__(self, ok, text):
        self.ok = ok
        self.text = text


class Tests(unittest.TestCase):
    def test_bioproject_esearch_is_retried(self):
        # NCBI eutils returns 429 when the (unauthenticated) 3 requests/second
        # rate limit is exceeded, which should be retried rather than fatal
        responses = [
            FakeResponse(False, '{"error":"API rate limit exceeded","count":"4","limit":"3"}'),
            FakeResponse(True, ESEARCH_RESULT),
        ]
        with mock.patch.object(kingfisher.sra_metadata.requests, 'get',
                               side_effect=lambda *args, **kwargs: responses.pop(0)) as get, \
                mock.patch.object(kingfisher.sra_metadata.time, 'sleep') as sleep, \
                mock.patch.object(SraMetadata, 'efetch_metadata_from_ids',
                                  return_value=pd.DataFrame({RUN_ACCESSION_KEY: ['ERR1739691']})):
            self.assertEqual(
                ['ERR1739691'], SraMetadata().fetch_runs_from_bioprojects(['PRJEB15706']))
        self.assertEqual(2, get.call_count)
        self.assertEqual(1, sleep.call_count)

    def test_bioproject_esearch_fails_after_retries(self):
        with mock.patch.object(kingfisher.sra_metadata.requests, 'get',
                               return_value=FakeResponse(False, 'nope')) as get, \
                mock.patch.object(kingfisher.sra_metadata.time, 'sleep'):
            with self.assertRaises(Exception):
                SraMetadata().fetch_runs_from_bioprojects(['PRJEB15706'])
        self.assertEqual(3, get.call_count)


if __name__ == "__main__":
    unittest.main()
