#!/usr/bin/python

# Copyright (C) 2014, ProfitBricks GmbH
# Authors: Benjamin Drung <benjamin.drung@profitbricks.com>
# Based on code from Zachary Bowen <zachary.bowen@profitbricks.com>.
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

"""command line tool for the public ProfitBricks API"""

# We want everything in one file to be self contained. pylint: disable=C0302

from __future__ import print_function

import getpass
import logging
import os
import pprint
import re
import shutil
import sys
import types
import xml.etree.ElementTree

try:
    import configparser
    if sys.version_info[:2] >= (3, 2):
        from configparser import ConfigParser
    else:
        from configparser import SafeConfigParser as ConfigParser
except ImportError:
    import ConfigParser as configparser
    from ConfigParser import SafeConfigParser as ConfigParser

try:
    from urllib.error import URLError  # pylint: disable=E0611
    from urllib.request import urlopen  # pylint: disable=E0611
except ImportError:
    from urllib2 import URLError, urlopen

try:
    import argparse
except ImportError:
    print("This utility requires the argparse Python module, which is a separate module (and not "
          "part of the Python standard library) for Python < 2.7 and < 3.2", file=sys.stderr)
    sys.exit(1)

try:
    import appdirs
except ImportError:
    print("This utility requires the appdirs (>= 1.3.0) Python module, which isn't currently "
          "installed.", file=sys.stderr)
    sys.exit(1)
if not hasattr(appdirs, "user_config_dir"):
    print("This utility requires the appdirs Python module in version 1.3.0 or later, "
          "but only version " + appdirs.__version__ + " is installed.", file=sys.stderr)
    sys.exit(1)

try:
    import suds
except ImportError:
    print("This utility requires the suds (>= 0.4) Python module, which isn't currently "
          "installed.", file=sys.stderr)
    sys.exit(1)
if [int(X) for X in suds.__version__.split(".")] < [0, 4]:
    print("This utility requires the suds Python module in version 0.4 or later, "
          "but only version " + suds.__version__ + " is installed.", file=sys.stderr)
    sys.exit(1)

if sys.version_info[0] < 3:
    import __builtin__
    input = getattr(__builtin__, 'raw_input')  # pylint: disable=C0103,W0622

_COMPANY = "ProfitBricks"
_INDENTATION = "    "
_SCRIPT_NAME = "profitbricks-client"
_SUPPORT_MATRIX_URL = "https://api.profitbricks.com/support_matrix.ini"
_DEFAULT_TIMEOUT = 180
_UNSET = object()
# Use semantic versioning for the client (different than the API version!). See http://semver.org/
__version__ = "1.0.0"

_KEYWORD_LIST = [
    "DataCenter",
    "Firewall",
    "Image",
    "InternetAccess",
    "LoadBalancer",
    "Nic",
    "Notifications",
    "PublicIp",
    "RomDrive",
    "Server",
    "Snapshot",
    "Storage",
]


class ClientTooNewException(Exception):
    """Raised when the ProfitBricks client is too new in general or for a specified API version."""
    pass


class ClientTooOldException(Exception):
    """Raised when the ProfitBricks client is too old in general or for a specified API version."""
    pass


class SupportMatrixMalformedException(Exception):
    """Raised when the downloaded support matrix file is malformed and failed to be parsed."""
    pass


class _Method(object):
    """Callable object representing one ProfitBricks API call."""

    def __init__(self, soap_client, name, parameters):
        self.__name__ = name
        self._soap_client = soap_client
        self._soap_parameters = parameters
        self._cache = dict()

    def __call__(self, profitbricks_client, **kwargs):
        unexpected_arguments = [a for a in kwargs.keys() if a not in self.get_parameter_names()]
        if unexpected_arguments:
            if len(unexpected_arguments) == 1:
                msg = "{name}() got an unexpected keyword argument '{argument}'".format(
                    name=self.__name__,
                    argument=unexpected_arguments[0],
                )
            else:
                msg = "{name}() got {n} unexpected keyword arguments {arguments}".format(
                    name=self.__name__,
                    n=len(unexpected_arguments),
                    arguments=", ".join(["'" + a + "'" for a in unexpected_arguments]),
                )
            raise TypeError(msg)

        call = getattr(self._soap_client.service, self.__name__)
        try:
            if self._has_complex_input_parameter():
                result = call(kwargs)
            else:
                result = call(**kwargs)
        except AttributeError as error:
            if error.args[0] == "'NoneType' object has no attribute 'read'":
                raise WrongCredentialsException("Bad user name and password.")
            else:
                raise
        return result

    def command_line_doc(self):
        """Return a human-readable string documenting how to use the API call via the command line.

        The returned string contains the description of the input and
        output parameters and a usage example how to call it from the
        command line. Use the __doc__ docstring instead to get the
        documentation when using the client as Python module.

        """
        cli_params = ""
        for (name, parameter) in self._input_parameters:
            parameter_string = "--" + name + " " + _get_type_str(parameter.resolve(), True)
            if not parameter.required():
                parameter_string = "[" + parameter_string + "]"
            cli_params += " " + parameter_string

        return (self.__name__ + "\n\n" +
                self._input_parameter_str() + "\n" + self._output_parameters +
                "\nExample:\n" + _INDENTATION + _SCRIPT_NAME + " " + self.__name__ + cli_params)

    @property
    def __doc__(self):
        return self._input_parameter_str() + "\n" + self._output_parameters

    def _flatten_input_parameters(self, parameters):
        """Return a list of input parameters as (name, type) pairs for this call.

        parameters -- List of input parameters with the type suds.xsd.sxbasic.Element

        Complex parameters structures are flatten to one simple list.
        When the method is called, the suds library will construct the
        complex parameter structure out of the given list of method
        arguments.

        """
        parameter_list = []
        for parameter in parameters:
            parameter_type = parameter.resolve()
            if parameter_type.enum():
                parameter_list.append((parameter.name, parameter))
            else:
                children = parameter_type.children()
                if len(children) == 0:
                    parameter_list.append((parameter.name, parameter))
                else:
                    parameter_list += self._flatten_input_parameters([p[0] for p in children])
        return parameter_list

    def get_parameter_names(self):
        """Return a list of input parameter names for this call."""
        return [p[0] for p in self._input_parameters]

    def _has_complex_input_parameter(self):
        """Returns true if the call takes exactly one complex input parameter."""
        is_complex_type = False
        if len(self._soap_parameters) == 1:
            parameter_type = self._soap_parameters[0][1].resolve()
            is_complex_type = not parameter_type.enum() and len(parameter_type.children()) > 0
        return is_complex_type

    def _input_parameter_str(self):
        """Return a human-readable string representation of the input parameter type."""
        doc = "Input parameters:\n\n"
        if len(self._input_parameters) == 0:
            doc += _INDENTATION + "None\n"
        else:
            for (name, parameter) in self._input_parameters:
                if parameter.required():
                    required = "  required!"
                else:
                    required = ""
                if parameter.unbounded():
                    unbounded = "[]"
                else:
                    unbounded = ""
                param_type = _get_type_str(parameter.resolve())
                doc += _INDENTATION + name + unbounded + " :" + param_type + required + "\n"
        return doc

    @property
    def _input_parameters(self):
        """Return a list of input parameters as (name, type) pairs for this call.

        The list of input parameters is calculated once and then cached.

        """
        if "input_parameters" not in self._cache:
            parameters = [p[1] for p in self._soap_parameters]
            self._cache["input_parameters"] = self._flatten_input_parameters(parameters)
        return self._cache["input_parameters"]

    @property
    def _output_parameters(self):
        """Return a human-readable string representation of the output parameter type.

        The returned string is generated once and then cached.

        """
        if "output_parameters" not in self._cache:
            method = getattr(self._soap_client.service, self.__name__).method
            returned_types = method.binding.output.returned_types(method)
            output_params = self._parse_output_type(returned_types, 1)
            if len(output_params) == 0:
                output_params = _INDENTATION + "None"
            self._cache["output_parameters"] = "Returned parameters:\n\n" + output_params
        return self._cache["output_parameters"]

    def _parse_output_type(self, parameters, nest_level):
        """Return a human-readable string representation of the output parameter type.

        parameters -- List of output parameters with the type suds.xsd.sxbasic.Element
        nest_level -- Integer representing the nest level of the output parameter tree structure

        """
        text = ""
        for parameter in parameters:
            parameter_type = parameter.resolve()
            if parameter.unbounded():
                unbounded = "[]"
            else:
                unbounded = ""
            type_text = _get_type_str(parameter_type)
            if type_text == "":
                name = parameter_type.name
            else:
                name = parameter.name
            text += _INDENTATION * nest_level + name + unbounded + " :" + type_text + "\n"

            children = parameter_type.children()
            if len(children) > 0 and not parameter_type.enum():
                text += self._parse_output_type([p[0] for p in children], nest_level + 1)
        return text


class _MyConfigParser(ConfigParser):  # pylint: disable=R0904
    """Extended SafeConfigParser

    This config parser can be associated with a file and save the configs
    there.
    """

    def __init__(self):  # pylint: disable=E1002,W0231
        if sys.version_info[0] >= 3:
            super().__init__()
        else:
            ConfigParser.__init__(self)
        self._filename = None

    def get(self, section, option, raw=False, vars=None, fallback=_UNSET):
        # pylint: disable=E1002,W0221,W0622,R0913
        """Get an option value for a given section.

        If the key is not found and `fallback' is provided, it is used as
        a fallback value. This feature is backported from Python 3.2.
        """
        try:
            if sys.version_info[0] >= 3:
                value = super().get(section, option, raw=raw, vars=vars)
            else:
                value = ConfigParser.get(self, section, option, raw, vars)
        except (configparser.NoOptionError, configparser.NoSectionError):
            if fallback is _UNSET:
                raise
            else:
                value = fallback
        return value

    def get_filename(self):
        """Return the associated filename."""
        return self._filename

    def save(self, filename=None):
        """Save the given user configuration."""
        if filename is None:
            filename = self._filename
        parent_path = os.path.dirname(filename)
        if not os.path.isdir(parent_path):
            os.makedirs(parent_path)
        with open(filename, "w") as configfile:
            self.write(configfile)

    def set_filename(self, filename):
        """Set the associated filename (used in the save method)."""
        self._filename = filename

    def store(self, section, option, value):
        """Set an option and create the section if it does not exist yet."""
        if not self.has_section(section):
            self.add_section(section)
        self.set(section, option, value)
        self.save()


class _NotPrefixMatchingArgumentParser(argparse.ArgumentParser):
    """Monkey patched ArgumentParser

    This extended argument parser does two things:
    1) It disables the prefix matching.
       See: http://bugs.python.org/issue14910
    2) It adds a completions attribute containing all arguments.
    """

    def _get_option_tuples(self, option_string):
        """Disable prefix matching. See: http://bugs.python.org/issue14910"""
        return []

    def add_completions(self, arguments, **kwargs):
        """Add given arguments to the list of completions."""
        if 'help' not in kwargs or kwargs['help'] != argparse.SUPPRESS:
            if 'completions' not in self.__dict__:
                self.completions = []  # pylint: disable=W0201
            self.completions += [a for a in arguments if a.startswith('-')]

    def add_argument(self, *args, **kwargs):
        """Monkey patched add_argument method to call add_completions."""
        self.add_completions(args, **kwargs)
        super(_NotPrefixMatchingArgumentParser, self).add_argument(*args, **kwargs)

    def add_argument_group(self, *args, **kwargs):  # pylint: disable=E1003
        """Monkey patched add_argument_group to call add_completions."""
        def group_add_argument(self, *args, **kwargs):
            """Monkey patched add_argument function to call add_completions."""
            self.parent.add_completions(args, **kwargs)
            super(type(self), self).add_argument(*args, **kwargs)
        group = super(_NotPrefixMatchingArgumentParser, self).add_argument_group(*args, **kwargs)
        group.parent = self
        group.add_argument = types.MethodType(group_add_argument, group)
        return group

    def valid_call_name(self, string, allow_empty=False):
        """Check if the given string is a valid call name (if a client object is specified)."""
        if not (allow_empty and string == "") and hasattr(self, "client"):
            if string not in self.client.client_method_names:  # pylint: disable=E1101
                msg = "Invalid call '" + string + "'.\nTo see a list of valid calls, use --list."
                raise argparse.ArgumentTypeError(msg)
        return string


class _ProfitbricksClient(object):  # pylint: disable=R0903
    """A ProfitBricks client providing methods for every available API call."""

    def __init__(self, soap_client):
        self._soap_client = soap_client
        self.client_parameter_names = set()
        self.client_method_names = []
        soap_methods = soap_client.sd[0].ports[0][1]
        for (name, parameters) in soap_methods:
            name = str(name)
            self.client_method_names.append(name)
            method = _Method(soap_client, name, parameters)
            setattr(self, name, types.MethodType(method, self))
            self.client_parameter_names |= set(method.get_parameter_names())


class UnknownAPIVersionException(Exception):
    """Raised when an unknown API version was requested."""
    pass


class WrongCredentialsException(Exception):
    """Raised when an API calls fails due to a wrong username and password."""
    pass


def _add_dynamic_arguments(parser, client):
    """Add the API call parameter names from the given client to the argument parser."""
    parser.client = client
    group = parser.add_argument_group("Call Parameter")
    for parameter in client.client_parameter_names:
        group.add_argument("--" + parameter)


def _ask(question, options, default):
    """Ask the user a question with a list of allowed answers (like yes or no).

    The user is presented with a question and asked to select an answer from
    the given options list. The default will be returned if the user enters
    nothing. The user is asked to repeat his answer if his answer does not
    match any of the allowed anwsers.
    """
    assert default in options

    separator = " ("
    for option in options:
        if option == default:
            question += separator + option.upper()
        else:
            question += separator + option
        separator = "/"
    question += ")? "

    selected = None
    while selected not in options:
        selected = input(question).strip().lower()
        if selected == "":
            selected = default
        else:
            if selected not in options:
                if len(options) == 2:
                    options_string = "'" + options[0] + "' or '" + \
                                     options[1] + "'"
                else:
                    options_string = "'" + "', '".join(options[:-1]) + \
                                     "', or '" + options[-1] + "'"
                question = "Please type " + options_string + ": "
    return selected


def clear_cache():
    """Delete all information regarding the client and WSDL by removing the cache directory."""
    cachedir = appdirs.user_cache_dir(_SCRIPT_NAME, _COMPANY)
    if os.path.isdir(cachedir):
        shutil.rmtree(cachedir)


def clear_credentials(config=None):
    """Delete username and password from configuration file and from the keyring."""
    if config is None:
        config = get_config()
    username = config.get("credentials", "username", fallback=None)
    if username:
        try:
            import keyring
            keyring.delete_password(_SCRIPT_NAME, username)
        except ImportError:
            pass
    config.remove_section("credentials")
    config.save()


def _convert_to_xml(data, parent=None):
    """Take a (nested) python data structure and converts it to an XML representation

    data -- any python data structure, ie (nested) lists and dicts and derived classes
    parent -- the preceding level of the data hierarchy. Only specified by recursive calls.

    Returns a ElementTree XML object or raises a TypeError.
    """
    if parent is None:
        parent = xml.etree.ElementTree.Element('body')

    if isinstance(data, suds.sudsobject.Object):
        child = xml.etree.ElementTree.SubElement(parent, data.__class__.__name__)
        if not hasattr(data, "__iter__"):
            raise TypeError('Unexpected value type: {0}'.format(type(data)))
        for element in data:
            _convert_to_xml(element, child)
    elif isinstance(data, tuple):
        (key, value) = data
        if isinstance(value, suds.sudsobject.Object):
            _convert_to_xml(value, parent)
        else:
            child = xml.etree.ElementTree.SubElement(parent, key)
            if hasattr(value, "__iter__"):
                _convert_to_xml(value, child)
            else:
                child.text = str(value)
    elif hasattr(data, "__iter__"):
        for element in data:
            _convert_to_xml(element, parent)
    else:
        assert parent.text is None
        parent.text = str(data)

    return parent


def _endpoint_from_support_matrix(client_version, api_version):
    """Determine an endpoint for a given API version."""

    def string2version_number(version_string):
        """Convert an API version string into a comparable version number."""
        return [int(x) for x in version_string.split(".")]

    older, newer, supported = _get_support_matrix(client_version)

    if api_version == "latest":
        if len(supported) == 0:
            msg = _SCRIPT_NAME + " " + client_version
            if len(newer) > 0:
                raise ClientTooOldException(msg + " is too old and not supported any more. "
                                            "Please upgrade to a newer version.")
            else:
                raise ClientTooNewException(msg + " is too new and not tested against the API.")
        endpoint = supported[max(supported.keys(), key=string2version_number)]
    else:
        if api_version in supported:
            endpoint = supported[api_version]
        elif api_version in newer:
            msg = (_SCRIPT_NAME + " " + client_version + " is too old for API version " +
                   api_version + ". Please upgrade the client to version " + newer[api_version] +
                   " or later.")
            raise ClientTooOldException(msg)
        elif api_version in older:
            msg = (_SCRIPT_NAME + " " + client_version + " is too new for API version " +
                   api_version + ". Please downgrade the client to version " +
                   older[api_version] + " or any later " + older[api_version].split(".")[0] +
                   ".x version.")
            raise ClientTooNewException(msg)
        else:
            msg = ("The specified API version " + api_version + " is not known. "
                   "Supported API versions by " + _SCRIPT_NAME + " " + client_version +
                   ": " + ", ".join(sorted(supported.keys(), key=string2version_number)))
            raise UnknownAPIVersionException(msg)

    return endpoint


def _generate_bash_completion(parser, args):
    """Print possible arguments for the command line (for bash completion).

    Returns 0 on success and 1 when an error occurred.
    """
    print("\n".join(parser.completions))
    config = get_config()
    endpoint = get_endpoint(None, args.endpoint, config, False, None)
    if endpoint:
        try:
            client = get_profitbricks_client("", "", endpoint=endpoint, config=config,
                                             store_endpoint=False)
        except URLError as error:
            print(_SCRIPT_NAME + ": Error: Could not connect to server: " + error.reason +
                  " [Errno" + str(error.errno) + "]", file=sys.stderr)
            return 1
        _add_dynamic_arguments(parser, client)
        args = parser.parse_known_args()[0]
        if args.call and hasattr(client, args.call):
            method = getattr(client, args.call)
            for parameter in method.get_parameter_names():
                print("--" + parameter)
        else:
            print("\n".join(client.client_method_names))
    return 0


def get_config():
    """Return a user configuration object."""
    config_filename = appdirs.user_config_dir(_SCRIPT_NAME, _COMPANY) + ".ini"
    config = _MyConfigParser()
    config.optionxform = str
    config.read(config_filename)
    config.set_filename(config_filename)
    return config


def get_endpoint(api_version=None, endpoint=None, config=None, store=True, default="latest"):
    """Return the endpoint for the WSDL service.

    :param api_version: Specify the version of the API that should be used
    :param endpoint: Specify an URL that should be used as endpoint
    :param config: configuration object that stores the endpoint URL
    :param store: Specify if the selected endpoint should be stored in the configuration.
    :param default: Default API version that should be used if no endpoint or version is specified

    If no API version or endpoint is specified, the previously stored
    endpoint will be returned. If no endpoint was stored (e.g. first
    script execution), the endpoint for given default API version
    will be returned.

    If `api_version` is specified, the endpoint for this API version
    will be retrieved. If `endpoint` is specified, this endpoint will
    be returned. If both `api_version` and `endpoint` is specified,
    the endpoint for the given API version must match the given
    endpoint. Otherwise an exception will be raised.

    When `store_selection` is set to True, the returned endpoint will
    be stored in the configuration file and can be used for the
    following calls of this function.
    """

    if config is None:
        config = get_config()

    if endpoint is None and api_version is None:
        if config.has_option("preferences", "endpoint"):
            endpoint = config.get("preferences", "endpoint")
        else:
            api_version = default

    if api_version:
        new_endpoint = None
        if api_version:
            new_endpoint = _endpoint_from_support_matrix(__version__, api_version)
        if new_endpoint:
            if endpoint and endpoint != new_endpoint:
                raise Exception('The given endpoint "{0}" does not match the endpoint "{1}" '
                                'for API version {2}.'.format(endpoint, new_endpoint, api_version))
            endpoint = new_endpoint

    if store and endpoint != config.get("preferences", "endpoint", fallback=None):
        config.store("preferences", "endpoint", endpoint)

    return endpoint


def _get_parser():
    """Return the parser used for the static command line arguments.

    The returned parser contains only the static arguments, but not the dynamically generated
    ones from the SOAP API. This parser allows one to partially parse the command line arguments
    to determine which API version to use and what credentials should be used.
    """
    # Set usage as a workaround to avoid cluttering the usage with all API calls and parameters.
    usage = _SCRIPT_NAME + """ [-l [KEYWORD]] [-h [CALL]] [--clear-credentials]
                           [--username USERNAME] [--password PASSWORD]
                           [--password-file PASSWORD_FILE]
                           [--api-version [VERSION]] [--endpoint URL]
                           [--clear-cache] [-v] [--xml] [call]"""
    parser = _NotPrefixMatchingArgumentParser(add_help=False, usage=usage)
    parser.add_argument("--bash-completion", action="store_true", help=argparse.SUPPRESS)

    group = parser.add_argument_group("Making calls")
    group.add_argument("call", nargs="?", type=parser.valid_call_name,
                       help="Execute call. Additional parameters required, "
                            "depending on choice of call.")
    group.add_argument("-l", "--list", nargs="?", const="all", metavar="KEYWORD",
                       choices=["all"] + _KEYWORD_LIST,
                       help="List all available calls. Optional KEYWORD refines the list to "
                            "display only calls listed under the keyword header.")
    group.add_argument("-h", "--help", const="", nargs="?", metavar="CALL",
                       type=lambda a: parser.valid_call_name(a, True),
                       help="Display this help message. Optional CALL displays detailed usage "
                            "information for the given call.")

    group = parser.add_argument_group("Credentials")
    group.add_argument("--username", help="username used for making the API call")
    group.add_argument("--password", help="plain text password used for making the API call")
    group.add_argument("--password-file", type=argparse.FileType('rt'),
                       help="file containing the plain text password")
    group.add_argument("--clear-credentials", action="store_true",
                       help="Clear all stored user credentials.")

    group = parser.add_argument_group("Configuring the API")
    group.add_argument("--api-version", nargs="?", const="latest", metavar="VERSION",
                       help="Configure which version of the API the CLI calls. If the version "
                            "number is left unspecified, the CLI will update to the most recent "
                            "compatible release of the API.")
    group.add_argument("--endpoint", metavar="URL",
                       help="Point the CLI at a URL of the user's choice.")
    group.add_argument("--clear-cache", action="store_true",
                       help="Updates to the latest version of the ProfitBricks WSDL.")
    group.add_argument("--timeout", type=int, default=_DEFAULT_TIMEOUT,
                       help="connection timeout in seconds (default %(default)s).")

    group = parser.add_argument_group("Input/Output Arguments")
    group.add_argument("-v", "--verbose", action="count", default=0,
                       help="Print data on the outgoing call to stderr. By default, print only "
                            "response data (on stdout).")
    group.add_argument("--xml", action="store_true",
                       help="Returns an XML formatted version of the response.")

    return parser


def get_password(username, config=None):
    """Return the password for the given username.

    This function tries to get the password from the user's keyring. The
    user is asked for the password if the password is not available.
    """

    question = ("Please enter your password for {username}: ".format(username=username))
    try:
        import keyring
        password = keyring.get_password(_SCRIPT_NAME, username)
        if password is None:
            password = getpass.getpass(question)
            try:
                keyring.set_password(_SCRIPT_NAME, username, password)
            except keyring.errors.PasswordSetError as error:
                print(_SCRIPT_NAME + ": Warning: Storing password in keyring failed: " +
                      str(error), file=sys.stderr)
    except ImportError:
        if config is None:
            config = get_config()
        if config.has_option("credentials", "password"):
            password = config.get("credentials", "password")
        else:
            password = getpass.getpass(question)
            store_plaintext_passwords = config.get("preferences", "store-plaintext-passwords",
                                                   fallback=None)
            if store_plaintext_passwords != "no":
                question = ("Do you want to store your passwort in plain text in " +
                            config.get_filename())
                answer = _ask(question, ["yes", "no", "never"], "no")
                if answer == "yes":
                    config.store("credentials", "username", username)
                    config.store("credentials", "password", password)
                elif answer == "never":
                    config.store("preferences", "store-plaintext-passwords", "no")
    return password


def get_profitbricks_client(username=None, password=None, api_version=None, endpoint=None,
                            config=None, store_endpoint=True, timeout=_DEFAULT_TIMEOUT):
    # pylint: disable=R0913
    """Connect to the API and return a ProfitBricks client object.

    If `username` is not specified, :func:`get_username()` is used to
    retrieve the username. If `password` is not specified,
    :func:`get_password()` is used for determining the password.
    `api_version`, `endpoint`, and `store_endpoint` are passed to a
    :func:`get_endpoint()` call to calculate the endpoint.

    A connection to the ProfitBricks public API is made and ProfitBricks
    client object is created. All available API calls will become methods
    of the returned client object.

    An :class:`urllib2.URLError` will be raised when the connection to
    the API failed. No error will be raised when the credentials are
    wrong, but method calls will raise a
    :class:`WrongCredentialsException`.
    """

    if config is None:
        config = get_config()
    if username is None:
        username = get_username(config)
    if password is None:
        password = get_password(username, config)
    endpoint = get_endpoint(api_version, endpoint, config, store_endpoint)

    cachedir = appdirs.user_cache_dir(_SCRIPT_NAME, _COMPANY)
    cache = suds.cache.ObjectCache(cachedir)
    soap_client = suds.client.Client(endpoint, username=username, cache=cache,
                                     password=password, timeout=timeout, cachingpolicy=1)
    return _ProfitbricksClient(soap_client)


def _get_support_matrix(running_client_version):
    """Read the support_matrix.ini file and return older, newer, supported dictionaries."""

    # Get (major, minor) from client version
    running_client_version_number = [int(x) for x in running_client_version.split(".")[:2]]
    parser = ConfigParser()
    support_matrix = urlopen(_SUPPORT_MATRIX_URL)
    try:
        if hasattr(parser, "read_file"):
            parser.read_file(support_matrix)  # pylint: disable=E1103
        else:
            parser.readfp(support_matrix)
    except configparser.MissingSectionHeaderError:
        raise SupportMatrixMalformedException(
            "Failed to parse {url}. This file is malformed. Please contact support. "
            "You can work around this issue by specifying an endpoint with "
            "--endpoint.".format(url=_SUPPORT_MATRIX_URL)
        )

    # Construct dictionaries with older/newer/supported API version mapping to endpoints
    older = dict()
    newer = dict()
    supported = dict()
    for client_version in parser.sections():
        client_version_number = [int(x) for x in client_version.split(".")]
        if client_version_number > running_client_version_number:
            version_dict = newer
        elif client_version_number[0] == running_client_version_number[0]:
            version_dict = supported
        else:
            version_dict = older
        for api_version in parser.options(client_version):
            if version_dict == supported:
                version_dict[api_version] = parser.get(client_version, api_version)
            else:
                version_dict[api_version] = client_version
    return (older, newer, supported)


def _get_type_str(parameter_type, command_line=False):
    """Return a human-readable string representation of the given type.

    parameter_type -- A resolved suds.xsd.sxbasic.Element type object
    command_line -- Boolean. When set to True, the type will be
    printed in the format needed for specifying it on the command line.
    """
    children = parameter_type.children()
    if parameter_type.enum():
        enum_values = [c[0].resolve().name for c in children]
        if command_line:
            type_text = "|".join(enum_values)
        else:
            type_text = " [" + ", ".join(enum_values) + "]"
    else:
        if len(children) == 0:
            if command_line:
                if parameter_type.name == "boolean":
                    type_text = "True|False"
                else:
                    type_text = "<" + parameter_type.name + ">"
            else:
                type_text = " " + parameter_type.name
        else:
            type_text = ""
    return type_text


def get_username(config=None):
    """Return the username.

    The username is read from the configuration file. The user is asked
    for the username if the username is not available. The username is
    then stored in the configuration file.
    """

    if config is None:
        config = get_config()
    username = config.get("credentials", "username", fallback=None)
    if username is None:
        username = input("Please enter your username: ")
        config.store("credentials", "username", username)
    return username


def _list_calls(call_list, selected_keyword):
    """List available calls on stdout (grouped by keywords)

    call_list -- List of all available API calls
    selected_keyword -- Restrict output to the given keyword
    """

    assert selected_keyword in ["all"] + _KEYWORD_LIST

    call_groups = dict((keyword, []) for keyword in _KEYWORD_LIST + ["Keywordless"])
    for call in call_list:
        matched_keywords = 0
        for keyword in _KEYWORD_LIST:
            if re.search(keyword, call) is not None:
                call_groups[keyword].append(call)
                matched_keywords += 1
        if matched_keywords == 0:
            call_groups["keywordless"].append(call)

    group_delimiter = ""
    for keyword in _KEYWORD_LIST + ["Keywordless"]:
        if selected_keyword in ("all", keyword):
            calls = call_groups[keyword]
            if len(calls) > 0:
                print(group_delimiter + keyword + "\n")
                for call in sorted(calls):
                    print(_INDENTATION + call)
                group_delimiter = "\n"


def _make_soap_call(client, action_name, args, verbose, xml_output):
    """Builds a SOAP call based on the specified action and parameters

    client -- ProfitBricks client object to act on
    action_name -- the name of a API call
    args -- arguments for the API call
    verbose -- Integer, more verbose output for higher numbers.
    xml_output -- Boolean. Return XML string instead of a Python structure.

    Returns 0 on success and 1 when an error occurred.
    """
    call_parameters = vars(args)
    for arg in list(call_parameters):
        if call_parameters[arg] is None or arg not in client.client_parameter_names:
            del call_parameters[arg]

    if verbose > 0:
        if verbose == 1:
            level = logging.ERROR
        else:
            level = logging.DEBUG
        logging.basicConfig(level=level)
        print(_SCRIPT_NAME + ": Calling " + action_name + "(" +
              ", ".join([k + "=" + repr(v) for (k, v) in call_parameters.items()]) + ")",
              file=sys.stderr)
    else:
        logging.basicConfig(level=logging.CRITICAL)

    action = getattr(client, action_name)
    try:
        output = action(**call_parameters)  # pylint: disable=W0142
    except WrongCredentialsException:
        print(_SCRIPT_NAME + ": Error: Bad user name and password. Use --clear-credentials to "
              "reset them.", file=sys.stderr)
        return 1
    except suds.WebFault as exception:
        print(exception, file=sys.stderr)
        return 1

    if xml_output:
        print('<?xml version="1.0" encoding="utf-8" ?>' +
              xml.etree.ElementTree.tostring(_convert_to_xml(output)))
    else:
        print(output)
    return 0


def _pretty_object(value):
    """Return a nicely formatted, human-readable representation of a Python stucture.

    value -- a data structure to be printed to stdout

    Use this before printing data structures.
    """
    pretty_printer = pprint.PrettyPrinter(indent=4)
    return pretty_printer.pformat(value)


def _print_help(help_argument, call_argument, client):
    """Print help for a given API call on stdout.

    :param help_argument: API call name passed as argument to --help
    :param call_argument: API call name specified as call on the command line
    :param client: ProfitBricks client object
    """
    if help_argument:
        call_name = help_argument
    else:
        call_name = call_argument
    method = getattr(client, call_name)
    print(method.command_line_doc())


def main():  # pylint: disable=R0911,R0912
    """Main function for the command line client.

    The command line arguments are parsed and the corresponding actions
    are triggered. The function returns 0 on success and a positive,
    non-zero value on error.
    """

    parser = _get_parser()
    # Note: The parsed "call" can be wrongly set (could be a value for a not-yet-known argument).
    args = parser.parse_known_args()[0]

    if args.bash_completion:
        return _generate_bash_completion(parser, args)

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        return 2
    need_connection = args.help is not None or args.list or args.call
    if not (args.clear_cache or args.clear_credentials or need_connection):
        parser.error("You did not specify a call (or anything else that causes an action).")

    # Print generic help (no call specified)
    if args.help == "" and args.call is None:
        parser.print_help()
        return 0

    # Clear data
    config = get_config()
    if args.clear_cache:
        clear_cache()
    if args.clear_credentials:
        clear_credentials(config)

    if need_connection:
        if args.password_file:
            args.password = args.password_file.read().strip()
        try:
            client = get_profitbricks_client(args.username, args.password, args.api_version,
                                             args.endpoint, config, True, args.timeout)
        except URLError as error:
            print(_SCRIPT_NAME + ": Error: Could not connect to server: " + str(error.reason),
                  file=sys.stderr)
            return 1
        except (ClientTooNewException, ClientTooOldException, SupportMatrixMalformedException,
                UnknownAPIVersionException) as error:
            print(_SCRIPT_NAME + ": Error: " + str(error), file=sys.stderr)
            return 1

        _add_dynamic_arguments(parser, client)
        args = parser.parse_args()

        if args.help is not None:
            _print_help(args.help, args.call, client)
            return 0

        # List all actions
        if args.list:
            _list_calls(client.client_method_names, args.list)
            return 0

        if args.call:
            return _make_soap_call(client, args.call, args, args.verbose, args.xml)

    return 0

if __name__ == '__main__':
    sys.exit(main())
