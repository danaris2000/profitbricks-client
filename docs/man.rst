=====================
 profitbricks-client
=====================

SYNOPSIS
========

``profitbricks-client`` [*OPTIONS*] **--help** [*call*]

``profitbricks-client`` [*OPTIONS*] **--list** [*keyword*]

``profitbricks-client`` [*OPTIONS*] *call* [*per-call-arguments*]

DESCRIPTION
===========

The ProfitBricks client can be used to manage your data centers through ProfitBricks’ public API.

OPTIONS
=======

-h [*call*], --help [*call*]
    Display a list of options if no *call* is specified. Optional *call* displays
    detailed usage information for the given call.
-l [*keyword*], --list [*keyword*]
    List all available calls. Optional *keyword* refines the list to display only calls listed
    under the keyword header. Available keywords are: DataCenter, Firewall, Image, InternetAccess,
    LoadBalancer, Nic, Notifications, PublicIp, RomDrive, Server, Snapshot, and Storage.
call
    Execute call. Additional parameters required, depending on choice of call. Use ``--list`` to
    get an overview of available calls.
--username username
    username used for making the API call. The username stored in the configuration file is used if
    no username is specified on the command line. If no username is stored in the configuration
    file, the user will get prompted to enter their username.
--password password
    plain text password used for making the API call. When no password or password file is
    specified on the command line, the password stored in the configuration file will be used or
    the users keyring will be queried (if the Python keyring module is installed). If no password
    is found, the user will get prompted to enter their password.
--password-file password-filename
    file containing the plain text password. The file must contain only one line with the password
    to use. See ``--password`` for details.
--clear-credentials
    Clear all stored user credentials from the configuration file and the keyring.
--api-version [*version*]
    Configure which version of the API is used for making the calls. If *version* is left
    unspecified, the CLI will update to the most recent compatible release of the API.
--endpoint URL
    Point the CLI at a URL of the user's choice.
--clear-cache
    Updates to the latest version of the ProfitBricks WSDL.
-v, --verbose
    Print data on the outgoing call to stderr. By default, print only response data (on stdout).
--xml
    Returns an XML formatted version of the response.
