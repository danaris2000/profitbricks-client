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

Python Module example
---------------------

Imagine you want to write a small Python script that shows the list of IP
addresses for every server. You can walk through this example step by step with
ipython_. First you need to import the :mod:`profitbricks_client` and create a
client object:

.. code-block:: python

   import profitbricks_client
   client = profitbricks_client.get_profitbricks_client()

Then you can retrieve a list of all data centers by calling
:func:`getAllDataCenters`. You get the ID, name, and version for every data
center. You can iterate over all data center IDs or just select the ones that
you are interested in. To keep this example simple, you just take the first
one. For the following example, you just want to have the unique IDs.

.. code-block:: python

    all_datacenters = client.getAllDataCenters()
    datacenter_id = all_datacenters[0].dataCenterId

The function :func:`getDataCenter` gives you all information about your data
center including all servers, storages, load balancers and so on. So let's call
this function for your selected data center:

.. code-block:: python

    datacenter = client.getDataCenter(dataCenterId=datacenter_id)

You can print the name of the data center:

.. code-block:: python

    print datacenter.dataCenterName + ':'

The returned `datacenter` object has an attribute `servers` which contains a
list of all servers in that data center. Every server in this list has a
`serverName` and a list of `ips`. You can sort the `servers` list by the
`serverName` attribute and then print the server name with the IPs belonging to
it:

.. code-block:: python

    from operator import attrgetter
    for server in sorted(datacenter.servers, key=attrgetter('serverName')):
        print server.serverName + '   '+ ' '.join(server.ips)

The full script to print all servers and their IP addresses for every data
center look like this:

.. literalinclude:: ../example/server2ip.py

.. _ipython: http://ipython.org/

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
