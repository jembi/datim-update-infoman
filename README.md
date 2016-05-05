# datim-update-infoman-facilities
Datim script for updating OpenInfoMan resources from a spreadsheet.

# Usage
```
./resources/scripts/datim-update-infoman.py [OPTIONS...] CSV DIRECTORY_NAME
```
Updates OpenInfoMan with codes provided by a file in csv format. The `DIRECTORY_NAME` that needs to be updated in OpenInfoMan has to be specified.

`OPTIONS` are:
* `-h`: Print help and exit.
* `-f`: Do not resume partially processed files. Will start from the beginning.
* `-l`: Treat the first line as a row. Without this option the first line will be treated as a header and ignored.
* `-m PEPFAR_ID_COL`: The Pepfar ID column in the CSV. `1` indicates the first column. (Default: `1`)
* `-n LOCAL_ID_COL`: The Local ID column in the CSV. `1` indicates the first column. (Default: `2`)
* `-s SCHEMA`: The code schema to use for the local identifier. A default UUID will be used if not specified.
* `-t RESOURCE_TYPE`: The CSD resource type to update. Options are 'facility', 'organization', 'provider' and 'service'. The default is 'organization'.
* `-u URL`: The base URL to use for OpenInfoMan. Without this option, the value `http://localhost:8984/CSD` will be used.

# Getting and running the script
The script should work out-of-the-box on most Linux distributions and OS X (Windows users see [here](http://docs.python-guide.org/en/latest/starting/install/win/)). Simply grab the script and run:
```
wget https://raw.githubusercontent.com/jembi/datim-update-infoman/master/resources/scripts/datim-update-infoman.py
chmod +x resources/scripts/datim-update-infoman.py
./resources/scripts/datim-update-infoman.py -u http://my-infoman:8984/CSD -s uuid:me:localid -t facility updates.csv my-facilities
```

# CSV
The updates must be specified in a CSV file with the first column containing the Pepfar ID and the second column containing the local ID. The script will lookup the resource using the Pepfar ID and add an otherID to the resource with the local ID value.

The spreadsheet can have other columns - these will simply be ignored.

If the Pepfar and Local IDs are in different columns in your spreadsheet, use the `-m` and `-n` arguments to set the correct columns.

# Exporting a mapping document from the ILR

To export an initial mapping spreadsheet you may use a custom stored function in the ILR. Here is how to get started.

First you will have to have the `openinfoman-mapping` package installed in the ILR:

```sh
sudo add-apt-repository -y ppa:openhie/release
sudo apt-get update
sudo apt-get install openinfoman-mapping
```

You will be prompted to supply the correct `codingSchema` that you are using for local identifiers, which will change [line 30](https://github.com/jembi/datim-update-infoman/blob/master/export_organizations_to_csv.xml#L30) of the stored function.

To run without an interactive terminal, you can pass the `codingSchema` as a debconf argument:

```sh
echo 'update-infoman update-infoman/codingSchema string my-coding-schema' | sudo debconf-set-selections
sudo apt-get install openinfoman-mapping -y
```

Once that is done, you can export the mapping spreadsheet by executing the following:

```sh
curl -X POST http://<your_server>:8984/CSD/csr/<the_csd_document>/careServicesRequest/urn:datim.org:export-mapping-csv > mapping.csv
```
