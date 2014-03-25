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

"""Unit tests for the profitbricks_client Python module."""

from __future__ import print_function

import datetime
import io
import os
import unittest
import xml.dom.minidom

try:
    import unittest.mock as mock  # pylint: disable=E0611
except ImportError:
    import mock

import httpretty

from suds.sax.date import UtcTimezone

import profitbricks_client

ALL_DATACENTERS = u"""<?xml version='1.0' encoding='UTF-8'?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
<S:Body>
<ns2:getAllDataCentersResponse xmlns:ns2="http://ws.api.profitbricks.com/">
  <return>
    <dataCenterId>7cf8012b-b834-4e31-aa70-2c67e808e271</dataCenterId>
    <dataCenterName>profitbricks-client test datacenter</dataCenterName>
    <dataCenterVersion>7</dataCenterVersion>
  </return>
</ns2:getAllDataCentersResponse>
</S:Body>
</S:Envelope>"""

CREATED_DATACENTER = u"""<?xml version='1.0' encoding='UTF-8'?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
<S:Body>
<ns2:CreateDataCenterResponse xmlns:ns2="http://ws.api.profitbricks.com/">
  <return>
    <requestId>2360771</requestId>
    <dataCenterId>4649b926-5989-4911-8d43-6114e2ae1f49</dataCenterId>
    <dataCenterVersion>1</dataCenterVersion>
    <region>EUROPE</region>
  </return>
</ns2:CreateDataCenterResponse>
</S:Body>
</S:Envelope>"""

CREATED_SERVER = u"""<?xml version='1.0' encoding='UTF-8'?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
<S:Body>
<ns2:CreateServerResponse xmlns:ns2="http://ws.api.profitbricks.com/">
  <return>
    <requestId>2360771</requestId>
    <dataCenterId>7724e95d-c446-4d7f-bede-3d2b0f1d56af</dataCenterId>
    <dataCenterVersion>1</dataCenterVersion>
    <serverId>35c34b7e-e212-46af-91a6-4dd50bafbe5c</serverId>
  </return>
</ns2:CreateServerResponse>
</S:Body>
</S:Envelope>"""


DATACENTER = u"""<?xml version='1.0' encoding='UTF-8'?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
<S:Body>
<ns2:getDataCenterResponse xmlns:ns2="http://ws.api.profitbricks.com/">
  <return>
    <requestId>2524736</requestId>
    <dataCenterId>7cf8012b-b834-4e31-aa70-2c67e808e271</dataCenterId>
    <dataCenterVersion>7</dataCenterVersion>
    <dataCenterName>profitbricks-client test datacenter</dataCenterName>
    <servers>
      <dataCenterId>7cf8012b-b834-4e31-aa70-2c67e808e271</dataCenterId>
      <dataCenterVersion>7</dataCenterVersion>
      <serverId>a6376253-0c1b-4949-9722-b471e696b616</serverId>
      <serverName>Server 42</serverName>
      <cores>1</cores>
      <ram>256</ram>
      <internetAccess>true</internetAccess>
      <ips>192.0.2.7</ips>
      <nics>
        <dataCenterId>7cf8012b-b834-4e31-aa70-2c67e808e271</dataCenterId>
        <dataCenterVersion>7</dataCenterVersion>
        <nicId>17949987-30c1-4f43-b6ae-e006d27c99bc</nicId>
        <lanId>2</lanId>
        <internetAccess>true</internetAccess>
        <serverId>a6376253-0c1b-4949-9722-b471e696b616</serverId>
        <ips>192.0.2.7</ips>
        <macAddress>00:16:3e:1f:fd:0f</macAddress>
        <firewall>
          <active>false</active>
          <firewallId>341bff23-baec-4bcf-a766-547ca7e5a975</firewallId>
          <nicId>17949987-30c1-4f43-b6ae-e006d27c99bc</nicId>
          <provisioningState>AVAILABLE</provisioningState>
        </firewall>
        <dhcpActive>true</dhcpActive>
        <gatewayIp>192.0.2.1</gatewayIp>
        <provisioningState>AVAILABLE</provisioningState>
      </nics>
      <provisioningState>AVAILABLE</provisioningState>
      <virtualMachineState>RUNNING</virtualMachineState>
      <creationTime>2014-03-12T09:36:58.554Z</creationTime>
      <lastModificationTime>2014-03-12T15:34:22.661Z</lastModificationTime>
      <osType>UNKNOWN</osType>
      <availabilityZone>AUTO</availabilityZone>
      </servers>
    <provisioningState>AVAILABLE</provisioningState>
    <region>EUROPE</region>
  </return>
</ns2:getDataCenterResponse>
</S:Body>
</S:Envelope>
"""

SUPPORT_MATRIX = u"""
[2.0]
1.2=https://api.profitbricks.com/1.2/wsdl
1.3=https://api.profitbricks.com/1.3/wsdl

[2.1]
1.4=https://api.profitbricks.com/1.4/wsdl

[3.0]
1.5=https://api.profitbricks.com/1.5/wsdl
1.6=https://api.profitbricks.com/1.6/wsdl
"""


def soap_request(body):
    """Return a full SOAP request XML document with the given body."""
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<SOAP-ENV:Envelope xmlns:ns0="http://ws.api.profitbricks.com/"'
            ' xmlns:ns1="http://schemas.xmlsoap.org/soap/envelope/"'
            ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
            ' xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">'
            '<SOAP-ENV:Header/>'
            '<ns1:Body>{body}</ns1:Body>'
            '</SOAP-ENV:Envelope>'.format(body=body))


# pylint: disable=W0212
class CallTests(unittest.TestCase):  # pylint: disable=R0904
    """The calling functions from the API."""

    maxDiff = None

    @httpretty.activate
    def setUp(self):  # pylint: disable=C0103
        wsdl_filename = os.path.join(os.path.abspath(os.path.dirname(__name__)),
                                     "api-1.2-wsdl.xml")
        endpoint = "https://api.test.profitbricks.test.com/1.2/wsdl"
        httpretty.register_uri(httpretty.GET, endpoint, body=open(wsdl_filename).read())
        self.client = profitbricks_client.get_profitbricks_client(
            "profitbricks-client test user",
            "very secret password",
            endpoint=endpoint,
            store_endpoint=False
        )
        self.factory = self.client._soap_client.factory

    def assert_sudsobject_equal(self, first, second):
        """Fail if the two objects are unequal as determined by their string representation."""
        self.assertMultiLineEqual(str(first), str(second))

    def assert_xml_equal(self, first, second):
        """Prettify XML strings before comparing them to make the exception easier to read."""
        try:
            pretty_first = xml.dom.minidom.parseString(first).toprettyxml()
            pretty_second = xml.dom.minidom.parseString(second).toprettyxml()
            first = pretty_first
            second = pretty_second
        except xml.parsers.expat.ExpatError:
            pass
        self.assertEqual(first, second)

    @httpretty.activate
    def test_create_datacenter_1arg(self):
        """Test calling client.createDataCenter(dataCenterName='Test')"""
        httpretty.register_uri(httpretty.POST, 'https://api.profitbricks.com/1.2',
                               body=CREATED_DATACENTER)
        created_datacenter = self.client.createDataCenter(dataCenterName='Test')
        request = httpretty.last_request()
        expected_request = ('<ns0:createDataCenter><dataCenterName>Test</dataCenterName>'
                            '</ns0:createDataCenter>')
        self.assert_xml_equal(soap_request(expected_request), request.body)

        expected_datacenter = self.factory.create('createDcResponse')
        expected_datacenter.requestId = '2360771'
        expected_datacenter.dataCenterId = '4649b926-5989-4911-8d43-6114e2ae1f49'
        expected_datacenter.dataCenterVersion = 1
        expected_datacenter.region = 'EUROPE'
        self.assert_sudsobject_equal(expected_datacenter, created_datacenter)

    @httpretty.activate
    def test_create_server(self):
        """Test calling client.createServer(cores=1, ram=256)"""
        httpretty.register_uri(httpretty.POST, 'https://api.profitbricks.com/1.2',
                               body=CREATED_SERVER)
        created_server = self.client.createServer(cores=1, ram=256)
        request = httpretty.last_request()
        expected_request = ('<ns0:createServer><request><cores>1</cores><ram>256</ram>'
                            '</request></ns0:createServer>')
        self.assert_xml_equal(soap_request(expected_request), request.body)

        expected_response = self.factory.create('createServerResponse')
        expected_response.requestId = "2360771"
        expected_response.dataCenterId = "7724e95d-c446-4d7f-bede-3d2b0f1d56af"
        expected_response.dataCenterVersion = 1
        expected_response.serverId = "35c34b7e-e212-46af-91a6-4dd50bafbe5c"
        self.assert_sudsobject_equal(expected_response, created_server)

    @httpretty.activate
    def test_create_datacenter_2args(self):
        """Test calling client.createDataCenter(dataCenterName='Test', region='EUROPE')"""
        httpretty.register_uri(httpretty.POST, 'https://api.profitbricks.com/1.2',
                               body=CREATED_DATACENTER)
        created_datacenter = self.client.createDataCenter(dataCenterName='Test', region='EUROPE')
        request = httpretty.last_request()
        expected_request = ('<ns0:createDataCenter><dataCenterName>Test</dataCenterName>'
                            '<region>EUROPE</region></ns0:createDataCenter>')
        self.assert_xml_equal(soap_request(expected_request), request.body)

        expected_datacenter = self.factory.create('createDcResponse')
        expected_datacenter.requestId = '2360771'
        expected_datacenter.dataCenterId = '4649b926-5989-4911-8d43-6114e2ae1f49'
        expected_datacenter.dataCenterVersion = 1
        expected_datacenter.region = 'EUROPE'
        self.assert_sudsobject_equal(expected_datacenter, created_datacenter)

    @httpretty.activate
    def test_get_all_datacenters(self):
        """Test calling client.getAllDataCenters()"""
        httpretty.register_uri(httpretty.POST, "https://api.profitbricks.com/1.2",
                               body=ALL_DATACENTERS)
        datacenters = self.client.getAllDataCenters()
        request = httpretty.last_request()
        self.assert_xml_equal(soap_request("<ns0:getAllDataCenters/>"), request.body)

        expected_datacenter = self.factory.create('dataCenterIdentifier')
        expected_datacenter.dataCenterId = "7cf8012b-b834-4e31-aa70-2c67e808e271"
        expected_datacenter.dataCenterName = "profitbricks-client test datacenter"
        expected_datacenter.dataCenterVersion = 7
        self.assert_sudsobject_equal([expected_datacenter], datacenters)

    @httpretty.activate
    def test_get_datacenter(self):  # pylint: disable=R0915
        """Test calling client.getDataCenter(dataCenterId=<id>)"""
        httpretty.register_uri(httpretty.POST, "https://api.profitbricks.com/1.2",
                               body=DATACENTER)
        datacenter_id = "7cf8012b-b834-4e31-aa70-2c67e808e271"
        datacenter = self.client.getDataCenter(dataCenterId=datacenter_id)
        request = httpretty.last_request()
        expected_body = ("<ns0:getDataCenter><dataCenterId>" + datacenter_id +
                         "</dataCenterId></ns0:getDataCenter>")
        self.assert_xml_equal(soap_request(expected_body), request.body)

        expected_datacenter = self.factory.create('dataCenter')
        expected_datacenter.requestId = "2524736"
        expected_datacenter.dataCenterId = datacenter_id
        expected_datacenter.dataCenterVersion = 7
        expected_datacenter.dataCenterName = "profitbricks-client test datacenter"
        server1 = self.factory.create('server')
        expected_datacenter.servers = [server1]
        del expected_datacenter.storages
        del expected_datacenter.loadBalancers
        expected_datacenter.provisioningState = "AVAILABLE"
        expected_datacenter.region = "EUROPE"

        del server1.requestId
        server1.dataCenterId = datacenter_id
        server1.dataCenterVersion = 7
        server1.serverId = "a6376253-0c1b-4949-9722-b471e696b616"
        server1.serverName = "Server 42"
        server1.cores = 1
        server1.ram = 256
        server1.internetAccess = True
        server1.ips = ["192.0.2.7"]
        del server1.connectedStorages
        del server1.romDrives
        nic1 = self.factory.create('nic')
        server1.nics = [nic1]
        server1.provisioningState = "AVAILABLE"
        server1.virtualMachineState = "RUNNING"
        server1.creationTime = datetime.datetime(2014, 3, 12, 9, 36, 58, 554000, UtcTimezone())
        server1.lastModificationTime = datetime.datetime(2014, 3, 12, 15, 34, 22, 661000,
                                                         UtcTimezone())
        server1.osType = "UNKNOWN"
        server1.availabilityZone = "AUTO"

        del nic1.requestId
        nic1.dataCenterId = datacenter_id
        nic1.dataCenterVersion = 7
        nic1.nicId = "17949987-30c1-4f43-b6ae-e006d27c99bc"
        del nic1.nicName
        nic1.lanId = 2
        nic1.internetAccess = True
        nic1.serverId = "a6376253-0c1b-4949-9722-b471e696b616"
        nic1.ips = ["192.0.2.7"]
        nic1.macAddress = "00:16:3e:1f:fd:0f"
        nic1.firewall = self.factory.create('firewall')
        nic1.firewall.active = False
        nic1.firewall.firewallId = "341bff23-baec-4bcf-a766-547ca7e5a975"
        nic1.firewall.nicId = nic1.nicId
        del nic1.firewall.firewallRules
        nic1.firewall.provisioningState = "AVAILABLE"
        nic1.dhcpActive = True
        nic1.gatewayIp = "192.0.2.1"
        nic1.provisioningState = "AVAILABLE"

        self.assert_sudsobject_equal(expected_datacenter, datacenter)


class SupportMatrixTests(unittest.TestCase):  # pylint: disable=R0904
    """Test parsing and processing the client_matrix.ini file."""

    def __init__(self, *args, **kwargs):
        super(SupportMatrixTests, self).__init__(*args, **kwargs)
        if not hasattr(self, "assertRaisesRegex"):
            self.assertRaisesRegex = self.assertRaisesRegexp  # pylint: disable=C0103

    @mock.patch('profitbricks_client.urlopen')
    def test_client_too_old(self, urlopen_mock):
        """Test getting the latest API endpoint for profitbricks-client 1.0"""
        urlopen_mock.return_value = io.StringIO(SUPPORT_MATRIX)
        msg = ("profitbricks-client 1.0 is too old and not supported any more. "
               "Please upgrade to a newer version.")
        self.assertRaisesRegex(profitbricks_client.ClientTooOldException, msg,
                               profitbricks_client._endpoint_from_support_matrix, "1.0", "latest")

    @mock.patch('profitbricks_client.urlopen')
    def test_latest_2_0(self, urlopen_mock):
        """Test getting the latest API endpoint for profitbricks-client 2.0"""
        urlopen_mock.return_value = io.StringIO(SUPPORT_MATRIX)
        endpoint = profitbricks_client._endpoint_from_support_matrix("2.0", "latest")
        self.assertEqual("https://api.profitbricks.com/1.3/wsdl", endpoint)

    @mock.patch('profitbricks_client.urlopen')
    def test_latest_2_1(self, urlopen_mock):
        """Test getting the latest API endpoint for profitbricks-client 2.1.3"""
        urlopen_mock.return_value = io.StringIO(SUPPORT_MATRIX)
        endpoint = profitbricks_client._endpoint_from_support_matrix("2.1.3", "latest")
        self.assertEqual("https://api.profitbricks.com/1.4/wsdl", endpoint)

    @mock.patch('profitbricks_client.urlopen')
    def test_latest_2_5(self, urlopen_mock):
        """Test getting the latest API endpoint for profitbricks-client 2.5"""
        urlopen_mock.return_value = io.StringIO(SUPPORT_MATRIX)
        endpoint = profitbricks_client._endpoint_from_support_matrix("2.5", "latest")
        self.assertEqual("https://api.profitbricks.com/1.4/wsdl", endpoint)

    @mock.patch('profitbricks_client.urlopen')
    def test_client_too_new(self, urlopen_mock):
        """Test getting the latest API endpoint for profitbricks-client 4.1"""
        urlopen_mock.return_value = io.StringIO(SUPPORT_MATRIX)
        msg = "profitbricks-client 4.1 is too new and not tested against the API."
        self.assertRaisesRegex(profitbricks_client.ClientTooNewException, msg,
                               profitbricks_client._endpoint_from_support_matrix, "4.1", "latest")

    @mock.patch('profitbricks_client.urlopen')
    def test_api_version_2_0(self, urlopen_mock):
        """Test getting the endpoint for a specific API version for profitbricks-client 2.0"""
        urlopen_mock.return_value = io.StringIO(SUPPORT_MATRIX)
        endpoint = profitbricks_client._endpoint_from_support_matrix("2.0", "1.2")
        self.assertEqual("https://api.profitbricks.com/1.2/wsdl", endpoint)

    @mock.patch('profitbricks_client.urlopen')
    def test_api_version_2_3(self, urlopen_mock):
        """Test getting the endpoint for a specific API version for profitbricks-client 2.3"""
        urlopen_mock.return_value = io.StringIO(SUPPORT_MATRIX)
        endpoint = profitbricks_client._endpoint_from_support_matrix("2.3", "1.3")
        self.assertEqual("https://api.profitbricks.com/1.3/wsdl", endpoint)

    @mock.patch('profitbricks_client.urlopen')
    def test_unknown_api_version(self, urlopen_mock):
        """Test getting the endpoint for unknown API version"""
        urlopen_mock.return_value = io.StringIO(SUPPORT_MATRIX)
        msg = ("The specified API version 1.1 is not known. Supported API versions "
               "by profitbricks-client 2.0: 1.2, 1.3")
        self.assertRaisesRegex(profitbricks_client.UnknownAPIVersionException, msg,
                               profitbricks_client._endpoint_from_support_matrix, "2.0", "1.1")

    @mock.patch('profitbricks_client.urlopen')
    def test_too_old_for_api_version(self, urlopen_mock):
        """Test getting the endpoint for a client that is too new for the given API version"""
        urlopen_mock.return_value = io.StringIO(SUPPORT_MATRIX)
        msg = ("profitbricks-client 2.0 is too old for API version 1.4. Please upgrade "
               "the client to version 2.1 or later.")
        self.assertRaisesRegex(profitbricks_client.ClientTooOldException, msg,
                               profitbricks_client._endpoint_from_support_matrix, "2.0", "1.4")

    @mock.patch('profitbricks_client.urlopen')
    def test_too_new_for_api_version(self, urlopen_mock):
        """Test getting the endpoint for a client that is too new for the given API version"""
        urlopen_mock.return_value = io.StringIO(SUPPORT_MATRIX)
        msg = ("profitbricks-client 3.1 is too new for API version 1.3. "
               "Please downgrade the client to version 2.0 or any later 2.x version.")
        self.assertRaisesRegex(profitbricks_client.ClientTooNewException, msg,
                               profitbricks_client._endpoint_from_support_matrix, "3.1", "1.3")

if __name__ == '__main__':
    unittest.main()
