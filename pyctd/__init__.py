import pkg_resources
import pycnv
from .gui import pyctd_gui as pyctd_gui
#from .tors.test import pymqds_rand as rand
#from .gui.pyctd_gui import mainWidget

# Get the version
version_file = pkg_resources.resource_filename('pyctd','VERSION')

with open(version_file) as version_f:
   version = version_f.read().strip()

__version__ = version
