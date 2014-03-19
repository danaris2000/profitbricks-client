.. ProfitBricks Client documentation master file, created by
   sphinx-quickstart on Tue Mar  4 10:42:09 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

ProfitBricks Client documentation
=================================

Contents:

.. toctree::
   :maxdepth: 2

   man
   profitbricks_client

Introduction
------------

The ProfitBricks client can be used to manage your data centers through ProfitBricks' public API.
It comes as a command line tool with Bash completion and as a :mod:`profitbricks_client` Python
module. You can use the :mod:`profitbricks_client` Python module to write your own scripts or to
interactively use it with tools like ipython_.

.. _ipython: http://ipython.org/

Quick start
-----------

Call

.. code-block:: bash

   profitbricks-client --help

to get a help message. Then you probably want to know which API calls are available:

.. code-block:: bash

   profitbricks-client --list

You will be asked for your username and password. The password will be stored in your keyring
(if you have the keyring Python module installed). Then you might want to know how to list all
your data centers:

.. code-block:: bash

   profitbricks-client getAllDataCenters --help

This call takes no arguments. To list all your datacenters, run:

.. code-block:: bash

   profitbricks-client getAllDataCenters

Then you are interested in getting one of your data centers by specifying one of your data centers:

.. code-block:: bash

   profitbricks-client getDataCenter --dataCenterId <dataCenterId>

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
