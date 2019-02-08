.. sectnum::

Python toolbox to read, process and plot several different
conductivity, temperature and depth (CTD) formats including Seabird
and Sea &amp; Sun Technology files.

The backbone of the pyctd toolbox are tools to read and process
different CTD fie formats from different vendors. This includes tools
to for Seabird_ cnv files and `Sea & Sun Technology`_ (SST) microstructure profilers (MSS).

.. _Seabird: http://www.seabird.com/
.. _`Sea & Sun Technology` https://www.sea-sun-tech.com/technology.html

Install
=======

The package was developed using python 3.5+, it might work with
earlier versions, but its not supported. The newest
`Gibb Sea Water Toolbox (gsw) <https://github.com/TEOS-10/GSW-Python>`_
depends also on python 3.5+, pycnv heavily depends on the gsw toolbox. It
therefore strongly recommended to use python 3.5+.

User
----

Install as a user

.. code:: bash
	  
   python setup.py install --user

Uninstall as a user
   
.. code:: bash
	  
pip uninstall pyctd



Developer
---------

Install as a developer

.. code:: bash
	  
   python setup.py develop --user

Uninstall as a user
   
.. code:: bash
	  
   pip uninstall pyctd
   



Seabird
=======

The cnv text files are the standard output files of the Seabird CTD
software. The files are processed with the "pycnv" tools found in the
subfolder "seabird"

The main purpose for pycnv is to create a standardised interface for
slightly differing naming conventions of sensors in the cnv files and
the usage of the `Gibb Sea Water Toolbox (gsw) <https://github.com/TEOS-10/GSW-Python>`_
for the calculation of all
derived parameters as practical salinity, absolute salinity, potential
and conservative temperature or density. For this purpose pycnv does
only need pressure, conductivity and temperature, all other properties
will be derived from these. Furthermore pycnv will take care for a
different absolute salinity computation in the Baltic Sea, by
automatically checking of a cast was made in the Baltic Sea and
choosing the correct function.





FEATURES
--------

- The data can be accessed by the original names defined in the cnv
  file in the named array called data. E.g. header name "# name 11 =
  oxsatML/L: Oxygen Saturation, Weiss [ml/l]" can be accessed like
  this: data['oxsatML/L'].

- Standard parameters (Temperature, Conductivity, pressure, oxygen)
  are mapped to standard names. E.g. data['T0'] for the first
  temperature sensor and data['C1'] for the second conductivity sensor.

- If the standard parameters (C0,T0,p), (C1,T1,p) are available the
  Gibbs Sea water toolbox is used to calculate absolute salinity, SA,
  conservative temperature, CT, and potential temperature pt. The data
  is stored in a second field called computed data:
  cdata. E.g. cdata['SA00'].

- The module checks if the cast was made in the Baltic Sea, if so, the
  modified Gibbs sea water functions are automatically used.

- The package provides scripts to search a given folder for cnv files
  and can create a summary of the folder in a csv format easily
  readable by python or office programs. The search can be refined by
  a location or a predefined station.

- Possibility to provide an own function for parsing custom header
  information.

- Plotting of the profile using `matplotlib <https://matplotlib.org>`_



USAGE
-----

The package installs the executables:

- pycnv

- pycnv_sum_folder

  
EXAMPLES
--------
Plot the in Situ temperature and the conservative temperature of a CTD cast:

.. code:: python
	  
	  import pycnv
	  import pylab as pl
	  fname='test.cnv' # A sebaird cnv file
	  p = pycnv.pycnv(fname)
	  pl.figure(1)
	  pl.clf()
	  pl.subplot(1,2,1)
	  pl.plot(p.data['T'],p.data['p'])
	  pl.xlabel(p.units['T'])
	  pl.gca().invert_yaxis()	  
	  pl.subplot(1,2,2)
	  pl.plot(p.cdata['CT'],p.data['p'])
	  pl.xlabel(p)
	  pl.gca().invert_yaxis()

	  
Lists all predefined stations (in terminal):

.. code:: bash
	  
	  pycnv_sum_folder --list_stations


Makes a summary of the folder called cnv_data of all casts around
station TF0271 with a radius of 5000 m, prints it to the terminal and
saves it into the file TF271.txt  (in terminal):

.. code:: bash
	  
	  pycnv_sum_folder --data_folder cnv_data --station TF0271 5000 -p -f TF271.txt


Show and plot conservative temperature, salinity and potential density of a cnv file into a pdf:

.. code:: bash
	  
	  pycnv --plot show,save,CT00,SA00,pot_rho00 ctd_cast.cnv


Interpolate all CTD casts on station TF0271 onto the same pressure axis and make a netCDF out of it:

see code pycnv/test/make_netcdf.py


Devices tested 
--------------

- SEACAT V4.0g

- SBE 11plus V 5.1e

- SBE 11plus V 5.1g

- Sea-Bird SBE 9 Software Version 4.206


Sea & Sun Technology (SST)
==========================

The mrd binary files are the standard output files of the MSS-Profiler
software. The files are processed with the "pymrd" tools found in the
subfolder "sst"

	  


