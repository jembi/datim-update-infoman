#!/usr/bin/env python

# Only import from the python standard library.
#
# Since this is a simple standalone script,
# we want to make it easy for implementers to grab and run.
#
import sys
import os
import getopt
import urllib2
from xml.etree import ElementTree as ET
import contextlib


# which column to use for pepfar and local IDs (0-indexed; note that program args are 1-indexed)
DEFAULT_PEPFAR_ID_COL = 0
DEFAULT_LOCAL_ID_COL = 1

DEFAULT_URL = "http://localhost:8984/CSD"
DEFAULT_OTHERID_SCHEMA = "urn:uuid:2cec73f2-396f-4772-93e3-b26909387e63"

FACILITY = 'facility'
ORGANIZATION = 'organization'
PROVIDER = 'provider'
SERVICE = 'service'
DEFAULT_RESOURCE_TYPE = ORGANIZATION


USAGE = """Usage: ./datim-update-infoman.py [OPTIONS...] CSV DIRECTORY_NAME

Updates OpenInfoMan with codes provided by a file in csv format. The DIRECTORY_NAME that needs to be updated in OpenInfoMan has to be specified.

OPTIONS are:
    -h
        Print help and exit.
    -f
        Do not resume partially processed files. Will start from the beginning.
    -l
        Treat the first line as a row. Without this option the first line will be treated as a header and ignored.
    -m PEPFAR_ID_COL
        The Pepfar ID column in the CSV. '1' indicates the first column. (Default: 1)
    -n LOCAL_ID_COL
        The Local ID column in the CSV. '1' indicates the first column. (Default: 2)
    -s SCHEMA
        The code schema to use for the local identifier. A default UUID will be used if not specified.
    -t RESOURCE_TYPE
        The CSD resource type to update. Options are 'facility', 'organization', 'provider' and 'service'. The default is 'organization'.
    -u URL
        The base URL to use for OpenInfoMan. Without this option, the value 'http://localhost:8984/CSD' will be used.
"""

def print_usage_and_exit():
    print USAGE
    sys.exit()


ERROR = 0
SUCCESS = 1
WARN = 2
INFO = 3

def line_print(line_num, msg="", status=INFO):
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


RESOURCE_SEARCH = "%s/csr/%s/careServicesRequest/urn:ihe:iti:csd:2014:stored-function:%s-search"
RESOURCE_UPDATE = "%s/csr/%s/careServicesRequest/update/urn:openhie.org:openinfoman:%s_create"

RESOURCE_SEARCH_BODY = """
<requestParams xmlns="urn:ihe:iti:csd:2013">
  <id entityID="%s"/>
</requestParams>
"""

class RequestException(Exception): pass
class ContentException(Exception): pass

def lookup_csd_resource(base_url, resource_type, directory, entity_id):
    """Query OpenInfoMan for a resource with a particular entityID"""

    request_body = RESOURCE_SEARCH_BODY % (entity_id)
    req = urllib2.Request(RESOURCE_SEARCH % (base_url, directory, resource_type), data=request_body, headers={'content-type': 'text/xml'})

    with contextlib.closing(urllib2.urlopen(req)) as res:
        body = res.read()

        if res.code != 200: raise RequestException('Request to OpenInfoMan responded with status ' + str(res.code) + ': ' + body)
        if body.strip() == "": raise RequestException('Empty response from OpenInfoMan. Is a valid directory specified?')

        ET.register_namespace('', 'urn:ihe:iti:csd:2013')
        root = ET.fromstring(body)

        for child in root:
            if child.tag.endswith("%sDirectory" % (resource_type)):
                if len(child) >= 1:
                    return child[0]

        return None

def send_csd_resource_update(base_url, directory, request):
    """Send a resource update to OpenInfoMan"""

    req = urllib2.Request(RESOURCE_UPDATE % (base_url, directory, resource_type), data=request, headers={'content-type': 'text/xml'})

    with contextlib.closing(urllib2.urlopen(req)) as res:
        body = res.read()

        if res.code != 200: raise RequestException('Request to OpenInfoMan responded with status ' + str(res.code) + ': ' + body)


def process_resource_update(base_url, resource_type, directory, pepfar_id, local_id, otherid_schema):
    """Lookup a resource with a particular Pepfar ID and update it with a local ID"""

    resource = lookup_csd_resource(base_url, resource_type, directory, pepfar_id)
    if resource is None:
        raise ContentException('Could not find %s resource with entityID %s' % (resource_type, pepfar_id))

    # add a new <otherID> sub-element with the local ID
    ET.SubElement(resource, 'otherID', {'code': local_id, 'codingSchema': otherid_schema})
    updateRequest = ET.Element('requestParams')
    updateRequest.append(resource)

    # build CSD update request
    requestString = ET.tostring(updateRequest, encoding='utf-8')

    send_csd_resource_update(base_url, directory, requestString)


# Progress functions

# The script will (naively) try to resume a failed update by keeping a .file.csv.progress file.
# This file simply contains the line number of the last line processed without error.
# If the file exists, the update will be resumed from the line+1. If the entire update process finishes,
# the file will be removed, meaning that if the script were rerun it would start from the beginning.

resume_progress_file = lambda f: ".%s.progress" % (f)

def get_resume_line(csv_file):
    """Determine if the file should be resumed from a previous update, and if so which line"""

    if not os.path.isfile(resume_progress_file(csv_file)): return None

    with open(resume_progress_file(csv_file), 'r') as f:
        line = f.readline()
        line = line.strip()
        if line == '': return None
        return int(line)

def save_progress(csv_file, line):
    with open(resume_progress_file(csv_file), 'w') as f: f.write(str(line))

def clear_progress(csv_file):
    if os.path.isfile(resume_progress_file(csv_file)): os.remove(resume_progress_file(csv_file))

###


def process_csv_contents(csv_file, base_url, resource_type, directory, read_first_line, otherid_schema, pepfar_id_col, local_id_col, ignore_progress):
    print "Using OpenInfoMan instance %s and directory %s" % (base_url, directory)

    resume_line = get_resume_line(csv_file) if not ignore_progress else None
    if resume_line:
        print "Resuming CSV %s ..." % (csv_file)
    else:
        print "Processing CSV %s ..." % (csv_file)
    print

    with open(csv_file, 'r') as f:
        line_num=1

        for line in f:
            if resume_line and line_num <= resume_line:
                pass
            elif line_num == 1 and not read_first_line:
                line_print(line_num, "Skipping header")
            else:
                row = split_csv_line(line)

                if len(row) <= max(pepfar_id_col, local_id_col) or row[pepfar_id_col] == '' or row[local_id_col] == '':
                    line_print(line_num, "Invalid content", WARN)
                else:
                    try:
                        process_resource_update(base_url, resource_type, directory, row[pepfar_id_col], row[local_id_col], otherid_schema)
                        line_print(line_num, 'Updated', SUCCESS)
                    except ContentException as e:
                        line_print(line_num, e.message, WARN)
                    except RequestException as e:
                        line_print(line_num, e.message, ERROR)
                        sys.exit(1)
                    except urllib2.URLError as e:
                        line_print(line_num, "Failed to connect to OpenInfoMan host - " + str(e.reason), ERROR)
                        sys.exit(1)

            save_progress(csv_file, line_num)
            line_num = line_num+1

        clear_progress(csv_file)
        print
        print "Done"



if __name__ == "__main__":
    base_url = DEFAULT_URL
    resource_type = DEFAULT_RESOURCE_TYPE
    otherid_schema = DEFAULT_OTHERID_SCHEMA
    read_first_line = False
    pepfar_id_col = DEFAULT_PEPFAR_ID_COL
    local_id_col = DEFAULT_LOCAL_ID_COL
    ignore_progress = False

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hflm:n:s:t:u:")
    except getopt.GetoptError:
        print_usage_and_exit()

    for opt, arg in opts:
        if opt == '-h':
            print_usage_and_exit()
        if opt == '-f':
            ignore_progress = True
        elif opt == '-l':
            read_first_line = True
        elif opt == '-m':
            pepfar_id_col = int(arg)-1
        elif opt == '-n':
            local_id_col = int(arg)-1
        elif opt == '-s':
            otherid_schema = arg
        elif opt == '-t':
            if arg not in [FACILITY, ORGANIZATION, PROVIDER, SERVICE]:
                print "Unknown resource type: " + arg
                sys.exit(1)
            resource_type = arg
        elif opt == '-u':
            base_url = arg

    if len(args) <= 1: print_usage_and_exit()
    
    csv_file = args[0]
    directory = args[1]
    process_csv_contents(csv_file, base_url, resource_type, directory, read_first_line, otherid_schema, pepfar_id_col, local_id_col, ignore_progress)
