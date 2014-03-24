#!/usr/bin/python

# Copyright (C) 2014, ProfitBricks GmbH
# Authors: Benjamin Drung <benjamin.drung@profitbricks.com>
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

"""Install profitbricks-client with setuptools."""

import os
import re
from setuptools import setup


def get_version(versionfile):
    """Extract the __version__ from a given Python module."""
    match = re.search(r'^__version__ = [\'"]([^\'"]*)[\'"]', open(versionfile).read(), re.M)
    if match:
        return match.group(1)
    else:
        raise RuntimeError("Unable to find version string in {file}.".format(file=versionfile))

setup(
    name='profitbricks-client',
    version=get_version(os.path.join(os.path.dirname(__file__), 'profitbricks_client.py')),
    description='ProfitBricks Client',
    long_description=open(os.path.join(os.path.dirname(__file__), 'README.md')).read(),
    keywords='profitbricks IaaS cloud',
    author='Benjamin Drung',
    author_email='benjamin.drung@profitbricks.com',
    url='https://github.com/profitbricks/profitbricks-client',
    data_files=[('/etc/bash_completion.d/', ['bash_completion.d/profitbricks-client'])],
    py_modules=['profitbricks_client'],
    scripts=['profitbricks-client'],
    install_requires=['appdirs', 'suds'],
    license='ISC',
    test_suite="test_profitbricks_client",
    tests_require=['httpretty', 'mock'],
)
