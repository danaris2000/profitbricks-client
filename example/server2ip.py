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

from operator import attrgetter

import profitbricks_client


def main():
    client = profitbricks_client.get_profitbricks_client()
    datacenter_ids = [dc.dataCenterId for dc in client.getAllDataCenters()]
    for datacenter_id in datacenter_ids:
        datacenter = client.getDataCenter(dataCenterId=datacenter_id)
        print datacenter.dataCenterName + ':'
        for server in sorted(datacenter.servers, key=attrgetter('serverName')):
            print server.serverName + '   ' + ' '.join(server.ips)
        print


if __name__ == '__main__':
    main()
