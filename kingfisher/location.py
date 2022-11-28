import logging
import json
import re

import extern

from .exception import DownloadMethodFailed


class Location:
    @staticmethod
    def get_ncbi_locations(run_id):
        json_location_string = 'https://locate.ncbi.nlm.nih.gov/sdl/2/retrieve?&acc={}&accept-alternate-locations=yes'.format(
            run_id)
        json_response = extern.run('curl -q \'{}\''.format(json_location_string))
        logging.debug("Got location JSON: {}".format(json_response))

        j = json.loads(json_response)
        if 'version' not in j or j['version'] != '2':
            raise Exception(
                "Unexpected json location string returned: {}", json_location_string)
        # TODO: Assumes there is only 1 result, which is all I've ever seen
        return NcbiLocationJson(j)


class AwsLocation:
    def __init__(self, object_json, location_json):
        self.object_json = object_json
        self.j = location_json

    def service(self):
        if self.j['service'] == 's3':
            # The run ERR209516 for instance is non-ODP at s3://sra-pub-run-3/ERR209516/ERR209516.2
            # whereas SRR12324253 is Open Data, at https://sra-pub-run-odp.s3.amazonaws.com/sra/SRR12324253/SRR12324253
            # SRR12316190 is https://sra-pub-sars-cov2.s3.amazonaws.com/run/SRR12316190/SRR12316190
            if 'sra-pub-run-odp' in self.j['link']:
                return 's3-odp'
            elif 'sra-pub-sars-cov2' in self.j['link']:
                return 's3-sars-cov2'
            else:
                return 's3-pay'
        else:
            raise Exception("Programming error: {}".format(self.j))

    def s3_command_prefix(self, run_id):
        if self.service() == 's3-pay':
            # bucket/key not present in paid link from
            # 'https://locate.ncbi.nlm.nih.gov/sdl/2/retrieve?&acc=ERR209516&accept-alternate-locations=yes'
            # for instance.
            if 'bucket' in self.j and 'key' in self.j:
                # Below return is not tested currently, because I do not currently
                # know of an SRA accession that falls into this category.
                return 'aws s3 cp s3://{}/{}'.format(self.j['bucket'], self.j['key'])
            else:
                raise DownloadMethodFailed("Unexpected form of S3 location JSON: {}".format(self.j))
                # elif 'link' in self.j:
                # E.g. SRR16940109 is currently:
                # {
                #     "service": "s3",
                #     "region": "us-east-1",
                #     "payRequired": true,
                #     "link": "https://sra-pub-run-6.s3.amazonaws.com/SRR16940109/SRR16940109.1"
                # }
                # => That link is currently not available
            
        elif self.service() == 's3-odp':
            # Use --no-sign-request to avoid the AWS CLI signing into an
            # account, avoiding potential usage charges. There is a possibility
            # here that a non-ODP link is specified in the location API, but
            # this will only case an error since we are using --no-sign-request.
            return 'aws s3 cp --no-sign-request s3://sra-pub-run-odp/sra/{}/{}'.format(run_id, run_id)
        elif self.service() == 's3-sars-cov2':
            return 'aws s3 cp --no-sign-request s3://sra-pub-sars-cov2/run/{}/{}'.format(run_id, run_id)
        else:
            raise Exception("Unexpected json location found: {}", self.j)

    def link(self):
        return self.j['link']

    def md5sum(self):
        return self.object_json['md5']


class GcpLocation:
    def __init__(self, object_json, location_json):
        self.object_json = object_json
        self.j = location_json

    def gs_path(self):
        if 'rehydrationRequired' in self.j and self.j['rehydrationRequired'] == True:
            raise DownloadMethodFailed("Rehydration required from GCP, so ignoring")
        elif 'key' in self.j and 'bucket' in self.j:
            # Possibly now outdated and this branch is never used?
            return 'gs://{}/{}'.format(self.j['bucket'], self.j['key'])
        elif 'link' in self.j:
            r = re.compile('https://storage.googleapis.com/(.*?)/(.*)')
            m = r.match(self.j['link'])
            if m is None:
                raise DownloadMethodFailed("Unexpected GCP link URL in {}".format(self.j))
            else:
                return 'gs://{}/{}'.format(m[1],m[2])
        else:
            raise DownloadMethodFailed("Unsure how to copy from GCP location {}".format(self.j))

    def md5sum(self):
        return self.object_json['md5']


class NcbiLocationJson:
    OBJECT_TYPE_SRA = 'sra-qual'
    OBJECT_TYPE_SRA_NOQUAL = 'sra-noqual'

    GCP_SERVICE = 'gs-service'
    AWS_SERVICE = 's3-service'

    def __init__(self, j):
        self.j = j

    def object_locations(self, object_type, service, allow_paid):
        # First get a set of objects that are suitable
        passable_objects = []
        if 'files' not in self.j['result'][0]:
            error_msg = "No results returned from NCBI location API"
            if 'msg' in self.j['result'][0]:
                error_msg += ". msg was '{}'".format(self.j['result'][0]['msg'])
            logging.warning(error_msg)
            return []
        for obj in self.j['result'][0]['files']:
            if obj['type'] == 'sra':
                if obj['name'].endswith('.noqual'):
                    if object_type == NcbiLocationJson.OBJECT_TYPE_SRA_NOQUAL:
                        passable_objects.append(obj)
                else:
                    if object_type == NcbiLocationJson.OBJECT_TYPE_SRA:
                        passable_objects.append(obj)
        # Then get a set of locations of those objects that suit
        passable_objects_and_locations = []
        for obj in passable_objects:
            for loc in obj['locations']:
                logging.debug("Assessing location {}".format(loc))
                if 'payRequired' in loc and loc['payRequired'] != False and allow_paid != True:
                    # Payment is required but we aren't allow-paid
                    logging.debug("Excluding location as we aren't paid: {}".format(loc))
                    continue
                elif service == NcbiLocationJson.GCP_SERVICE:
                    if loc['service'] == 'gs':
                        logging.debug("Accepting location")
                        passable_objects_and_locations.append(GcpLocation(obj, loc))
                    else:
                        logging.debug("Location has the wrong service")
                elif service == NcbiLocationJson.AWS_SERVICE:
                    if loc['service'] == 's3':
                        logging.debug("Accepting location")
                        passable_objects_and_locations.append(AwsLocation(obj, loc))
                    else:
                        logging.debug("Location has the wrong service")
                else:
                    logging.debug("Discarding location as unsuitable: {}".format(loc))
        return passable_objects_and_locations