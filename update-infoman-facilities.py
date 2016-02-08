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


# which column to use for pepfar and local IDs
PEPFAR_ID_COL=0
LOCAL_ID_COL=1

DEFAULT_URL="http://localhost:8984/CSD"


usage_msg = """Usage: $0 [OPTIONS...] CSV
Updates OpenInfoMan with facility codes provided by a file in csv format.
OPTIONS are:
    -h
        Print help and exit.
    -l
        Treat the first line as a row. Without this option the first line will be treated as a header and ignored.
    -u
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


FACILITY_SEARCH = "/csr/CSD-Facilities-Connectathon-20150120/careServicesRequest/urn:ihe:iti:csd:2014:stored-function:facility-search"
FACILITY_UPDATE = "/csr/CSD-Facilities-Connectathon-20150120/careServicesRequest/update/urn:openhie.org:openinfoman:facility_create"

FACILITY_SEARCH_BODY = """
<requestParams xmlns="urn:ihe:iti:csd:2013">
  <id entityID="%s"/>
</requestParams>
"""

class RequestException(Exception): pass
class ContentException(Exception): pass

def lookup_csd_facility(base_url, entity_id):
    request_body = FACILITY_SEARCH_BODY % (entity_id)
    req = urllib2.Request(base_url+FACILITY_SEARCH, data=request_body, headers={'content-type': 'text/xml'})

    with contextlib.closing(urllib2.urlopen(req)) as res:
        body = res.read()

        if res.code != 200: raise RequestException('Request to OpenInfoMan responded with status ' + str(res.code) + ': ' + body)

        root = ET.fromstring(body)
        for child in root:
            if child.tag.endswith('facilityDirectory'):
                if len(child) >= 1:
                    return child[0]

        return None

def send_csd_facility_update(base_url, request):
    req = urllib2.Request(base_url+FACILITY_UPDATE, data=request, headers={'content-type': 'text/xml'})

    with contextlib.closing(urllib2.urlopen(req)) as res:
        body = res.read()

        if res.code != 200: raise RequestException('Request to OpenInfoMan responded with status ' + str(res.code) + ': ' + body)


def process_facility_update(base_url, pepfar_id, local_id):
    facility = lookup_csd_facility(base_url, pepfar_id)
    if facility is None:
        raise ContentException('Could not find facility with entityID ' + pepfar_id)

    ET.SubElement(facility, 'otherID', {'code': local_id, 'codingSchema': 'TODO'})
    updateRequest = ET.Element('requestParams')
    updateRequest.append(facility)
    requestString = ET.tostring(updateRequest, encoding='utf-8')
    send_csd_facility_update(base_url, requestString)

def process_csv_contents(args, base_url, read_first_line=False):
    print "Using OpenInfoMan instance " + base_url
    print "Processing CSV %s ..." % (args[0])

    with open(args[0], 'r') as f:
        line_num=0
        first_line=not read_first_line

        for line in f:
            if first_line == True:
                first_line = False
            else:
                row = split_csv_line(line)

                if len(row) <= max(PEPFAR_ID_COL, LOCAL_ID_COL) or row[PEPFAR_ID_COL] == '' or row[LOCAL_ID_COL] == '':
                    line_print(line_num, "invalid content", WARN)
                else:
                    try:
                        process_facility_update(base_url, row[PEPFAR_ID_COL], row[LOCAL_ID_COL])
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
    read_first_line = False

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hlu:")
    except getopt.GetoptError:
        print_usage_and_exit()

    for opt, arg in opts:
        if opt == '-h':
            print_usage_and_exit()
        elif opt == '-l':
            read_first_line = True
        elif opt == '-u':
            base_url = arg

    if len(args) == 0: print_usage_and_exit()
    
    process_csv_contents(args, base_url, read_first_line)
