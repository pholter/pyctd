from ..seabird import pycnv as pycnv
from ..seabird import pycnv_sum_folder as pycnv_sum_folder
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
    print(summary)
    with open(filename, 'w') as outfile:
        yaml.dump(summary, outfile, default_flow_style=False)


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
            for key in self.data.keys():
                self.data[key].extend(data_tmp[key])
        
        
    def status_function(self,i,nf,f):
        self.search_status.emit(self,i,nf,f)


class casttableWidget(QtWidgets.QTableWidget):
    plot_signal = QtCore.pyqtSignal(object,str) # Create a custom signal for plotting
    transect_signal = QtCore.pyqtSignal(object) # Create a custom signal for adding the cast to transect
    def __init__(self):
        QtWidgets.QTableWidget.__init__(self)

    def contextMenuEvent(self, event):
        print('Event!')
        self.menu = QtWidgets.QMenu(self)
        plotAction = QtWidgets.QAction('Add to map', self)
        plotAction.triggered.connect(self.plot_map)
        transectAction = QtWidgets.QAction('Add/Rem to Station/Transect', self)
        transectAction.triggered.connect(self.transect)
        remplotAction = QtWidgets.QAction('Rem from map', self)
        remplotAction.triggered.connect(self.rem_from_map)
        plotcastAction = QtWidgets.QAction('Plot cast', self)
        plotcastAction.triggered.connect(self.plot_cast)                
        print(QtGui.QCursor.pos())
        self.menu.addAction(transectAction)
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
        print('Rows',self.rows)
        #action = self.menu.exec_(QtGui.QCursor.pos())#self.mapToGlobal(event))

    def transect(self):
        """ Signal for transect
        """
        row_list = self.rows
        self.transect_signal.emit(row_list) # Emit the signal with the row list and the command        

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
        self.folder_button = QtWidgets.QPushButton('Choose Datafolder')
        self.folder_button.clicked.connect(self.folder_clicked)
        self.search_button = QtWidgets.QPushButton('Search valid data')
        self.search_button.clicked.connect(self.search_clicked)
        self.clear_table_button = QtWidgets.QPushButton('Clear')
        self.clear_table_button.clicked.connect(self.clear_table_clicked)                        
        self.file_table = casttableWidget() # QtWidgets.QTableWidget()
        self.file_table.plot_signal.connect(self.plot_signal) # Custom signal for plotting
        self.file_table.transect_signal.connect(self.transect_signal) # Custom signal for adding casts to transect
        self._ncolumns = 6
        self.file_table.setColumnCount(self._ncolumns)
        self.file_table.setHorizontalHeaderLabels("Date;Lon;Lat;Station/Transect;Comment;File".split(";"))
        for i in range(self._ncolumns):
            self.file_table.horizontalHeaderItem(i).setTextAlignment(QtCore.Qt.AlignHCenter)
            
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        self.layout = QtWidgets.QGridLayout(self)
        self.layout.addWidget(self.folder_dialog,0,0)
        self.layout.addWidget(self.folder_button,0,1)
        self.layout.addWidget(self.search_button,1,0)
        self.layout.addWidget(self.file_table,2,0,1,2)
        self.layout.addWidget(self.clear_table_button,3,0)
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

        # Transect/stations widget
        self._transect_widget      = QtWidgets.QWidget()
        layout       = QtWidgets.QGridLayout(self._transect_widget)
        self._new_transect_edit = QtWidgets.QLineEdit(self)
        layout.addWidget(self._new_transect_edit,0,0)
        #layout.addWidget(QtWidgets.QLabel('Transect/Station name'),0,0)
        button_add = QtWidgets.QPushButton('Add Sta./Trans.')
        button_add.clicked.connect(self._transect_add)
        layout.addWidget(button_add,0,1)        
        self.transect_combo = QtWidgets.QComboBox()
        self.transect_combo.addItem('Remove')        
        layout.addWidget(self.transect_combo,1,0,1,2)
        button_apply = QtWidgets.QPushButton('Apply')
        button_apply.clicked.connect(self._transect_apply)
        button_cancel = QtWidgets.QPushButton('Close')
        button_cancel.clicked.connect(self._transect_cancel)
        layout.addWidget(button_apply,2,0)
        layout.addWidget(button_cancel,2,1)        
        self._transect_widget.hide()

        
    def _transect_add(self):
        tran_name = self._new_transect_edit.text()
        FLAG_NEW = True
        if(len(tran_name) > 0):
            for count in range(self.transect_combo.count()):
                if(self.transect_combo.itemText(count) == tran_name):
                    FLAG_NEW = False

            if FLAG_NEW:
                self.transect_combo.addItem(tran_name)
                cnt = self.transect_combo.count()
                print(cnt)
                self.transect_combo.setCurrentIndex(cnt-1)


    def _transect_apply(self):
        print('apply')
        if True:
            for i in self._transect_rows:
                tran = self.transect_combo.currentText()
                if tran == 'Remove':
                    self.data['pyctd_transect'][i] = None
                else:
                    self.data['pyctd_transect'][i] = tran


        self.update_table()        
        self._transect_widget.hide()

    def _transect_cancel(self):
        self._transect_widget.hide()

        
    def plot_map_opts(self):
        print('Plot map options')        

    def plot_map(self):
        try:
            self.data['lon']
            self.data['lat']
        except:
            print('No data')
            #return

        FIG_LON = [-170,180]
        FIG_LAT = [-89,90]
        #FIG_LON = [0,180]
        #FIG_LAT = [0,70]

        #self.fig       = Figure((5.0, 4.0), dpi=self.dpi)
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
        ax.set_extent([FIG_LON[0], FIG_LON[1], FIG_LAT[0], FIG_LAT[1]])
        #ax.coastlines()
        ax.coastlines('10m')

        #ax.draw()
        self.figwidget.show()

        
    def transect_signal(self,rows):
        print('Transect signal')
        self._transect_rows = rows
        self._transect_widget.show() # Open the widget and let it decide what to do with the choosen rows

            
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
        print('Plot cast row',row)
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
            
        print('Add positions', rows)
        for row in rows:
            print(row)
            lon = self.data['lon'][row]
            lat = self.data['lat'][row]
            self.data['pyctd_plot_map'][row].append(self.axes.plot(lon,lat,'o',transform=ccrs.PlateCarree()))

        self.canvas.draw()
        
    def rem_positions_from_map(self,rows):
        # Check if we have a map, if not call plot_map to create one
        try:
            self.axes
        except:
            return
            
        print('Remove positions', rows)
        for row in rows:
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
        print('Search opts')
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
        self.data = self.search_thread.data
        # Add additional information
        self.data['pyctd_plot_map'] = [[]] * len(self.data['files']) # Plotting information
        self.data['pyctd_transect'] = [None] * len(self.data['files']) # transect information
        try:
            cnt = len(self.data['files'])
        except:
            cnt = 0
        for i in range(cnt):
            self.file_table.insertRow(i)
            
        self.update_table()

    def update_table(self):        
        # Fill the table
        try:
            cnt = len(self.data['files'])
        except:
            cnt = 0
        for i in range(cnt):
            date = self.data['dates'][i]
            self.file_table.setItem(i,0, QtWidgets.QTableWidgetItem( date.strftime('%Y-%m-%d %H:%M:%S' )))
            lon = self.data['lon'][i]
            self.file_table.setItem(i,1, QtWidgets.QTableWidgetItem( "{:6.3f}".format(lon)))
            lat = self.data['lat'][i]
            self.file_table.setItem(i,2, QtWidgets.QTableWidgetItem( "{:6.3f}".format(lat)))
            tran = self.data['pyctd_transect'][i]
            if(tran is not None):
                self.file_table.setItem(i,3, QtWidgets.QTableWidgetItem( str(tran) ))
            else:
                self.file_table.setItem(i,3, QtWidgets.QTableWidgetItem( str('') ))
                
            fname = self.data['files'][i]
            self.file_table.setItem(i,self._ncolumns-1, QtWidgets.QTableWidgetItem( fname ))

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
        FLAG_REL_PATH = True
        filename,extension  = QtWidgets.QFileDialog.getSaveFileName(self,"Choose file for yaml summary","","YAML File (*.yaml);;All Files (*)")
        if 'yaml' in extension and ('.yaml' not in filename):
            filename += '.yaml'
            
        print('filename',filename,extension)
        yaml_dict = {}
        # Add cruise information
        try:
            yaml_dict['Cruise ID'] = self._cruise_fields['Cruise ID']
        except Exception as e:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setInformativeText('You did not define a cruise ID, you want to continue? TODO, let the user define a cruise ID and/or cancel this ...')
            retval = msg.exec_()
            print(retval)

            
        yaml_dict['created'] = str(datetime.datetime.now(pytz.utc))
        yaml_dict['version'] = version
        
        yaml_dict['casts'] = self.data['info_dict']
        # Convert datetime objects into something readable
        for i,d in enumerate(yaml_dict['casts']):
            yaml_dict['casts'][i]['date'] = str(d['date'])
            if(FLAG_REL_PATH):
                fname = yaml_dict['casts'][i]['file']
                fname = fname.replace(self.foldername,'.') # TODO, check if filesep is needed for windows
                yaml_dict['casts'][i]['file'] = fname
                print(self.foldername,fname)

        #create_yaml_summary(yaml_dict,filename)

    def create_cruise_summary(self):
        try:
            self._cruise_fields['Cruise ID']
        except:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setInformativeText('You have to define at least a cruise ID')
            retval = msg.exec_()
            return

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
        print('Load summary')

    def cruise_information(self):
        print('Cruise information')

        # Check if we have a cruise fields, otherwise create one
        try:
            self._cruise_fields['Cruise name']
        except:
            self._cruise_fields['Cruise name'] = ''
            self._cruise_fields['Cruise ID'] = ''            
            self._cruise_fields['Ship name'] = ''
            self._cruise_fields['Ship callsign'] = ''
            self._cruise_fields['Project'] = ''            
            self._cruise_fields['Principal investigator'] = ''
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
            
        self.cruise_widget.show()

    def _cruise_apply(self):
        for i,f in enumerate(self._cruise_dialogs.keys()):
            print(self._cruise_dialogs[f].text())
            self._cruise_fields[f] = str(self._cruise_dialogs[f].text())
        
    def _cruise_cancel(self):
        self.cruise_widget.hide()
        
        


class pyctdMainWindow(QtWidgets.QMainWindow):
    def __init__(self,logging_level=logging.INFO):
        QtWidgets.QMainWindow.__init__(self)
        mainMenu = self.menuBar()
        self.setWindowTitle("pyctd")
        quitAction = QtWidgets.QAction("&Quit", self)
        quitAction.setShortcut("Ctrl+Q")
        quitAction.setStatusTip('Closing the program')
        quitAction.triggered.connect(self.close_application)



        fileMenu = mainMenu.addMenu('&File')
        fileMenu.addAction(quitAction)
        #fileMenu.addAction(chooseStreamAction)

        self.mainwidget = mainWidget()
        self.setCentralWidget(self.mainwidget)

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


        sumMenu = mainMenu.addMenu('&Dataset')
        sumcruiseAction = QtWidgets.QAction("&Create cruise summary", self)
        sumcruiseAction.triggered.connect(self.mainwidget.create_cruise_summary)                
        sumcastAction = QtWidgets.QAction("&Create cast summary", self)
        sumcastAction.triggered.connect(self.mainwidget.create_cast_summary)        
        sumlAction = QtWidgets.QAction("&Load summary", self)
        sumlAction.triggered.connect(self.mainwidget.load_summary)
        sumMenu.addAction(sumcruiseAction)
        sumMenu.addAction(sumcastAction)
        sumMenu.addAction(sumlAction)


        cruiseMenu = mainMenu.addMenu('&Cruise')
        cruiseAction = QtWidgets.QAction("&Cruise information", self)
        cruiseAction.setShortcut("Ctrl+I")        
        cruiseAction.triggered.connect(self.mainwidget.cruise_information)
        cruiseMenu.addAction(cruiseAction)                
        tranAction = QtWidgets.QAction("&Create Station/Transect", self)
        cruiseMenu.addAction(tranAction)        

        
        
        self.statusBar()

    def close_application(self):
        sys.exit()                                



def main():
    app = QtWidgets.QApplication(sys.argv)
    window = pyctdMainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()    
