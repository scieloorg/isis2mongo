#!/usr/bin/python2.7
#encode: utf-8

import sys
import os
import json
import urllib2

ARTICLEMETAAPI = 'http://nefertiti.scielo.org:7000'


def articlemeta_identifiers():
    identifiers = set()
    offset = 0

    with open('articlemeta_identifiers.txt', 'w') as f:
        while True:
            url = '{0}/api/v1/article/identifiers?offset={1}'.format(ARTICLEMETAAPI, str(offset))
            print url
            request = json.loads(urllib2.urlopen(url).read())
            if len(request['objects']) == 0:
                return identifiers

            for identifier in request['objects']:
                f.write('{0}\r\n'.format(identifier.strip()))
                identifiers.add(identifier.strip())

            offset += 1000


def legacy_identifiers():
    identifiers = set()
    with open('legacy_identifiers.txt', 'r') as f:
        for identifier in f:
            identifiers.add(identifier.strip())

    return identifiers


def new_identifiers(legacy, articlemeta):
    legacy.difference_update(articlemeta)

    return legacy


def main():
    legacy_ids = legacy_identifiers()
    am_ids = articlemeta_identifiers()

    difference = new_identifiers(legacy_ids, am_ids)

    with open('new_identifiers.txt', 'w') as f:
        for identifier in difference:
            f.write('{0}\r\n'.format(identifier))


if __name__ == '__main__':
    main()
