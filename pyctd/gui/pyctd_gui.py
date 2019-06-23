from pycnv import pycnv, pycnv_sum_folder
from ..sst import pymrd as pymrd
from ..sst import pymrd_sum_folder as pymrd_sum_folder
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

# Get the version
version_file = pkg_resources.resource_filename('pyctd','VERSION')

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

def create_yaml_summary(summary,filename):
    """ Creates a yaml summary
    """
    print('Create yaml summary in file:' + filename)
    with open(filename, 'w') as outfile:
        yaml.dump(summary, outfile, default_flow_style=False)


def create_csv_summary(summary,filename,order=None,):
    """ Creates a csv summary
    """
    print('Create csv summary in file:' + filename)
    pass


class get_valid_files(QtCore.QThread):
    """ A thread to search a directory for valid files
    """
    search_status = QtCore.pyqtSignal(object,int,int,str) # Create a custom signal
    def __init__(self,foldername,search_seabird = True,search_mrd = True):
        QtCore.QThread.__init__(self)
        self.foldername = foldername
        self.search_seabird = search_seabird
        self.search_mrd = search_mrd
        
    def __del__(self):
        self.wait()

    def run(self):
        # your logic here
        #pycnv_sum_folder.get_all_valid_files(foldername,status_function=self.status_function)
        #https://stackoverflow.com/questions/39658719/conflict-between-pyqt5-and-datetime-datetime-strptime
        locale.setlocale(locale.LC_TIME, "C")
        data_tmp = pycnv_sum_folder.get_all_valid_files(self.foldername,loglevel = logging.WARNING,status_function=self.status_function)
        self.data = data_tmp
        
        if(self.search_mrd):
            data_tmp = pymrd_sum_folder.get_all_valid_files(self.foldername,loglevel = logging.WARNING,status_function=self.status_function)
            if True:
                for key in self.data.keys():
                    self.data[key].extend(data_tmp[key])
        
        
    def status_function(self,i,nf,f):
        self.search_status.emit(self,i,nf,f)


class casttableWidget(QtWidgets.QTableWidget):
    plot_signal = QtCore.pyqtSignal(object,str) # Create a custom signal for plotting
    station_signal = QtCore.pyqtSignal(object) # Create a custom signal for adding the cast to station
    comment_signal = QtCore.pyqtSignal(object) # Create a custom signal for adding the cast to station    
    def __init__(self):
        QtWidgets.QTableWidget.__init__(self)

    def contextMenuEvent(self, event):
        self.menu = QtWidgets.QMenu(self)
        plotAction = QtWidgets.QAction('Add to map', self)
        plotAction.triggered.connect(self.plot_map)
        stationAction = QtWidgets.QAction('Add/Rem to Station', self)
        stationAction.triggered.connect(self.station)
        remplotAction = QtWidgets.QAction('Rem from map', self)
        remplotAction.triggered.connect(self.rem_from_map)
        plotcastAction = QtWidgets.QAction('Plot cast', self)
        plotcastAction.triggered.connect(self.plot_cast)                
        self.menu.addAction(stationAction)
        self.menu.addAction(plotAction)
        self.menu.addAction(remplotAction)
        self.menu.addAction(plotcastAction)        
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

    def plot_map(self):
        row_list = self.rows
        self.plot_signal.emit(row_list,'add to map') # Emit the signal with the row list and the command

    def rem_from_map(self):
        row_list = self.rows
        self.plot_signal.emit(row_list,'rem from map') # Emit the signal with the row list and the command

    def plot_cast(self):
        self.plot_signal.emit(self.currentRow(),'plot cast') # Emit the signal with the row list and the command



        

class mainWidget(QtWidgets.QWidget):
    def __init__(self,logging_level=logging.INFO):
        QtWidgets.QWidget.__init__(self)
        self.folder_dialog = QtWidgets.QLineEdit(self)
        self.folder_dialog.setText(os.getcwd()) # Take the local directory as a start
        self.foldername = os.getcwd()        
        self.folder_button = QtWidgets.QPushButton('Choose Datafolder')
        self.folder_button.clicked.connect(self.folder_clicked)
        self.search_button = QtWidgets.QPushButton('Search valid data')
        self.search_button.clicked.connect(self.search_clicked)
        self.clear_table_button = QtWidgets.QPushButton('Clear table')
        self.clear_table_button.clicked.connect(self.clear_table_clicked)                        
        self.file_table = casttableWidget() # QtWidgets.QTableWidget()
        self.file_table.plot_signal.connect(self.plot_signal) # Custom signal for plotting
        self.file_table.station_signal.connect(self.station_signal) # Custom signal for adding casts to station
        self.file_table.cellChanged.connect(self.table_changed)

        self.columns                     = {}
        self.columns['date']             = 0
        self.columns['lon']              = 1
        self.columns['lat']              = 2
        self.columns['station (File)']   = 3
        self.columns['station (Custom)'] = 4
        self.columns['comment']          = 5
        self.columns['file']             = 6
        self.columns['map']              = 7
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

        self.layout = QtWidgets.QGridLayout(self)
        self.layout.addWidget(self.folder_dialog,0,0)
        self.layout.addWidget(self.folder_button,0,1)
        self.layout.addWidget(self.search_button,1,0)
        self.layout.addWidget(self.file_table,2,0,1,2)
        self.layout.addWidget(self.clear_table_button,3,0)


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
        layout.addWidget(self._search_opt_cnv,0,0)
        layout.addWidget(self._search_opt_mrd,1,0)
        self.search_opts_widget.hide()

        # Station/stations widget
        self._station_widget      = QtWidgets.QWidget()
        layout       = QtWidgets.QGridLayout(self._station_widget)
        self._new_station_edit = QtWidgets.QLineEdit(self)
        layout.addWidget(self._new_station_edit,0,0)
        #layout.addWidget(QtWidgets.QLabel('Station/Station name'),0,0)
        button_add = QtWidgets.QPushButton('Add Station')
        button_add.clicked.connect(self._station_add)
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


    def table_changed(self,row,column):
        """ If a comment was added, add it to the comment list and update the data dictionary
        """
        if column == self.columns['comment']:
            comstr = self.file_table.item(row,column).text()
            self.data['pyctd_comment'][row] = comstr
            # Resize the columns
            self.file_table.resizeColumnsToContents()

        
    def _station_add(self):
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
        print('Plot map options')
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
        
    def plot_map(self):
        #try:
        #    self.data['lon']
        #    self.data['lat']
        #except:
        #    print('No data')
        #    #return

        FIG_LON = [-170,180]
        FIG_LAT = [-89,90]
        #FIG_LON = [0,180]
        #FIG_LAT = [0,70]
        #self.fig       = Figure((5.0, 4.0), dpi=self.dpi)
        try:
            self.figwidget
            NEW_FIGURE=False
        except:
            NEW_FIGURE=True
            
        self.fig       = Figure(dpi=self.dpi)
        self.figwidget = QtWidgets.QWidget()
        self.figwidget.setWindowTitle('pyctd map')
        self.canvas    = FigureCanvas(self.fig)
        self.canvas.setParent(self.figwidget)
        plotLayout = QtWidgets.QVBoxLayout()
        plotLayout.addWidget(self.canvas)
        self.figwidget.setLayout(plotLayout)
        self.canvas.setMinimumSize(self.canvas.size()) # Prevent to make it smaller than the original size
        self.mpl_toolbar = NavigationToolbar(self.canvas, self.figwidget)
        plotLayout.addWidget(self.mpl_toolbar)
        #self.figs.append(fig)
        self.axes      = self.fig.add_subplot(111,projection=ccrs.Mercator())
        ax             = self.axes
        try:
            print('Setting xlim',self._map_zoom_x,self._map_zoom_y)
            self.axes.set_xlim(self._map_zoom_x)
            self.axes.set_ylim(self._map_zoom_y)
        except Exception as e:
            print(e)
            ax.set_extent([FIG_LON[0], FIG_LON[1], FIG_LAT[0], FIG_LAT[1]])


        #ax.coastlines()
        ax.coastlines(self._map_settings['res'])
        ax.add_feature(cartopy.feature.OCEAN, zorder=0)

        #ax.draw()
        self.figwidget.show()

        
    def station_signal(self,rows):
        self._station_rows = rows
        self._station_widget.show() # Open the widget and let it decide what to do with the choosen rows


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

    def add_positions_to_map(self,rows):
        # Check if we have a map, if not call plot_map to create one
        try:
            self.axes
        except:
            self.plot_map()
            
        for row in rows:
            color = (0,0,0) # Black
            self.draw_to_map(row,color)
            # Add an item to the table, which is used to change properties
            item = QtWidgets.QTableWidgetItem( 'Plot' )
            item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable) # Unset to not have it editable
            item.setBackground(QtGui.QColor(color[0],color[1],color[2]))
            self.file_table.setItem(row,self.columns['map'], item)            

        self.canvas.draw()
        
    def draw_to_map(self,row,color):
        lon = self.data['info_dict'][row]['lon']
        lat = self.data['info_dict'][row]['lat']
        # If we already have a dataset
        if (len(self.data['pyctd_plot_map'][row]) > 0):
            #print('Changing plot properties, removing the old one')
            tmpdata = self.data['pyctd_plot_map'][row].pop()
            for line in tmpdata:
                line.remove()            


        line = self.axes.plot(lon,lat,'o',color=color,transform=ccrs.PlateCarree())
        self.data['pyctd_plot_map'][row].append(line)                

        
    def rem_positions_from_map(self,rows):
        # Check if we have a map, if not call plot_map to create one
        try:
            self.axes
        except:
            return
            
        for row in rows:
            item = QtWidgets.QTableWidgetItem('')
            item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable) # Unset to not have it editable
            self.file_table.setItem(row,self.columns['map'], item)                        
            while self.data['pyctd_plot_map'][row]:
                tmpdata = self.data['pyctd_plot_map'][row].pop()
                for line in tmpdata:
                    line.remove()
                
            #self.data['plot_map'][row].pop(0)[0].remove()

        self.canvas.draw()
        
    def clear_table_clicked(self):
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
            self._f_widget           = QtWidgets.QLabel('Hallo f')
            self._f_widget.setWordWrap(True)
            self.status_layout.addWidget(self._progress_bar,0,0)
            self.status_layout.addWidget(self._f_widget,1,0)
            #self.status_layout.addWidget(self._thread_stop_button,2,0)
            self.status_widget.show()
            self.search_thread = get_valid_files(foldername,search_seabird=self._search_opt_cnv.isChecked(), search_mrd = self._search_opt_mrd.isChecked())
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
        
        try:
            data_new['pyctd_plot_map']
        except:
            data_new['pyctd_plot_map'] = [[] for i in range(len(data_new['info_dict'])) ] # Plotting information

        try:
            data_new['pyctd_station']
        except:
            data_new['pyctd_station'] = [None] * len(data_new['info_dict']) # station information
            
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
        # Fill the table
        try:
            cnt = len(self.data['info_dict'])
        except:
            cnt = 0
        for i in range(cnt):
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

    def create_cast_summary(self):
        """ Creates a summary from the given sum_dict
        """

        cwd = os.getcwd()
        filename,extension  = QtWidgets.QFileDialog.getSaveFileName(self,"Choose file for yaml summary","","YAML File (*.yaml);;All Files (*)")
        if 'yaml' in extension and ('.yaml' not in filename):
            filename += '.yaml'
            
        yaml_dict = {}
        try:
            self.data['info_dict']
        except:
            return
        # Add cruise information
        try:
            yaml_dict['Cruise ID'] = self._cruise_fields['Cruise ID']
        except Exception as e:
            def diag_clicked_ok():
                self._cruise_fields['Cruise ID'] = str(cruise.text())
                yaml_dict['Cruise ID'] = self._cruise_fields['Cruise ID']                
                self._diag_cruise.close()
            def diag_clicked_cancel():
                self._diag_cruise.close()
                
            diag = QtWidgets.QDialog()
            layout = QtWidgets.QVBoxLayout(diag)
            buttons = QtWidgets.QDialogButtonBox( QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
                                                  QtCore.Qt.Horizontal, diag)
            buttons.accepted.connect(diag_clicked_ok)
            buttons.rejected.connect(diag_clicked_cancel)
            cruise_label = QtWidgets.QLabel('You did not define a cruise ID.\n If you want to do it now,\n enter it below and press "ok"')            
            cruise = QtWidgets.QLineEdit(diag)
            layout.addWidget(cruise_label)
            layout.addWidget(cruise)            
            layout.addWidget(buttons)
            self._diag_cruise = diag
            retval = diag.exec_()

            
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
                
            if(self.FLAG_REL_PATH):
                fname = yaml_dict['casts'][i]['file']
                fname = fname.replace(self.foldername,'.') # TODO, check if filesep is needed for windows
                yaml_dict['casts'][i]['file'] = fname

        create_yaml_summary(yaml_dict,filename)

    def create_cruise_summary(self):
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
        
        
    def load_summary(self):
        filename_all,extension  = QtWidgets.QFileDialog.getOpenFileName(self,"Choose existing summary file","","YAML File (*.yaml);;All Files (*)")
        filename                =  os.path.basename(filename_all) # Get the filename
        dirname                 =  os.path.dirname(filename_all)  # Get the path
        if(len(filename_all) == 0):
            return
        
        # Opening the yaml file
        try:
            stream = open(filename_all, 'r')
            data_yaml = yaml.load(stream)
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

        plotMenu = mainMenu.addMenu('&Plot')
        plotmapAction = QtWidgets.QAction("&Plot map", self)
        plotmapAction.setShortcut("Ctrl+M")
        plotmapAction.setStatusTip('Plot a map')
        plotmapAction.triggered.connect(self.mainwidget.plot_map)        
        plotMenu.addAction(plotmapAction)
        plotmapoptAction = QtWidgets.QAction("&Plot map options", self)
        plotmapoptAction.setStatusTip('Map plotting options')
        plotmapoptAction.triggered.connect(self.mainwidget.plot_map_opts)        
        plotMenu.addAction(plotmapoptAction)



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
