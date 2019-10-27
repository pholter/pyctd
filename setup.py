from setuptools import setup
import os

ROOT_DIR='pyctd'
with open(os.path.join(ROOT_DIR, 'VERSION')) as version_file:
    version = version_file.read().strip()


setup(name='pyctd',
      version=version,
      description='Tools to read and view conductivity, temperature and depth (CTD) files',
      url='https://github.com/MarineDataTools/pyctd',
      author='Peter Holtermann',
      author_email='peter.holtermann@io-warnemuende.de',
      license='GPLv03',
      packages=['pyctd'],
      scripts = [],
      entry_points={ 'console_scripts': ['pycnv_cmd=pyctd.pycnv:main','pyctd=pyctd.gui.pyctd_gui:main', 'pymrd=pyctd.sst.pymrd:main']},
      package_data = {'':['VERSION','stations/iow_stations.yaml','ships/ships.yaml']},
      install_requires=[ 'gsw', 'pyproj','pytz','pyaml','pycnv','geojson','pysst'],
      zip_safe=False)


