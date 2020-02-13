.. sectnum::

Python toolbox to read, process and plot several different
conductivity, temperature and depth (CTD) formats including Seabird
and Sea &amp; Sun Technology files. The main task is to search valid
data in a certain folder and to define metadata as stations,
transects, campaigns. 

The backbone of the pyctd toolbox are tools to read and process
different CTD fie formats from different vendors. This includes tools
to for Seabird_ cnv files and `Sea & Sun Technology`_ (SST) microstructure profilers (MSS).

.. _Seabird: http://www.seabird.com/
.. _Sea & Sun Technology: https://www.sea-sun-tech.com/technology.html

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


Seabird
=======

The cnv text files are the standard output files of the Seabird CTD
software. The files are processed with the "pycnv" package.


Sea & Sun Technology (SST)
==========================

The mrd binary files are the standard output files of the MSS-Profiler
software. The files are processed with the "pysst" tools.

	  



