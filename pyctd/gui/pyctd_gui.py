from pycnv import pycnv, pycnv_sum_folder
from pysst import pymrd as pymrd
from pysst import pymrd_sum_folder as pymrd_sum_folder
import sys
import os
import logging
import argparse
import time
import locale
import yaml
import pkg_resources
import datetime
import pytz
import copy
import pkg_resources
import re
import numpy as np
import geojson
from pytz import timezone

# Get the version
version_file = pkg_resources.resource_filename('pyctd','VERSION')
# Get the ships
ship_file = pkg_resources.resource_filename('pyctd', 'ships/ships.yaml')
sfile = open(ship_file, 'r')
ships = yaml.safe_load(sfile)
sfile.close()

with open(version_file) as version_f:
   version = version_f.read().strip()

try:
    from PyQt5 import QtCore, QtGui, QtWidgets
except:
    from qtpy import QtCore, QtGui, QtWidgets

# For the map plotting
import pylab as pl
import cartopy
import cartopy.crs as ccrs
from cartopy.io import shapereader
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER    
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure


def str_to_time(timestr):
    """ Converts a timestr to a datetime object
    Args:
        timestr: The timestr
    Returns:
        List with first entry a boolean if the conversion was sucessfull and a second entry the datetime object
    """
    good_time = False
    try:
        d = datetime.datetime.strptime(timestr,'%Y-%m-%d %H:%M:%S')
        d = d.replace(tzinfo=timezone('UTC'))
        good_time = True
    except Exception as e:
        print(e)
        d = None

    print('d',d)
    return [good_time,d]
        

def create_geojson_summary(summary,filename,name='CTD',properties='all'):
    """ Creates a geojson summary
    """
    print('Create geojson summary in file:' + filename)
    crs = { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } } # Reference coordinate system

    #['date','lon','lat','station','campaign','file','comment']
    if(properties == 'all'):
        try:
            properties = summary['casts'][0].keys()
        except:
            properties = []

        try:
            properties_stations = summary['stations'][0].keys()
        except:
            properties_stations = []

        try:
            properties_transects = summary['transects'].keys()
        except:
            properties_transects = []                        

    
    filename_ctd       = filename.replace('.geojson','') + '_CTD_casts.geojson'
    filename_stations  = filename.replace('.geojson','') + '_stations.geojson'
    filename_transects = filename.replace('.geojson','') + '_transects.geojson'    
    
    if(len(properties) > 0):
        features = []
        print(properties)
        for i,d in enumerate(summary['casts']):
            print(d)
            csv_line = ''
            lon = d['lon']
            lat = d['lat']
            p = geojson.Point((lon, lat))
            prop = {}
            for o in properties:
                if(o in d):
                    prop[o] = d[o]
                else: # Property not there, e.g. station not existing in MRD files.
                    pass

            feature = geojson.Feature(geometry=p, properties=prop)
            features.append(feature)

        featurecol = geojson.FeatureCollection(features,name=name,crs=crs)
        with open(filename_ctd, 'w') as outfile:
            geojson.dump(featurecol, outfile)

        outfile.close()

    if(len(properties_stations) > 0):
        features_stations = []
        for i,d in enumerate(summary['stations']):
            csv_line = ''
            lon = d['lon']
            lat = d['lat']
            p = geojson.Point((lon, lat))
            prop = {}
            for o in properties_stations:
                prop[o] = d[o]

            feature = geojson.Feature(geometry=p, properties=prop)
            features_stations.append(feature)
            
        featurecol_stations = geojson.FeatureCollection(features_stations,name='stations',crs=crs)
        with open(filename_stations, 'w') as outfile:
            geojson.dump(featurecol_stations, outfile)
            
        outfile.close()

    if(len(properties_transects) > 0):
        features_transects = []
        #self.tran['name']          
        #self.tran['numbers']       
        #self.tran['station_names'] 
        #self.tran['station_lon']   
        #self.tran['station_lat']   
        for i,d in enumerate(summary['transects']['name']):
            lon   = summary['transects']['station_lon'][i]
            lat   = summary['transects']['station_lat'][i]
            ps = []            
            for k in range(len(lon)):
                ps.append((lon[k], lat[k]))

            gl = geojson.LineString(ps)                          
            prop = {'name':summary['transects']['name'][i]}

            feature = geojson.Feature(geometry=gl, properties=prop)
            features_transects.append(feature)
            
        featurecol_transects = geojson.FeatureCollection(features_transects,name='transects',crs=crs)
        with open(filename_transects, 'w') as outfile:
            geojson.dump(featurecol_transects, outfile)
            
        outfile.close()        


def create_yaml_summary(summary,filename):
    """ Creates a yaml summary
    """
    if ('.yaml' not in filename):
        filename += '.yaml'
        
    print('Create yaml summary in file:' + filename)
    with open(filename, 'w') as outfile:
        yaml.dump(summary, outfile, default_flow_style=False)


def create_csv_summary(summary,filename,order=['date','lon','lat','station','file','comment']):
    """ Creates a csv summary
    """
    print('Create csv summary in file:' + filename)
    print(summary)
    try:
        outfile = open(filename, 'w')
    except Exception as e:
        return
    
    csv_line = ''
    for o in order:
        csv_line += str(o) +','

    csv_line = csv_line[:-2]
    outfile.write(csv_line)
    for i,d in enumerate(summary['casts']):
        csv_line = ''
        for o in order:
            csv_line += str(d[o]) +','

        csv_line = csv_line[:-2] + '\n'
        outfile.write(csv_line)        
        #print(csv_line)

    outfile.close()

class get_valid_files(QtCore.QThread):
    """ A thread to search a directory for valid files
    Arguments:
       foldername:
       search_seabird: 
       search_mrd:
       start_time: type datetime
       stop_time: type datetime
       station: 
    """
    search_status = QtCore.pyqtSignal(object,int,int,str) # Create a custom signal
    def __init__(self, foldername, search_seabird = True, search_mrd = True, start_time = None, stop_time = None, station = None):
        QtCore.QThread.__init__(self)
        self.foldername = foldername
        self.search_seabird = search_seabird
        self.search_mrd = search_mrd
        self.start_time = start_time
        self.stop_time  = stop_time
        self.station    = station
        #print('Search seabird',self.search_seabird)        
        #print('Search MRD',self.search_mrd)
        
    def __del__(self):
        self.wait()

    def run(self):
        # your logic here
        #pycnv_sum_folder.get_all_valid_files(foldername,status_function=self.status_function)
        #https://stackoverflow.com/questions/39658719/conflict-between-pyqt5-and-datetime-datetime-strptime
        locale.setlocale(locale.LC_TIME, "C")
        
        if((type(self.start_time) == datetime.datetime)):
            start_time = self.start_time
        else:
            start_time = None

        if((type(self.stop_time) == datetime.datetime)):
            stop_time = self.stop_time
        else:
            stop_time = None            
            
        data_tmp = pycnv_sum_folder.get_all_valid_files(self.foldername,loglevel = logging.WARNING,status_function=self.status_function, station = self.station,start_time = start_time,stop_time=stop_time)
        self.data = data_tmp
        if(self.search_mrd):
            #print('Search for SST files')
            data_tmp = pymrd_sum_folder.get_all_valid_files(self.foldername,loglevel = logging.WARNING,status_function=self.status_function)
            if True:
                for key in self.data.keys():
                    self.data[key].extend(data_tmp[key])
        
        
    def status_function(self,i,nf,f):
        self.search_status.emit(self,i,nf,f)


class casttableWidget(QtWidgets.QTableWidget,):
    plot_signal = QtCore.pyqtSignal(object,str) # Create a custom signal for plotting
    station_signal = QtCore.pyqtSignal(object) # Create a custom signal for adding the cast to station
    remstation_signal = QtCore.pyqtSignal(object) # Create a custom signal for removing the cast to station
    campaign_signal = QtCore.pyqtSignal(object) # Create a custom signal for adding the cast to campaign
    remcampaign_signal = QtCore.pyqtSignal(object) # Create a custom signal for removing the cast to campaign
    comment_signal = QtCore.pyqtSignal(object) # Create a custom signal for adding the cast to station
    
    def __init__(self, within_qgis=False):
        """ Changing the contextmenu if pyctd is used within qgis
        """
        self.within_qgis = within_qgis
        QtWidgets.QTableWidget.__init__(self)
        if self.within_qgis:
            self.addlayerAction = QtWidgets.QAction('Add to layer', self)        

    def contextMenuEvent(self, event):
        self.menu = QtWidgets.QMenu(self)
        plotAction = QtWidgets.QAction('Add to map', self)
        plotAction.triggered.connect(self.plot_map)
        stationAction = QtWidgets.QAction('Add to Station', self)
        stationAction.triggered.connect(self.station)
        stationRemAction = QtWidgets.QAction('Rem from Station', self)
        stationRemAction.triggered.connect(self.rem_station)
        campaignAction = QtWidgets.QAction('Add to Campaign', self)
        campaignAction.triggered.connect(self.campaign)
        campaignRemAction = QtWidgets.QAction('Rem from Campaign', self)
        campaignRemAction.triggered.connect(self.rem_campaign)                
        remplotAction = QtWidgets.QAction('Rem from map', self)
        remplotAction.triggered.connect(self.rem_from_map)
        plotcastAction = QtWidgets.QAction('Plot cast', self)
        plotcastAction.triggered.connect(self.plot_cast)

            
        self.menu.addAction(stationAction)
        self.menu.addAction(stationRemAction)
        self.menu.addAction(campaignAction)
        self.menu.addAction(campaignRemAction)                
        #self.menu.addAction(plotAction)
        #self.menu.addAction(remplotAction)
        #self.menu.addAction(plotcastAction)
        if self.within_qgis:
            self.menu.addAction(self.addlayerAction)            
            
        self.menu.popup(QtGui.QCursor.pos())
        self.menu.show()
        # Get selected rows (as information for plotting etc.)
        self.rows = set() # Needed for "unique" list
        for idx in self.selectedIndexes():
            self.rows.add(idx.row())

        self.rows = list(self.rows)
        #action = self.menu.exec_(QtGui.QCursor.pos())#self.mapToGlobal(event))

    def station(self):
        """ Signal for station
        """
        row_list = self.rows
        self.station_signal.emit(row_list) # Emit the signal with the row list and the command

    def rem_station(self):
        """ Signal for removing station
        """
        row_list = self.rows
        self.remstation_signal.emit(row_list) # Emit the signal with the row list and the command

    def campaign(self):
        """ Signal for campaign
        """
        row_list = self.rows
        self.campaign_signal.emit(row_list) # Emit the signal with the row list and the command
 
    def rem_campaign(self):
        """ Signal for removing campaign
        """
        row_list = self.rows
        self.remcampaign_signal.emit(row_list) # Emit the signal with the row list and the command                

    def plot_map(self):
        row_list = self.rows
        self.plot_signal.emit(row_list,'add to map') # Emit the signal with the row list and the command

    def rem_from_map(self):
        row_list = self.rows
        self.plot_signal.emit(row_list,'rem from map') # Emit the signal with the row list and the command

    def plot_cast(self):
        self.plot_signal.emit(self.currentRow(),'plot cast') # Emit the signal with the row list and the command



        

class mainWidget(QtWidgets.QWidget):
    def __init__(self,logging_level=logging.INFO,within_qgis = False):
        self.within_qgis = within_qgis
            
        QtWidgets.QWidget.__init__(self)
        self.folder_dialog = QtWidgets.QLineEdit(self)
        self.folder_dialog.setText(os.getcwd()) # Take the local directory as a start
        self.foldername = os.getcwd()        
        self.folder_button = QtWidgets.QPushButton('Choose Datafolder')
        self.folder_button.clicked.connect(self.folder_clicked)
        self.search_button = QtWidgets.QPushButton('Search for CTD files')
        self.search_button.clicked.connect(self.search_clicked)
        self.clear_table_button = QtWidgets.QPushButton('Clear table')
        self.clear_table_button.clicked.connect(self.clear_table_clicked)

        # The table with the casts
        self.file_table_widget = QtWidgets.QWidget() # The widget housing the file table and the clear button
        self.file_table_widget_layout = QtWidgets.QVBoxLayout(self.file_table_widget)
        self.file_table = casttableWidget(within_qgis=self.within_qgis) # QtWidgets.QTableWidget()
        self.file_table.plot_signal.connect(self.plot_signal) # Custom signal for plotting
        self.file_table.station_signal.connect(self.station_signal) # Custom signal for adding casts to station
        self.file_table.remstation_signal.connect(self.remstation_signal) # Custom signal for adding casts to station
        self.file_table.campaign_signal.connect(self.campaign_signal) # Custom signal for adding casts to campaign
        self.file_table.remcampaign_signal.connect(self.remcampaign_signal) # Custom signal for adding casts to campaign       
        self.file_table.cellChanged.connect(self.table_changed)
        
        self.columns                     = {}
        self.columns['date']             = 0
        self.columns['lon']              = 1
        self.columns['lat']              = 2
        self.columns['station (File)']   = 3
        self.columns['station (Custom)'] = 4
        self.columns['campaign']         = 5
        self.columns['comment']          = 6        
        self.columns['file']             = 7
        #self.columns['map']              = 8
        self._ncolumns = len(self.columns.keys())      
        # TODO, create column names according to the data structures
        self.file_table.setColumnCount(self._ncolumns)

        header_labels = [None]*self._ncolumns
        for key in self.columns.keys():
            ind = self.columns[key]
            header_labels[ind] = key[0].upper() + key[1:]

        self.file_table.setHorizontalHeaderLabels(header_labels)            
        for i in range(self._ncolumns):
            self.file_table.horizontalHeaderItem(i).setTextAlignment(QtCore.Qt.AlignHCenter)
            
        #self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.file_table.resizeColumnsToContents()        
        self.file_table_widget_layout.addWidget(self.file_table)
        self.file_table_widget_layout.addWidget(self.clear_table_button)

        # Station table widget setup
        self.setup_stations_widget()
        # Transect table widget setup
        self.setup_transect_widget()
        self.setup_campaign_widget()
        self.setup_plot_widget()
        self.setup_save_widget()        
        
        # Tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self.file_table_widget,'Casts')
        self.tabs.addTab(self.stations['station_widget'],'Stations')
        self.tabs.addTab(self.tran['widget'],'Transects')
        self.tabs.addTab(self.camp['widget'],'Campaigns')
        self.tabs.addTab(self.plot['widget'],'Plot')
        self.tabs.addTab(self.save['widget'],'Load/Save')        
        self.layout = QtWidgets.QGridLayout(self)
        self.layout.addWidget(self.folder_dialog,0,0)
        self.layout.addWidget(self.folder_button,0,1)
        self.layout.addWidget(self.search_button,1,0)
        self.layout.addWidget(self.tabs,2,0,1,2)
        #self.layout.addWidget(,3,0)


        self.FLAG_REL_PATH = True
        self.dpi       = 100
        self.data = {}
        self._cruise_fields = {}


        # Search options widget
        self.search_opts_widget      = QtWidgets.QWidget()
        layout       = QtWidgets.QGridLayout(self.search_opts_widget)
        self._search_opt_cnv = QtWidgets.QCheckBox('Seabird cnv')
        self._search_opt_mrd = QtWidgets.QCheckBox('Sea & Sun mrd')
        self._search_opt_cnv.toggle() # put in on
        self._search_opt_mrd.toggle() # put in on
        self._search_opt_start = QtWidgets.QLineEdit(self.search_opts_widget)
        self._search_opt_start.editingFinished.connect(self._check_search_input)
        self._search_opt_start_lastvalid = '0001-01-01 00:00:00'
        self._search_opt_start.setText(self._search_opt_start_lastvalid)
        self._search_opt_end   = QtWidgets.QLineEdit(self.search_opts_widget)
        self._search_opt_end.editingFinished.connect(self._check_search_input)
        self._search_opt_end_lastvalid = '3001-01-01 00:00:00'        
        self._search_opt_end.setText(self._search_opt_end_lastvalid)
        # Radius search
        self._search_opt_lonc  = QtWidgets.QLineEdit(self.search_opts_widget)
        self._search_opt_lonc.editingFinished.connect(self._check_search_input)        
        self._search_opt_latc  = QtWidgets.QLineEdit(self.search_opts_widget)
        self._search_opt_latc.editingFinished.connect(self._check_search_input)                
        self._search_opt_radius= QtWidgets.QLineEdit(self.search_opts_widget)
        self._search_opt_radius.editingFinished.connect(self._check_search_input)                        
        # Rectangle search
        self._search_opt_lonc0  = QtWidgets.QLineEdit(self.search_opts_widget)
        self._search_opt_lonc0.editingFinished.connect(self._check_search_input)        
        self._search_opt_latc0  = QtWidgets.QLineEdit(self.search_opts_widget)
        self._search_opt_latc0.editingFinished.connect(self._check_search_input)        
        self._search_opt_lonc1  = QtWidgets.QLineEdit(self.search_opts_widget)
        self._search_opt_lonc1.editingFinished.connect(self._check_search_input)        
        self._search_opt_latc1  = QtWidgets.QLineEdit(self.search_opts_widget)
        self._search_opt_latc1.editingFinished.connect(self._check_search_input)
        # Which position
        self._search_opt_pos = QtWidgets.QComboBox()
        self._search_opt_pos.addItem('None')        
        self._search_opt_pos.addItem('Station with radius')
        self._search_opt_pos.addItem('Rectangle')                
        layout.addWidget(self._search_opt_cnv,0,0,1,2)
        layout.addWidget(self._search_opt_mrd,1,0,1,2)
        layout.addWidget( QtWidgets.QLabel('Start time'),2,0)      
        layout.addWidget(self._search_opt_start,2,1)
        layout.addWidget( QtWidgets.QLabel('End time'),3,0)
        layout.addWidget(self._search_opt_end,3,1)
        layout.addWidget( QtWidgets.QLabel('Choose position type for search'),4,0)
        layout.addWidget(self._search_opt_pos,4,1)
        layout.addWidget( QtWidgets.QLabel('Position (Point with radius)'),5,0,1,4)        
        layout.addWidget( QtWidgets.QLabel('Longitude [decDeg]'),6,0)
        layout.addWidget( QtWidgets.QLabel('Latitude [decDeg]'),6,1)
        layout.addWidget( QtWidgets.QLabel('Radius [m]'),6,2)                
        layout.addWidget(self._search_opt_lonc,7,0)
        layout.addWidget(self._search_opt_latc,7,1)
        layout.addWidget(self._search_opt_radius,7,2)
        layout.addWidget( QtWidgets.QLabel('Position (Rectangle)'),8,0,1,4)        
        layout.addWidget( QtWidgets.QLabel('Longitude min [decDeg]'),9,0)
        layout.addWidget( QtWidgets.QLabel('Longitude max [decDeg]'),9,1)        
        layout.addWidget( QtWidgets.QLabel('Latitude min [decDeg]'),9,2)
        layout.addWidget( QtWidgets.QLabel('Latitude max [decDeg]'),9,3)
        layout.addWidget(self._search_opt_lonc0,10,0)
        layout.addWidget(self._search_opt_lonc1,10,1)        
        layout.addWidget(self._search_opt_latc0,10,2)
        layout.addWidget(self._search_opt_latc1,10,3)                
        
        self.search_opts_widget.hide()

        # Station/stations widget
        self._station_widget      = QtWidgets.QWidget()
        layout       = QtWidgets.QGridLayout(self._station_widget)
        self._new_station_edit = QtWidgets.QLineEdit(self)
        layout.addWidget(self._new_station_edit,0,0)
        #layout.addWidget(QtWidgets.QLabel('Station/Station name'),0,0)
        button_add = QtWidgets.QPushButton('Add Station')
        button_add.clicked.connect(self._station_add_to_cast)
        layout.addWidget(button_add,0,1)        
        self.station_combo = QtWidgets.QComboBox()
        self.station_combo.addItem('Remove')        
        layout.addWidget(self.station_combo,1,0,1,2)
        button_apply = QtWidgets.QPushButton('Apply')
        button_apply.clicked.connect(self._station_apply)
        button_cancel = QtWidgets.QPushButton('Close')
        button_cancel.clicked.connect(self._station_cancel)
        layout.addWidget(button_apply,2,0)
        layout.addWidget(button_cancel,2,1)        
        self._station_widget.hide()

        # Map plotting settings
        self._map_settings = {'res':'110m'}

    def _check_search_input(self):
        print('Input done')
        w = self.sender()
        if(( w == self._search_opt_start) or ( w == self._search_opt_end)):
            print('Time test')
            [good_time,t] = str_to_time(w.text())
            print([good_time,t])
            if(good_time == False):
                if(w == self._search_opt_start):
                    self._search_opt_start.setText(self._search_opt_start_lastvalid)                    
                if(w == self._search_opt_end):
                    self._search_opt_end.setText(self._search_opt_end_lastvalid)

            else:
                if(w == self._search_opt_start):                
                    self._search_opt_start_lastvalid = w.text()
                if(w == self._search_opt_end):                
                    self._search_opt_end_lastvalid = w.text()          
        else:
            try:
                float(w.text())
            except:
                w.setText('')
                
        print(w.text())
        
    def setup_plot_widget(self):
        self.plot = {}
        self.plot['widget'] = QtWidgets.QWidget()
        
    def setup_save_widget(self):
        self.save = {}
        self.save['widget'] = QtWidgets.QWidget()
        # TODO, do the layout right, it looks really bad at the moment
        self.save['save'] = QtWidgets.QPushButton('Save')
        self.save['save'].clicked.connect(self.save_all)
        width = self.save['save'].fontMetrics().boundingRect('Save').width() + 7
        self.save['save_geojson'] = QtWidgets.QPushButton('Export casts/stations/transects to geojson')
        self.save['save_geojson'].clicked.connect(self.save_geojson)        
        self.save['save_csv'] = QtWidgets.QPushButton('Export casts to csv')
        self.save['save_csv'].clicked.connect(self.save_csv)

        self.save['save'].setMaximumWidth(width)
        self.save['load'] = QtWidgets.QPushButton('Load')
        self.save['load'].clicked.connect(self.load_file)
        self.save['layout'] = QtWidgets.QGridLayout(self.save['widget'])
        self.save['layout'].addWidget(self.save['save'],0,0)
        self.save['layout'].addWidget(self.save['save_geojson'],1,0)                
        self.save['layout'].addWidget(self.save['save_csv'],2,0)        
        self.save['layout'].addWidget(self.save['load'],3,0)
        
    def setup_campaign_widget(self):
        self.camp = {}
        self.camp['widget'] = QtWidgets.QWidget()        
        self.camp['table']  = QtWidgets.QTableWidget()
        table_columns                     = {}
        table_columns['Name']             = 0        
        table_columns['Project']          = 1
        table_columns['Begin']            = 2
        table_columns['End']              = 3        
        table_columns['Contact (name)']   = 4
        table_columns['Contact (email)']  = 5
        self.camp['index_ship'] = 6
        i = self.camp['index_ship']
        # Add ship columns        
        for k in ships['ships'][0].keys():
            table_columns['Ship ' + k] = i
            i += 1
            
        table = self.camp['table']
        ncolumns = len(table_columns.keys())      
        table.setColumnCount(ncolumns)
        header_labels = [None] * ncolumns
        for key in table_columns.keys():
            ind = table_columns[key]
            header_labels[ind] = key[0].upper() + key[1:]

        table.setHorizontalHeaderLabels(header_labels)            
        for i in range(ncolumns):
            table.horizontalHeaderItem(i).setTextAlignment(QtCore.Qt.AlignHCenter)        
        
        self.camp['layout'] = QtWidgets.QGridLayout(self.camp['widget'])
        self.camp['table_nrows'] = 0            
        self.camp['add_button'] = QtWidgets.QPushButton('Add')
        self.camp['add_button'].clicked.connect(self._campaign_add_blank)
        self.camp['rem_button'] = QtWidgets.QPushButton('Rem')
        self.camp['rem_button'].clicked.connect(self._campaign_rem)
        self.camp['add_ship_button'] = QtWidgets.QPushButton('Add Ship')
        self.camp['add_ship_button'].clicked.connect(self._campaign_add_ship)
        self.camp['ship_combo'] = QtWidgets.QComboBox()
        self._populate_ship_combo()
        self.camp['layout'].addWidget(self.camp['table'],0,0,1,2)
        self.camp['layout'].addWidget(self.camp['add_button'],1,0)
        self.camp['layout'].addWidget(self.camp['rem_button'],1,1)
        self.camp['layout'].addWidget(self.camp['add_ship_button'],2,1)
        self.camp['layout'].addWidget(self.camp['ship_combo'],2,0)                        
        #self.tran['station_table'].cellChanged.connect(self._update_station_table)
        self.camp['table'].resizeColumnsToContents()        

    def setup_transect_widget(self):
        self.tran = {}
        self.tran['widget'] = QtWidgets.QWidget()        
        self.tran['table']  = QtWidgets.QTableWidget()
        self.tran['layout'] = QtWidgets.QGridLayout(self.tran['widget'])
        self.tran['layout'].addWidget(self.tran['table'])
        #self.tran['station_table'].cellChanged.connect(self._update_station_table)
        self.tran_dict = {}

    def setup_stations_widget(self):
        self.stations = {}
        self.stations['station_table']  = QtWidgets.QTableWidget()
        self.stations['station_table'].cellChanged.connect(self._update_station_table)
        station_columns                     = {}
        station_columns['name']             = 0        
        station_columns['lon']              = 1
        station_columns['lat']              = 2
        station_columns['description']      = 3
        table = self.stations['station_table']
        ncolumns = len(station_columns.keys())      
        # TODO, create column names according to the data structures
        table.setColumnCount(ncolumns)

        header_labels = [None]*ncolumns
        for key in station_columns.keys():
            ind = station_columns[key]
            header_labels[ind] = key[0].upper() + key[1:]

        table.setHorizontalHeaderLabels(header_labels)            
        for i in range(ncolumns):
            table.horizontalHeaderItem(i).setTextAlignment(QtCore.Qt.AlignHCenter)

        table.resizeColumnsToContents()        
        self.stations['station_table_nrows'] = 0            
        self.stations['station_add_button'] = QtWidgets.QPushButton('Add')
        self.stations['station_add_button'].clicked.connect(self._station_add_blank)
        self.stations['station_rem_button'] = QtWidgets.QPushButton('Rem')
        self.stations['station_rem_button'].clicked.connect(self._station_rem)
        self.stations['station_known_stations'] = QtWidgets.QComboBox()
        # Populating the known stations, at the moment it is only IOW monitoring
        self.stations['station_known_stations'].addItem('Station File')        
        self.stations['station_known_stations'].addItem('IOW Monitoring')
        self.stations['station_load_button'] = QtWidgets.QPushButton('Load')
        self.stations['station_load_button'].clicked.connect(self.add_station_file)
        # Transect
        self.stations['tran_add_button'] = QtWidgets.QPushButton('Add transect')
        self.stations['tran_add_button'].clicked.connect(self.add_transect)
        self.stations['tran_name_le'] = QtWidgets.QLineEdit('Transect name')
        self.stations['tran_rem_button'] = QtWidgets.QPushButton('Rem transect')
        self.stations['tran_rem_button'].clicked.connect(self.rem_transect)        
        # Connect the table to functions
        self.stations['station_table'].cellChanged.connect(self.station_table_cellchanged)
        self.stations['station_widget'] = QtWidgets.QWidget()
        self.stations['station_layout'] = QtWidgets.QGridLayout(self.stations['station_widget'])
        layout = self.stations['station_layout']
        layout.addWidget(self.stations['station_table'],0,0,1,4)
        layout.addWidget(self.stations['station_add_button'],1,0)
        layout.addWidget(self.stations['station_rem_button'],1,1)
        layout.addWidget(self.stations['station_known_stations'],1,2)
        layout.addWidget(self.stations['station_load_button'],1,3)
        layout.addWidget(self.stations['tran_add_button'],2,0)
        layout.addWidget(self.stations['tran_name_le'],2,1)
        layout.addWidget(self.stations['tran_rem_button'],2,2)

    def _populate_ship_combo(self):
        """ Populates the ship combo with known ships found in yaml file
        """
        for s in ships['ships']:
            self.camp['ship_combo'].addItem(s['name'])

    def update_transects(self):
        """ Updating the transect table according to the entries in columns 4 etc. self.stations['station_table'] 
        """
        table = self.stations['station_table'] 
        nrows = table.rowCount()
        ncols = table.columnCount()
        tran_names   = []
        tran_numbers = []
        tran_station_names = []
        tran_station_lon = []
        tran_station_lat = []                      
            
        if(ncols > 3): # Do we have transects at all
            for i in range(4,ncols):
                tran_names.append(table.horizontalHeaderItem(i).text())
                tran_numbers.append([])
                tran_station_names.append([])
                tran_station_lon.append([])
                tran_station_lat.append([])
                for j in range(nrows):
                    try:
                        #print('Valid number in',j,i)
                        num = int(table.item(j,i).text())
                        tran_numbers[-1].append(num)
                        tran_station_names[-1].append(table.item(j,0).text())
                        tran_station_lon[-1].append(float(table.item(j,1).text()))
                        tran_station_lat[-1].append(float(table.item(j,2).text()))
                    except Exception as e: # not a valid number
                        pass
                        #print('Not a valid numer in ',j,i)

        # Update the transect table
        self.tran['table'].clear()
        self.tran['table'].setColumnCount(len(tran_names))
        self.tran['table'].setHorizontalHeaderLabels(tran_names)

        row_max = 0
        for i in range(len(tran_names)):
            for j in range(len(tran_station_names[i])):
                item = QtWidgets.QTableWidgetItem(tran_station_names[i][j])
                nrows = self.tran['table'].rowCount()
                if(len(tran_station_names[i]) > row_max):
                    row_max = len(tran_station_names[i])
                #print('nrows',nrows,j)
                if(nrows < (j+1)):
                    #print('Adding a row at ',j)
                    self.tran['table'].insertRow(j)

                self.tran['table'].setItem(j,i, item)

        # Check if we have to many rows and delete them if so
        drow = self.tran['table'].rowCount() - row_max
        for i in range(drow):
            self.tran['table'].removeRow(self.tran['table'].rowCount()-1)            
            
        self.tran['table'].resizeColumnsToContents()

        # Sort and save the transects to dictionary
        for i in range(len(tran_names)):
            numbers = np.asarray(tran_numbers[i])
            isort = np.argsort(numbers)
            tran_numbers[i]       = np.asarray(tran_numbers[i])[isort].tolist()
            tran_station_names[i] = np.asarray(tran_station_names[i])[isort].tolist()
            tran_station_lon[i]   = np.asarray(tran_station_lon[i])[isort].tolist()
            tran_station_lat[i]   = np.asarray(tran_station_lat[i])[isort].tolist()   

        self.tran_dict['name']          = tran_names
        #self.tran_dict['numbers']       = tran_numbers # Not really needed
        self.tran_dict['station_names'] = tran_station_names
        self.tran_dict['station_lon']   = tran_station_lon
        self.tran_dict['station_lat']   = tran_station_lat

    def station_table_cellchanged(self):
        col = self.stations['station_table'].currentColumn()
        row = self.stations['station_table'].currentRow()
        if(col > 3): # Check if we are in the transect columns
            print('Transect')
            tran_number = self.stations['station_table'].item(row,col).text()
            try:
                tran_number = int(tran_number)
            except:
                self.stations['station_table'].item(row,col).setText('Number required')
                
            self.update_transects()


    def rem_transect(self):    
        cols = sorted(set(index.column() for index in
                          self.stations['station_table'].selectedIndexes()),reverse=True)

        for i in cols:
            if(i > 3):
                self.stations['station_table'].removeColumn(i)

        self.update_transects()
        
    def add_transect(self):
        """ Creating a new column in station table for transect
        """
        # Adding a new column for the transect
        table = self.stations['station_table']
        ncolumns = table.columnCount()
        ncolumns += 1
        table.setColumnCount(ncolumns)
        transect_name = self.stations['tran_name_le'].text()
        headeritem = QtWidgets.QTableWidgetItem(transect_name)        
        table.setHorizontalHeaderItem(ncolumns-1,headeritem)
        table.resizeColumnsToContents()
        
    def table_changed(self,row,column):
        """ If a comment was added, add it to the comment list and update the data dictionary
        """
        if column == self.columns['comment']:
            comstr = self.file_table.item(row,column).text()
            self.data['pyctd_comment'][row] = comstr
            # Resize the columns
            self.file_table.resizeColumnsToContents()

    def _campaign_rem(self):
        rows = sorted(set(index.row() for index in
                          self.camp['table'].selectedIndexes()),reverse=True)
        for row in rows:
            #print('Row %d is selected' % row)
            self.camp['table'].removeRow(row)
            self.camp['table_nrows'] -= 1                        

    def _station_rem(self):
        rows = sorted(set(index.row() for index in
                          self.stations['station_table'].selectedIndexes()),reverse=True)
        for row in rows:
            #print('Row %d is selected' % row)
            self.stations['station_table'].removeRow(row)
            self.stations['station_table_nrows'] -= 1

        self.update_transects()

    def _update_station_table(self):
        self.stations['station_table'].resizeColumnsToContents()
        table = self.stations['station_table']
        self.station_combo.clear()        
        for row in range(table.rowCount()):
            station_name = table.item(row,0).text()
            #index = table.index(row, 0) # Station name
            #data_str = str(table.data(index).toString())
            self.station_combo.addItem(station_name)

    def _station_add(self,name,lon,lat,comment='',update_table=True):
        itemname = QtWidgets.QTableWidgetItem(name)
        itemlon = QtWidgets.QTableWidgetItem(str(lon))
        itemlat = QtWidgets.QTableWidgetItem(str(lat))
        itemcomment = QtWidgets.QTableWidgetItem(comment)
        self.stations['station_table'].insertRow(self.stations['station_table_nrows'])        
        self.stations['station_table'].setItem(self.stations['station_table_nrows'],0, itemname)
        self.stations['station_table'].setItem(self.stations['station_table_nrows'],1, itemlon)
        self.stations['station_table'].setItem(self.stations['station_table_nrows'],2, itemlat)
        self.stations['station_table'].setItem(self.stations['station_table_nrows'],3, itemcomment)        
        self.stations['station_table_nrows'] += 1
        if(update_table):
            self._update_station_table()

    def campaign_add_from_dict(self,data_yaml):
        """ Adds a campaign from a saved yaml file
        """

        table = self.camp['table']
        nrows = table.rowCount()
        ncols = table.columnCount()
        header = []
        for i in range(ncols):
            header.append(table.horizontalHeaderItem(i).text())

        self.camp['table'].insertRow(self.camp['table_nrows'])

        for camp in data_yaml['campaigns']:
            for i,head in enumerate(header):
                if(head in camp):
                    item = QtWidgets.QTableWidgetItem(camp[head])
                    self.camp['table'].setItem(self.camp['table_nrows'],i, item)

        self.camp['table_nrows'] += 1        
        self.camp['table'].resizeColumnsToContents()            

    def _campaign_add_ship(self):
        self.camp['index_ship']
        i = self.camp['ship_combo'].currentIndex()
        ship = ships['ships'][i] # Get the choosen ship
        iship = self.camp['index_ship'] # The index in self.camp['table']
        rows = sorted(set(index.row() for index in
                        self.camp['table'].selectedIndexes()),reverse=True)

        if(len(rows)>0):
            for i,k in enumerate(ship.keys()):
                for r in rows:
                    if ship[k] == None:
                        sstr = ''
                    else:
                        sstr = str(ship[k])
                        
                    item = QtWidgets.QTableWidgetItem(sstr)
                    self.camp['table'].setItem(r,iship+i, item)


        self.camp['table'].resizeColumnsToContents()

    def _campaign_add_blank(self):
        #print('Station add blank')
        item = QtWidgets.QTableWidgetItem('Campaign  ' + str(self.camp['table_nrows']))
        self.camp['table'].insertRow(self.camp['table_nrows'])        
        self.camp['table'].setItem(self.camp['table_nrows'],0, item)
        self.camp['table_nrows'] += 1
        self.camp['table'].resizeColumnsToContents()
        #self._update_station_table()

    def _station_add_from_dict(self,data_yaml):
        """ Add stations from a dictionary 
        """
        item = QtWidgets.QTableWidgetItem('Station  ' + str(self.stations['station_table_nrows']))
        self.stations['station_table'].insertRow(self.stations['station_table_nrows'])        
        self.stations['station_table'].setItem(self.stations['station_table_nrows'],0, item)
        self.stations['station_table_nrows'] += 1
        #self.stations['station_table'].resizeColumnsToContents()
        self._update_station_table()

    def _station_add_blank(self):
        #print('Station add blank')
        item = QtWidgets.QTableWidgetItem('Station  ' + str(self.stations['station_table_nrows']))
        self.stations['station_table'].insertRow(self.stations['station_table_nrows'])        
        self.stations['station_table'].setItem(self.stations['station_table_nrows'],0, item)
        self.stations['station_table_nrows'] += 1
        #self.stations['station_table'].resizeColumnsToContents()
        self._update_station_table()
        
    def _station_add_to_cast(self):                   
        #self.data['pyctd_station'][i] = tran    
        if True:
            tran_name = self._new_station_edit.text()
            FLAG_NEW = True
            if(len(tran_name) > 0):
                for count in range(self.station_combo.count()):
                    if(self.station_combo.itemText(count) == tran_name):
                        FLAG_NEW = False

                if FLAG_NEW:
                    self.station_combo.addItem(tran_name)
                    cnt = self.station_combo.count()
                    self.station_combo.setCurrentIndex(cnt-1)
                    
    def _station_apply(self):
        if True:
            for i in self._station_rows:
                tran = self.station_combo.currentText()
                if tran == 'Remove':
                    self.data['pyctd_station'][i] = None
                else:
                    self.data['pyctd_station'][i] = tran


        self.update_table()        
        self._station_widget.hide()

    def _station_cancel(self):
        self._station_widget.hide()

        
    def plot_map_opts(self):
        #print('Plot map options')
        self._map_options_widget = QtWidgets.QWidget()
        self._map_options_widget.setWindowTitle('pyctd map options')

        layout = QtWidgets.QGridLayout(self._map_options_widget)

        self._map_options_res_combo = QtWidgets.QComboBox()
        self._map_options_res_combo.addItem('110m')
        self._map_options_res_combo.addItem('50m')
        self._map_options_res_combo.addItem('10m')        
        index = self._map_options_res_combo.findText(self._map_settings['res'], QtCore.Qt.MatchFixedString)
        if index >= 0:
            self._map_options_res_combo.setCurrentIndex(index)

        self._map_options_change_button = QtWidgets.QPushButton('Change')
        self._map_options_change_button.clicked.connect(self.plot_change_settings)
        layout.addWidget(QtWidgets.QLabel('Coastline resolution'),0,0)
        layout.addWidget(self._map_options_res_combo,1,0)
        layout.addWidget(self._map_options_change_button,2,1)

        self._map_options_widget.show()

    def plot_change_settings(self):
        print('Changing settings')
        self._map_settings['res'] = self._map_options_res_combo.currentText()
        print(self._map_settings['res'])
        #self._map_settings =
        self._map_zoom_x = self.axes.get_xlim()
        self._map_zoom_y = self.axes.get_ylim()
        # Plotting the map
        try:
            self.figwidget.close()
        except:
            pass
        
        self.plot_map()
        
    def remstation_signal(self,rows):
        #print('Removing stations')
        for row in rows:        
            self.data['pyctd_station'][row] = None

        self.update_table()

    def remcampaign_signal(self,rows):
        #print('Removing stations')
        for row in rows:        
            self.data['pyctd_campaign'][row] = None

        self.update_table()        
        
    def station_signal(self,rows):
        """ Adding a station to the casts
        """
        self._station_rows = rows
        table = self.stations['station_table']
        self.station_combo.clear()
        self.choose_station = {}
        self.choose_station['widget'] = QtWidgets.QWidget()
        self.choose_station['layout'] = QtWidgets.QGridLayout(self.choose_station['widget'])
        table_choose = QtWidgets.QTableWidget()
        table_choose.setColumnCount(1)
        table_choose.setHorizontalHeaderLabels(['Name'])                    
        for row in range(table.rowCount()):
            station_name = table.item(row,0).text()
            item = QtWidgets.QTableWidgetItem( station_name )            
            table_choose.insertRow(row)
            table_choose.setItem(row,0,item)

        table_choose.resizeColumnsToContents()
        self.choose_station['button_add'] = QtWidgets.QPushButton('Add')
        self.choose_station['button_add'].clicked.connect(self._table_choose_add_to_casts)
        self.choose_station['layout'].addWidget(table_choose,0,0,1,2)
        self.choose_station['layout'].addWidget(self.choose_station['button_add'],1,0)
        self.choose_station['table'] = table_choose            
        self.choose_station['widget'].show()

    def _table_choose_add_to_casts(self):
        print('Hallo!')
        rows = sorted(set(index.row() for index in
                          self.choose_station['table'].selectedIndexes()),reverse=False)

        stations = ''
        for row in rows:
            print('Row %d is selected in choose table: ' % row)
            station_name = self.choose_station['table'].item(row,0).text()
            stations += station_name + ' ; '

        stations = stations[:-3] # remove last ;
        rows = sorted(set(index.row() for index in
                          self.file_table.selectedIndexes()),reverse=True)


        for row in rows:
            print('Row %d is selected in station table: ' % row)
            #item = QtWidgets.QTableWidgetItem( stations )
            self.data['pyctd_station'][row] = stations                    
            #self.file_table.setItem(row,self.columns['station (Custom)'], item)                        


        self.update_table()


    def campaign_signal(self,rows):
        """ Adding a station to the casts
        """
        self._campaign_rows = rows
        table = self.camp['table']
        self.choose_campaign = {}
        self.choose_campaign['widget'] = QtWidgets.QWidget()
        self.choose_campaign['layout'] = QtWidgets.QGridLayout(self.choose_campaign['widget'])
        table_choose = QtWidgets.QTableWidget()
        table_choose.setColumnCount(1)
        table_choose.setHorizontalHeaderLabels(['Name'])                    
        for row in range(table.rowCount()):
            campaign_name = table.item(row,0).text()
            item = QtWidgets.QTableWidgetItem( campaign_name )            
            table_choose.insertRow(row)
            table_choose.setItem(row,0,item)

        table_choose.resizeColumnsToContents()
        self.choose_campaign['button_add'] = QtWidgets.QPushButton('Add')
        self.choose_campaign['button_add'].clicked.connect(self._table_choose_campaign_to_casts)
        self.choose_campaign['layout'].addWidget(table_choose,0,0,1,2)
        self.choose_campaign['layout'].addWidget(self.choose_campaign['button_add'],1,0)
        self.choose_campaign['table'] = table_choose            
        self.choose_campaign['widget'].show()

    def _table_choose_campaign_to_casts(self):
        rows = sorted(set(index.row() for index in
                          self.choose_campaign['table'].selectedIndexes()),reverse=False)

        campaigns = ''
        for row in rows:
            print('Row %d is selected in choose table: ' % row)
            campaign_name = self.choose_campaign['table'].item(row,0).text()
            campaigns += campaign_name + ' ; '

        campaigns = campaigns[:-3] # remove last ;
        rows = sorted(set(index.row() for index in
                          self.file_table.selectedIndexes()),reverse=True)


        for row in rows:
            print('Row %d is selected in campaign table: ' % row)
            #item = QtWidgets.QTableWidgetItem( campaigns )
            self.data['pyctd_campaign'][row] = campaigns                    
            #self.file_table.setItem(row,self.columns['station (Custom)'], item)                        


        self.update_table()        

        
    def plot_signal(self,rows,command):
        if(command == 'add to map'):
            self.add_positions_to_map(rows)
        elif(command == 'rem from map'):
            self.rem_positions_from_map(rows)
        elif(command == 'plot cast'):
            self.plot_cast(rows)            

    def plot_cast(self,row):
        """ Plots a single CTD cast
        """
        filename = self.data['files'][row]
        cnv = pycnv(filename)
        self.cast_fig       = Figure(dpi=self.dpi)
        self.cast_figwidget = QtWidgets.QWidget()
        self.cast_figwidget.setWindowTitle('pyctd cast')
        self.cast_canvas    = FigureCanvas(self.cast_fig)
        self.cast_canvas.setParent(self.cast_figwidget)
        plotLayout = QtWidgets.QVBoxLayout()
        plotLayout.addWidget(self.cast_canvas)
        self.cast_figwidget.setLayout(plotLayout)
        self.cast_canvas.setMinimumSize(self.cast_canvas.size()) # Prevent to make it smaller than the original size
        self.cast_mpl_toolbar = NavigationToolbar(self.cast_canvas, self.cast_figwidget)
        plotLayout.addWidget(self.cast_mpl_toolbar)
        
        cnv.plot(figure=self.cast_fig)
        self.cast_canvas.draw()        
        #for ax in cnv.axes[0]['axes']:
        #    ax.draw()
        self.cast_figwidget.show()

    def clear_table_clicked(self):
        try:
            self.data['files']
        except:
            return
        # Remove from plot
        for row in range(len(self.data['files'])):            
            while self.data['pyctd_plot_map'][row]:
                tmpdata = self.data['pyctd_plot_map'][row].pop()
                for line in tmpdata:
                    line.remove()
        try:
            self.canvas.draw()
        except:
            pass
        
        self.file_table.setRowCount(0)
        
    def folder_clicked(self):
        foldername = str(QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory"))
        self.folder_dialog.setText(foldername)
        self.foldername = foldername

    def search_opts_clicked(self):
        self.search_opts_widget.show()

    def search_clicked(self):
        foldername = self.folder_dialog.text()
        self.foldername = self.folder_dialog.text()
        if(os.path.exists(foldername)):
            self.status_widget       = QtWidgets.QWidget()
            self.status_layout       = QtWidgets.QGridLayout(self.status_widget)
            self._progress_bar       = QtWidgets.QProgressBar(self.status_widget)
            #self._thread_stop_button = QtWidgets.QPushButton('Stop')
            #self._thread_stop_button.clicked.connect(self.search_stop)
            self._f_widget           = QtWidgets.QLabel('Filename')
            self._f_widget.setWordWrap(True)
            self.status_layout.addWidget(QtWidgets.QLabel('Loading files'),0,0)            
            self.status_layout.addWidget(self._progress_bar,1,0)
            self.status_layout.addWidget(self._f_widget,2,0)
            #self.status_layout.addWidget(self._thread_stop_button,2,0)
            self.status_widget.show()
            # Check for the positional thresholds
            print('Hallo!',self._search_opt_pos.currentText())
            if 'None' in self._search_opt_pos.currentText():
                print('No position search')
                station = None
            elif 'Station' in self._search_opt_pos.currentText():
                print('Station position search')                
                # TODO, this has to be parsed with pylatlon
                lon     = float(self._search_opt_lonc.text())
                lat     = float(self._search_opt_latc.text())
                radius  = float(self._search_opt_radius.text())                
                station = [lon,lat,radius]
            elif 'Rectangle' in self._search_opt_pos.currentText():
                print('Rectangle position search')
                # TODO, this has to be parsed with pylatlon                
                lon0     = float(self._search_opt_lonc0.text())
                lat0     = float(self._search_opt_latc0.text())
                lon1     = float(self._search_opt_lonc1.text())
                lat1     = float(self._search_opt_latc1.text())
                station = [lon0,lat0,lon1,lat1]

            print('Station',station)
            # Check for the time thresholds
            start_time = str_to_time(self._search_opt_start.text())[1]
            stop_time = str_to_time(self._search_opt_end.text())[1]
            self.search_thread = get_valid_files(foldername,search_seabird=self._search_opt_cnv.isChecked(), search_mrd = self._search_opt_mrd.isChecked(),start_time=start_time,stop_time = stop_time,station=station)
            self.search_thread.start()
            self.search_thread.search_status.connect(self.status_function)
            self.search_thread.finished.connect(self.search_finished)
            #pycnv_sum_folder.get_all_valid_files(foldername,status_function=self.status_function)
        else:
            print('Enter a valid folder')

    def search_stop(self):
        """This doesnt work, if a stop is needed it the search function needs
        to have the functionality to be interrupted

        """
        self.search_thread.terminate()
        #self.status_widget.close()
        
    def search_finished(self):
        self.status_widget.close()
        data = self.search_thread.data
        self.data = self.compare_and_merge_data(self.data,data)
        print('Search finished')
        #print(data)
        if(self.FLAG_REL_PATH):
            for i,c in enumerate(self.data['info_dict']):
                fname = c['file']
                fname = fname.replace(self.foldername,'.') # TODO, check if filesep is needed for windows
                self.data['info_dict'][i]['file'] = fname

        self.create_table()
        self.update_table()

    def compare_and_merge_data(self, data, data_new, new_station=True, new_comment=True):
        """ Checks in data field if new data is already there, if not it adds it, otherwise it rejects it, it also add pyctd specific data fields, if they not already exist
        """
        print('Compare and merge')
        try:
            data_new['pyctd_plot_map']
        except:
            data_new['pyctd_plot_map'] = [[] for i in range(len(data_new['info_dict'])) ] # Plotting information

        try:
            data_new['pyctd_station']
        except:
            data_new['pyctd_station'] = [None] * len(data_new['info_dict']) # station information

        try:
            data_new['pyctd_campaign']
        except:
            data_new['pyctd_campaign'] = [None] * len(data_new['info_dict']) # station information            
            
        try:
            data_new['pyctd_comment']
        except:
            data_new['pyctd_comment'] = [None] * len(data_new['info_dict']) # station information
            
        # Check if we have data at all
        try:
            data['info_dict']
        except:
            return data_new
        
        for i_new,c_new in enumerate(data_new['info_dict']):
            FLAG_SAME = False
            for i,c in enumerate(data['info_dict']):
                if c['sha1'] == c_new['sha1']: # Same file
                    FLAG_SAME = True
                    if(new_station):
                        if(data_new['pyctd_station'][i_new] is not None):
                            data['pyctd_station'][i] = data_new['pyctd_station'][i_new]
                            
                    if(new_comment):
                        if(data_new['pyctd_comment'][i_new] is not None):
                            data['pyctd_comment'][i] = data_new['pyctd_comment'][i_new]

                    break
                
            if(FLAG_SAME == False):
                data['info_dict'].append(data_new['info_dict'][i_new])
                data['pyctd_plot_map'].append(data_new['pyctd_plot_map'][i_new])                
                data['pyctd_station'].append(data_new['pyctd_station'][i_new])
                data['pyctd_comment'].append(data_new['pyctd_comment'][i_new])


        return data
        
    def create_table(self):
        # Add additional information (if its not there already)

            
        try:
            cnt = len(self.data['info_dict'])
        except:
            cnt = 0

        nrows = self.file_table.rowCount()
        n_new_rows = cnt - nrows
        for i in range(n_new_rows):
            self.file_table.insertRow(i)
            

    def update_table(self):
        #print('Update table')
        #print(len(self.data['pyctd_campaign']))
        #print(len(self.data['info_dict']))
        # Fill the table
        try:
            cnt = len(self.data['info_dict'])
        except:
            cnt = 0

        if(cnt > 0):
            self._status_widget_tmp    = QtWidgets.QWidget()
            self._status_layout_tmp    = QtWidgets.QVBoxLayout(self._status_widget_tmp)            
            self._progress_bar_tmp     = QtWidgets.QProgressBar()
            self._status_layout_tmp.addWidget(QtWidgets.QLabel('Updating table'))
            self._status_layout_tmp.addWidget(self._progress_bar_tmp)
            self._status_widget_tmp.show()
            self._progress_bar_tmp.setMaximum(cnt)            
        for i in range(cnt):
            # Create a progress bar
            self._progress_bar_tmp.setValue(i)
            # A poor mans solution to avoid blocking after reading a lot of data, better would be a thread
            # https://stackoverflow.com/questions/24738333/pyqt-gui-freezes-while-in-loop
            if(i%5 == 0):
                QtCore.QCoreApplication.processEvents()
            # Add date
            date = self.data['info_dict'][i]['date']
            item = QtWidgets.QTableWidgetItem( date.strftime('%Y-%m-%d %H:%M:%S' ))
            item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable) # Unset to not have it editable
            self.file_table.setItem(i,self.columns['date'], item)
            
            lon = self.data['info_dict'][i]['lon']
            item = QtWidgets.QTableWidgetItem( "{:6.3f}".format(lon))
            item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable) # Unset to not have it editable            
            self.file_table.setItem(i,self.columns['lon'], item)
            lat = self.data['info_dict'][i]['lat']
            item = QtWidgets.QTableWidgetItem( "{:6.3f}".format(lat))
            item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable) # Unset to not have it editable
            self.file_table.setItem(i,self.columns['lat'], item)
            # Station as in the file
            try:
                stat = self.data['info_dict'][i]['station']
            except:
                stat = ''
                
            item = QtWidgets.QTableWidgetItem(stat)
            item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable) # Unset to not have it editable
            self.file_table.setItem(i,self.columns['station (File)'], item)
            # Custom station as defined in pyctd
            stat = self.data['pyctd_station'][i]
            if(stat is not None):
                item = QtWidgets.QTableWidgetItem( str(stat) )
            else:
                item = QtWidgets.QTableWidgetItem( str('') )

            item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable) # Unset to not have it editable                
            self.file_table.setItem(i,self.columns['station (Custom)'], item)

            # Campaign as defined in pyctd
            stat = self.data['pyctd_campaign'][i]
            if(stat is not None):
                item = QtWidgets.QTableWidgetItem( str(stat) )
            else:
                item = QtWidgets.QTableWidgetItem( str('') )

            item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable) # Unset to not have it editable                
            self.file_table.setItem(i,self.columns['campaign'], item)                            

            # Comment
            comstr  = self.data['pyctd_comment'][i]                   
            if(comstr is None):
                comstr = ''

            comitem = QtWidgets.QTableWidgetItem( comstr )
            comitem.setFlags(QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self.file_table.setItem(i,self.columns['comment'],comitem)
                
            fname = self.data['info_dict'][i]['file']
            item = QtWidgets.QTableWidgetItem( fname )
            item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable) # Unset to not have it editable
            self.file_table.setItem(i,self.columns['file'], item)

        # If the widget is open
        try:
            self._status_widget_tmp.close()
        except:
            pass
        # Resize the columns
        self.file_table.resizeColumnsToContents()
        
    def status_function(self,call_object,i,nf,f):
        if(i == 0):
            self._progress_bar.setMaximum(nf)
            
        self._progress_bar.setValue(i)
        #tstr = str(i) +' of ' + str(nf)
        fstr = str(f)
        #self._i_widget.setText(tstr)
        self._f_widget.setText(fstr)

    def save_all(self):
        # Do the actual saving
        filename,extension  = QtWidgets.QFileDialog.getSaveFileName(self,"Choose file for summary","","All Files (*)")
        if(len(filename) > 0):
            filename_casts = filename + '_casts'
            filename_meta  = filename + '_meta'
            try: # Test if there are casts at all
                cnt = len(self.data['info_dict'])
            except:
                cnt = 0

            if(cnt > 0):
                self.save_data(filename_casts,casts=True,stations=False,transects=False,campaigns=False)
                
            self.save_data(filename_meta, casts=False,stations=True,transects=True,campaigns=True)        

    def save_geojson(self):
        # Do the actual saving
        filename,extension  = QtWidgets.QFileDialog.getSaveFileName(self,"Choose file for summary","","All Files (*)")
        
        if(len(filename) > 0):
            self.save_data(filename,casts=True,stations=True,transects=True,stype='geojson')
        
    def save_data(self,filename, casts=False,stations=False,transects=False,campaigns=False,stype='yaml'):
        """ This function saves everything (casts, stations, transects)
        """
        cast_dict    = self.create_cast_summary()
        station_dict = self.create_station_summary()
        transect_dict = self.create_transect_summary()
        campaign_dict = self.create_campaign_summary()
        yaml_dict = {}

        if casts:
            yaml_dict.update(cast_dict)
        if stations:
            yaml_dict.update(station_dict)
        if transects:
            yaml_dict.update(transect_dict)
        if campaigns:
            yaml_dict.update(campaign_dict)
        

        if(len(filename) > 0):
            # Save the files
            if stype is 'yaml':
                create_yaml_summary(yaml_dict,filename)
            if stype is 'geojson':
                create_geojson_summary(yaml_dict,filename)

    def save_csv(self):
        filename,extension  = QtWidgets.QFileDialog.getSaveFileName(self,"Choose file for summary","","CSV File (*.csv);;All Files (*)")
        if 'csv' in extension and ('.csv' not in filename):
            filename += '.csv'

        yaml_dict    = self.create_cast_summary()
        create_csv_summary(yaml_dict,filename)

    def create_station_summary(self):
        """ Creates a summary of all stations read in
        """

        yaml_dict = {}
        yaml_dict['created'] = str(datetime.datetime.now(pytz.utc))
        yaml_dict['version'] = version        
        yaml_dict['stations'] = []
        table = self.stations['station_table']
        #self.stations['station_table']
        for row in range(table.rowCount()):
            station = {}
            station['name'] = table.item(row,0).text()
            station['lon'] = float(table.item(row,1).text())
            station['lat'] = float(table.item(row,2).text())

            yaml_dict['stations'].append(station)

        return yaml_dict

    def create_transect_summary(self):
        """ Creates a summary of all stations read in
        """
        # self.tran is updated in update_transects function
        #self.tran['name']          = tran_names
        #self.tran['numbers']       = tran_numbers
        #self.tran['station_names'] = tran_station_names
        #self.tran['station_lon']   = tran_station_lon
        #self.tran['station_lat']   = tran_station_lat
        yaml_dict = {}
        yaml_dict['transects'] = self.tran_dict
        
        return yaml_dict

    def create_cast_summary(self):
        """ Creates a summary from the given sum_dict for all casts read in
        """
        yaml_dict = {}
        try:
            self.data['info_dict']
        except:
            return {}

        yaml_dict['created'] = str(datetime.datetime.now(pytz.utc))
        yaml_dict['version'] = version
        yaml_dict['casts']   = copy.deepcopy(self.data['info_dict'])
        # Convert datetime objects into something readable
        for i,d in enumerate(yaml_dict['casts']):
            yaml_dict['casts'][i]['date'] = str(d['date'])
            if(self.data['pyctd_station'][i] is not None):
                yaml_dict['casts'][i]['station pyctd'] = self.data['pyctd_station'][i]
            else:
                yaml_dict['casts'][i]['station pyctd'] = ''

            if(self.data['pyctd_comment'][i] is not None):
                yaml_dict['casts'][i]['comment'] = self.data['pyctd_comment'][i]
            else:
                yaml_dict['casts'][i]['comment'] = ''

            if(self.data['pyctd_campaign'][i] is not None):
                yaml_dict['casts'][i]['campaign'] = self.data['pyctd_campaign'][i]
            else:
                yaml_dict['casts'][i]['campaign'] = ''                                
                
            if(self.FLAG_REL_PATH):
                fname = yaml_dict['casts'][i]['file']
                fname = fname.replace(self.foldername,'.') # TODO, check if filesep is needed for windows
                yaml_dict['casts'][i]['file'] = fname
                
        return yaml_dict

    def create_campaign_summary(self):
        """ Reads in the campaign table in self.camp['table'] and creates a dictionary out of it
        """

        table = self.camp['table']
        nrows = table.rowCount()
        ncols = table.columnCount()
        campaigns = []
        header = []
        for i in range(ncols):
            header.append(table.horizontalHeaderItem(i).text())

        for i in range(nrows):
            camp = {}
            for j in range(ncols):
                it = table.item(i,j)
                if(it is not None):
                    dstr = it.text()
                else:
                    dstr = ''
                    
                camp[header[j]] = dstr

            campaigns.append(camp)
        
        return {'campaigns':campaigns}
        

    def create_cruise_summary(self):
        """ outdated, candidate to remove
        """
        try:
            self._cruise_fields['Cruise ID']
        except:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setInformativeText('You have to define at least a cruise ID')
            retval = msg.exec_()
            return

        yaml_dict = {}
        filename,extension  = QtWidgets.QFileDialog.getSaveFileName(self,"Choose file for yaml cruise summary","","YAML File (*.yaml);;All Files (*)")
        if 'yaml' in extension and ('.yaml' not in filename):
            filename += '.yaml'        
            
        yaml_dict['created'] = str(datetime.datetime.now(pytz.utc))
        yaml_dict['version'] = version
        
        for k in self._cruise_fields.keys():
            if(len(self._cruise_fields[k]) > 0):
                yaml_dict[k] = self._cruise_fields[k]

        
        create_yaml_summary(yaml_dict,filename)


    def load_file(self):
        """ Loads a file and merges it into the existing data
        """
        filename_all,extension  = QtWidgets.QFileDialog.getOpenFileName(self,"Choose existing summary file","","YAML File (*.yaml);;All Files (*)")
        filename                =  os.path.basename(filename_all) # Get the filename
        dirname                 =  os.path.dirname(filename_all)  # Get the path
        if(len(filename_all) == 0):
            return


        # Opening the yaml file
        try:
            stream = open(filename_all, 'r')
            data_yaml = yaml.safe_load(stream)
        except Exception as e:
            # TODO warning message, bad data
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setInformativeText('No valid or not existing yaml file')
            retval = msg.exec_()            
            return        

        if('campaigns' in data_yaml):
            print('Having campaigns')
            self.campaign_add_from_dict(data_yaml)

        if('stations' in data_yaml):
            print('Having stations')
            self.station_add_from_dict(stations_yaml = data_yaml)

        if('transects' in data_yaml):
            print('Having transects')
            self.transect_add_from_dict(data_yaml)                                    

    def load_summary(self):
        filename_all,extension  = QtWidgets.QFileDialog.getOpenFileName(self,"Choose existing summary file","","YAML File (*.yaml);;All Files (*)")
        filename                =  os.path.basename(filename_all) # Get the filename
        dirname                 =  os.path.dirname(filename_all)  # Get the path
        if(len(filename_all) == 0):
            return
        
        # Opening the yaml file
        try:
            stream = open(filename_all, 'r')
            data_yaml = yaml.safe_load(stream)
        except Exception as e:
            # TODO warning message, bad data
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setInformativeText('No valid or not existing yaml file')
            retval = msg.exec_()            
            return

        data = {}
        data['pyctd_station']   = []
        data['pyctd_comment']   = []
        # Fill the data structure again
        data['info_dict'] = data_yaml['casts']        
        for i,c in enumerate(data['info_dict']):
            # Fill in pyctd specific stuff
            try:
                data['pyctd_station'].append(c['station'])
            except Exception as e:
                data['pyctd_station'].append(None)

            try:
                data['pyctd_comment'].append(c['comment'])
            except Exception as e:
                data['pyctd_comment'].append(None)

            try:
                data['pyctd_campaign'].append(c['campaign'])
            except Exception as e:
                data['pyctd_campaign'].append(None)                                
                
            date = datetime.datetime.strptime(c['date'],'%Y-%m-%d %H:%M:%S%z')
            data['info_dict'][i]['date'] = date

            
        self.data = self.compare_and_merge_data(self.data,data)        
        self.create_table()
        self.update_table()

        
    def cruise_information(self):
        # Check if we have a cruise fields, otherwise create one
        try:
            self._cruise_fields['Cruise name']
        except:
            self._cruise_fields['Cruise name'] = ''
        try:            
            self._cruise_fields['Cruise ID']
        except:
            self._cruise_fields['Cruise ID'] = ''
        try:
            self._cruise_fields['Ship name']
        except:
            self._cruise_fields['Ship name'] = ''
        try:
            self._cruise_fields['Ship callsign']
        except:            
            self._cruise_fields['Ship callsign'] = ''
        try:
            self._cruise_fields['Project']
        except:            
            self._cruise_fields['Project'] = ''
        try:
            self._cruise_fields['Principal investigator']            
        except:            
            self._cruise_fields['Principal investigator'] = ''
        try:
            self._cruise_dialogs
        except Exception as e:
            print(str(e))
            self._cruise_dialogs = {}
            self.cruise_widget = QtWidgets.QWidget()
            cruise_layout = QtWidgets.QGridLayout(self.cruise_widget)            
            for i,f in enumerate(self._cruise_fields.keys()):
                dialog = QtWidgets.QLineEdit(self)
                self._cruise_dialogs[f] = dialog
                cruise_layout.addWidget(QtWidgets.QLabel(f),i,0)
                cruise_layout.addWidget(dialog,i,1)

            button_apply = QtWidgets.QPushButton('Apply')
            button_apply.clicked.connect(self._cruise_apply)
            button_cancel = QtWidgets.QPushButton('Close')
            button_cancel.clicked.connect(self._cruise_cancel)
            cruise_layout.addWidget(button_apply,i+1,0)
            cruise_layout.addWidget(button_cancel,i+1,1)

            
        for i,f in enumerate(self._cruise_fields.keys()):
            self._cruise_dialogs[f].setText(self._cruise_fields[f])            
            
        self.cruise_widget.show()

    def _cruise_apply(self):
        for i,f in enumerate(self._cruise_dialogs.keys()):
            self._cruise_fields[f] = str(self._cruise_dialogs[f].text())
        
    def _cruise_cancel(self):
        self.cruise_widget.hide()

    def add_station_file(self):
        """ Function to get a filename for loading a station
        """ 
        if True:
            combo_text = self.stations['station_known_stations'].currentText()
            if('Station File' in combo_text):
                files_types = "YAML (*.yml);; All (*)"
                fchoosen = QtWidgets.QFileDialog.getOpenFileName(self, "Select Station File",'',files_types)
                stations_file = fchoosen[0]
            elif('IOW Monitoring' in combo_text):
                stations_file = pkg_resources.resource_filename('pycnv', 'stations/iow_stations.yaml')

            try:
                f_stations = open(stations_file)
            except Exception as e:
                print('Could not open file:' + stations_file)
                return
            
            # use safe_load instead load
            print('Loading stations yaml')
            stations_yaml = yaml.safe_load(f_stations)
            f_stations.close()
            
        self.station_add_from_dict(stations_yaml)

    def transect_add_from_dict(self, transects_yaml):
        """ Adding the transects from the dictionary into the station table and doing an update
        """
        table = self.stations['station_table'] 
        nrows = table.rowCount()
        ncols = table.columnCount()        
        for i,name in enumerate(transects_yaml['transects']['name']):
            # Adding a new column for the transect
            table = self.stations['station_table']
            ncolumns = table.columnCount()
            ncolumns += 1
            table.setColumnCount(ncolumns)
            headeritem = QtWidgets.QTableWidgetItem(name)        
            table.setHorizontalHeaderItem(ncolumns-1,headeritem)
            for j,sname in enumerate(transects_yaml['transects']['station_names'][i]): # Loop through all stations and search for the same name
                for k in range(nrows):
                    ssname = table.item(k,0).text()
                    print(sname,ssname)
                    if(ssname == sname): # Found the same name
                        print('Found')
                        item = QtWidgets.QTableWidgetItem(str(j))                        
                        table.setItem(k,ncolumns-1,item)
                        break
        self.update_transects()                
        table.resizeColumnsToContents()
            
    def station_add_from_dict(self, stations_yaml = None):        
#    def add_station_file_dict(self, stations_file = None, stations_yaml = None):
        for i,station in enumerate(stations_yaml['stations']):
            name = station['name']
            #lon  = station['longitude']
            #lat  = station['latitude']
            lon  = station['lon']
            lat  = station['lat']                
            self._station_add(name,lon,lat,update_table=False)

        self._update_station_table()            

        
        


class pyctdMainWindow(QtWidgets.QMainWindow):
    def __init__(self,logging_level=logging.INFO):
        QtWidgets.QMainWindow.__init__(self)
        mainMenu = self.menuBar()
        self.setWindowTitle("pyctd")
        self.mainwidget = mainWidget()
        self.setCentralWidget(self.mainwidget)
        
        quitAction = QtWidgets.QAction("&Quit", self)
        quitAction.setShortcut("Ctrl+Q")
        quitAction.setStatusTip('Closing the program')
        quitAction.triggered.connect(self.close_application)
        sumlAction = QtWidgets.QAction("&Load summary", self)
        sumlAction.setShortcut("Ctrl+O")
        sumlAction.triggered.connect(self.mainwidget.load_summary)
        sumcastAction = QtWidgets.QAction("&Create cast summary", self)
        sumcastAction.triggered.connect(self.mainwidget.create_cast_summary)
        sumcastAction.setShortcut("Ctrl+S")
        sumcruiseAction = QtWidgets.QAction("&Create cruise summary", self)
        sumcruiseAction.triggered.connect(self.mainwidget.create_cruise_summary)                        

        fileMenu = mainMenu.addMenu('&File')
        fileMenu.addAction(sumlAction)
        fileMenu.addAction(sumcastAction)
        fileMenu.addAction(sumcruiseAction)        
        fileMenu.addAction(quitAction)
        #fileMenu.addAction(chooseStreamAction)

        searchMenu = mainMenu.addMenu('&Search')
        searchoptsAction = QtWidgets.QAction("&Search options", self)
        searchoptsAction.triggered.connect(self.mainwidget.search_opts_clicked)
        searchMenu.addAction(searchoptsAction)        


        cruiseMenu = mainMenu.addMenu('&Cruise')
        cruiseAction = QtWidgets.QAction("&Cruise information", self)
        cruiseAction.setShortcut("Ctrl+I")        
        cruiseAction.triggered.connect(self.mainwidget.cruise_information)
        cruiseMenu.addAction(cruiseAction)                
        statAction = QtWidgets.QAction("&Create Station", self)
        cruiseMenu.addAction(statAction)        

        self.statusBar()

    def close_application(self):
        sys.exit()                                



def main():
    app = QtWidgets.QApplication(sys.argv)
    window = pyctdMainWindow()
    w = 1000
    h = 600
    window.resize(w, h)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()    
