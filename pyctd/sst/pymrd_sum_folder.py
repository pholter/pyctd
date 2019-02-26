from . import pymrd as pymrd
import glob
import fnmatch
import os
import sys
import numpy
import argparse
import logging
import pkg_resources
import yaml
from pytz import timezone
import datetime


# Get the version
version_file = pkg_resources.resource_filename('pyctd','VERSION')

with open(version_file) as version_f:
   version = version_f.read().strip()

try:
    from pyproj import Geod
    FLAG_PYPROJ=True
    g = Geod(ellps='WGS84')
except:
    FLAG_PYPROJ=False

# Setup logging module
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
logger = logging.getLogger('pymrd_sum_folder')


def get_stations():
    stations_file = pkg_resources.resource_filename('pycnv', 'stations/iow_stations.yaml')
    f_stations = open(stations_file)
    # use safe_load instead load
    stations_yaml = yaml.safe_load(f_stations)
    return stations_yaml['stations']


def get_all_valid_files(DATA_FOLDER, loglevel = logging.INFO, station = None, save_summary = False, status_function = None):
    """
    Args:
       DATA_FOLDER: Either list of data_folder or string of one data_folder
       station: MSS cast has to lie within radius around position, given as a list with longitude [decdeg], latitude [decdeg], radius [m], e.g. [20.0,54.0,5000]
       status_function: A function that is called during reading, the function is called with the current filenumber i, the total number of files nf and the filename f, e.g. function(i,nf,f) 
    Returns:
        Dictionary with data
    """

    if(isinstance(DATA_FOLDER, str)):
        DATA_FOLDER = [DATA_FOLDER]
    if station == None:
        FLAG_DIST = False
    else:
        londist   = station[0]
        latdist   = station[1]
        distdist  = station[2]
        FLAG_DIST = True

    #
    # Loop through all subfolders
    #
    matches = []
    for DATA_P in DATA_FOLDER:
        for root, dirnames, fnames in os.walk(DATA_P):
            #print(root,dirnames,fnames)
            for fname in fnmatch.filter(fnames, '*.mrd'):
                matches.append(os.path.join(root, fname))
                #print(matches[-1])
                if(numpy.mod(len(matches),100) == 0):
                    logger.info('Found ' + str(len(matches)) + ' files')

            for fname in fnmatch.filter(fnames, '*.MRD'):
                matches.append(os.path.join(root, fname))
                if(numpy.mod(len(matches),100) == 0):
                    logger.info('Found ' + str(len(matches)) + ' files')
                #print(matches[-1])        


    logger.info('Found ' + str(len(matches)) + ' mrd files in folder(s):' + str(DATA_FOLDER))
    if(len(matches) == 0):
        return {'files':[],'dates':[],'lon':[],'lat':[],'info_dict':[]}
    save_file       = []
    files_date      = []
    file_names_save = []
    files_lon_save  = []
    files_lat_save  = []        
    files_date_save = []
    files_summary   = []
    files_info_dict = []
    
    if(len(matches) > 0):
        # Write the header of the file
        print('Hallo',matches[0])
        mrd = pymrd(matches[0],verbosity=logging.CRITICAL,only_metadata = True)

        # Loop through all files and make summary
        nf = len(matches)
        for i,f in enumerate(matches):
            logger.info('Reading file ' + str(i) +'/' + str(nf) + ': ' + str(f))
            if(status_function is not None): # At the moment used for gui
                print('Status function')
                status_function(i,nf,f)
                
            mrd = pymrd(f,verbosity=loglevel,only_metadata = True)
            if(mrd.valid_mrd):
                files_date.append(mrd.date)
                files_info_dict.append(mrd.get_info_dict())
                #summary = mrd.get_summary()
                FLAG_GOOD = False
                # Check if we are within a distance
                lon = mrd.lon
                lat = mrd.lat                
                if(FLAG_DIST):
                    if(not(numpy.isnan(lon)) and not(numpy.isnan(lat))):
                        az12,az21,dist = g.inv(lon,lat,londist,latdist)
                        if(dist < distdist):
                            FLAG_GOOD = True

                else:
                    FLAG_GOOD = True

                if(FLAG_GOOD):
                    save_file.append(True)
                    file_names_save.append(f)
                    files_date_save.append(mrd.date)
                    files_lon_save.append(lon)
                    files_lat_save.append(lat)
                    #files_summary.append(summary)
                else:
                    save_file.append(False)

        # Save the with respect to date sorted file
        logger.info('Sorting all files')
        print(files_lon_save)
        # Replace invalid dates with an obviously wrong date to be able to sort them
        for i in range(len(files_date_save)):
            if(files_date_save[i] == None):
                files_date_save[i] = datetime.datetime(1,1,1).replace(tzinfo=timezone('UTC'))

        ind_sort = numpy.argsort(files_date_save)                
        file_names_save_sort = list(numpy.asarray(file_names_save)[ind_sort])
        retdata  = {'files':file_names_save_sort,'dates':list(numpy.asarray(files_date_save)[ind_sort]),'lon':list(numpy.asarray(files_lon_save)[ind_sort]),'lat':list(numpy.asarray(files_lat_save)[ind_sort]),'info_dict':list(numpy.asarray(files_info_dict)[ind_sort])}

        print(retdata)
        if save_summary:
            summary_array = numpy.asarray(files_summary)[ind_sort]
            retdata['summary'] = summary_array
        
        return retdata
