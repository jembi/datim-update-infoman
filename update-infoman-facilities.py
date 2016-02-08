#!/usr/bin/env python

# Only import from the python standard library.
#
# Since this is a simple standalone script,
# we want to make it easy for implementers to grab and run.
#
import sys
import getopt
import urllib2
from xml.etree import ElementTree as ET
import contextlib


# which column to use for pepfar and local IDs (0-indexed; note that program args are 1-indexed)
DEFAULT_PEPFAR_ID_COL=0
DEFAULT_LOCAL_ID_COL=1

DEFAULT_URL="http://localhost:8984/CSD"
DEFAULT_OTHERID_SCHEMA="urn:uuid:2cec73f2-396f-4772-93e3-b26909387e63"


usage_msg = """Usage: ./update-infoman-faclities.py [OPTIONS...] CSV DIRECTORY_NAME
Updates OpenInfoMan with facility codes provided by a file in csv format. The DIRECTORY_NAME that needs to be updated in OpenInfoMan has to be specified.
OPTIONS are:
    -h
        Print help and exit.
    -l
        Treat the first line as a row. Without this option the first line will be treated as a header and ignored.
    -m PEPFAR_ID_COL
        The Pepfar ID column in the CSV. '1' indicates the first column. (Default: 1)
    -n LOCAL_ID_COL
        The Local ID column in the CSV. '1' indicates the first column. (Default: 2)
    -s SCHEMA
        The code schema to use for the local identifier. A default UUID will be used if not specified.
    -u URL
        The base URL to use for OpenInfoMan. Without this option, the value 'http://localhost:8984/CSD' will be used.
"""

def print_usage_and_exit():
    print usage_msg
    sys.exit()


ERROR=0
SUCCESS=1
WARN=2

def line_print(line_num, msg="", status=-1):
    """Print a message for the current line"""

    if status == ERROR:
        _stat = "\x1b[31mError\x1b[0m"
    elif status == SUCCESS:
        _stat = "\x1b[32mSuccess\x1b[0m"
    elif status == WARN:
        _stat = "\x1b[33mWarn\x1b[0m"
    else:
        _stat = "Info"

    print "[%s] line %s: %s" % (_stat, line_num, msg)


def split_csv_line(line):
    """Split a CSV row on comma delimiters"""

    line = line.rstrip() 

    split = []
    token = ''
    in_quotes = 0
    is_in_quotes = lambda: in_quotes%2 == 1

    for c in line:
        if c == '"':
            in_quotes = in_quotes+1
            continue

        if c == ',' and not is_in_quotes():
            split.append(token)
            token = ''
        else:
            token = token + c

    if len(token)>0: split.append(token)

    return split


FACILITY_SEARCH = "%s/csr/%s/careServicesRequest/urn:ihe:iti:csd:2014:stored-function:facility-search"
FACILITY_UPDATE = "%s/csr/%s/careServicesRequest/update/urn:openhie.org:openinfoman:facility_create"

FACILITY_SEARCH_BODY = """
<requestParams xmlns="urn:ihe:iti:csd:2013">
  <id entityID="%s"/>
</requestParams>
"""

class RequestException(Exception): pass
class ContentException(Exception): pass

def lookup_csd_facility(base_url, directory, entity_id):
    request_body = FACILITY_SEARCH_BODY % (entity_id)
    req = urllib2.Request(FACILITY_SEARCH % (base_url, directory), data=request_body, headers={'content-type': 'text/xml'})

    with contextlib.closing(urllib2.urlopen(req)) as res:
        body = res.read()

        if res.code != 200: raise RequestException('Request to OpenInfoMan responded with status ' + str(res.code) + ': ' + body)
        if body.strip() == "": raise RequestException('Empty response from OpenInfoMan. Is a valid directory specified?')

        root = ET.fromstring(body)
        for child in root:
            if child.tag.endswith('facilityDirectory'):
                if len(child) >= 1:
                    return child[0]

        return None

def send_csd_facility_update(base_url, directory, request):
    req = urllib2.Request(FACILITY_UPDATE % (base_url, directory), data=request, headers={'content-type': 'text/xml'})

    with contextlib.closing(urllib2.urlopen(req)) as res:
        body = res.read()

        if res.code != 200: raise RequestException('Request to OpenInfoMan responded with status ' + str(res.code) + ': ' + body)


def process_facility_update(base_url, directory, pepfar_id, local_id, otherid_schema):
    facility = lookup_csd_facility(base_url, directory, pepfar_id)
    if facility is None:
        raise ContentException('Could not find facility with entityID ' + pepfar_id)

    ET.SubElement(facility, 'otherID', {'code': local_id, 'codingSchema': otherid_schema})
    updateRequest = ET.Element('requestParams')
    updateRequest.append(facility)
    requestString = ET.tostring(updateRequest, encoding='utf-8')
    send_csd_facility_update(base_url, directory, requestString)

def process_csv_contents(csv_file, base_url, directory, read_first_line, otherid_schema, pepfar_id_col, local_id_col):
    print "Using OpenInfoMan instance " + base_url
    print "Processing CSV %s ..." % (csv_file)

    with open(csv_file, 'r') as f:
        line_num=0
        first_line=not read_first_line

        for line in f:
            if first_line == True:
                first_line = False
            else:
                row = split_csv_line(line)

                if len(row) <= max(pepfar_id_col, local_id_col) or row[pepfar_id_col] == '' or row[local_id_col] == '':
                    line_print(line_num, "invalid content", WARN)
                else:
                    try:
                        process_facility_update(base_url, directory, row[pepfar_id_col], row[local_id_col], otherid_schema)
                    except ContentException as e:
                        line_print(line_num, e.message, WARN)
                    except RequestException as e:
                        line_print(line_num, e.message, ERROR)
                        sys.exit(1)
                    except urllib2.URLError as e:
                        line_print(line_num, "Failed to connect to OpenInfoMan host - " + str(e.reason), ERROR)
                        sys.exit(1)

            line_num = line_num+1



if __name__ == "__main__":
    base_url=DEFAULT_URL
    otherid_schema = DEFAULT_OTHERID_SCHEMA
    read_first_line = False
    pepfar_id_col = DEFAULT_PEPFAR_ID_COL
    local_id_col = DEFAULT_LOCAL_ID_COL

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hlm:n:s:u:")
    except getopt.GetoptError:
        print_usage_and_exit()

    for opt, arg in opts:
        if opt == '-h':
            print_usage_and_exit()
        elif opt == '-l':
            read_first_line = True
        elif opt == '-m':
            pepfar_id_col = int(arg)-1
        elif opt == '-n':
            local_id_col = int(arg)-1
        elif opt == '-s':
            otherid_schema = arg
        elif opt == '-u':
            base_url = arg

    if len(args) <= 1: print_usage_and_exit()
    
    process_csv_contents(args[0], base_url, args[1], read_first_line, otherid_schema, pepfar_id_col, local_id_col)
