import pkg_resources
import pycnv

# Get the version
version_file = pkg_resources.resource_filename('pyctd','VERSION')

with open(version_file) as version_f:
   version = version_f.read().strip()

__version__ = version
