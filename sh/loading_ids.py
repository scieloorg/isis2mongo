#!/usr/bin/python2.7
#encode: utf-8

import sys
import os
import json
import urllib2

ARTICLEMETAAPI = 'http://nefertiti.scielo.org:7000'


def articlemeta_identifiers(offset_range=1000):
    identifiers = []
    offset = 0

    with open('articlemeta_identifiers.txt', 'w') as f:
        while True:
            url = '{0}/api/v1/article/identifiers?offset={1}'.format(
                ARTICLEMETAAPI, str(offset)
            )
            print url
            request = json.loads(urllib2.urlopen(url).read())
            if len(request['objects']) == 0:
                return identifiers

            for identifier in request['objects']:
                line = identifier['collection'].strip()+identifier['code'].strip()
                f.write('{0}\n'.format(line)
                )
                identifiers.append(line)

            offset += offset_range


def legacy_identifiers():
    identifiers = []
    with open('legacy_identifiers.txt', 'r') as f:
        for identifier in f:
            identifiers.append(identifier.strip())

    return identifiers


def new_identifiers(legacy, articlemeta):
    legacy.difference_update(articlemeta)

    return legacy


def to_remove_identifiers(legacy, articlemeta):
    articlemeta.difference_update(legacy)

    return articlemeta


def write_to_file(filename, data):

    with open(filename, 'w') as f:
        for identifier in data:
            f.write('{0}\n'.format(identifier))


def main():
    legacy_ids = legacy_identifiers()
    articlemeta_ids = articlemeta_identifiers()

    difference_new = new_identifiers(
        set(legacy_ids), set(articlemeta_ids)
    )

    write_to_file('new_identifiers.txt', difference_new)

    difference_to_remove = to_remove_identifiers(
        set(articlemeta_ids), set(legacy_ids)
    )

    write_to_file('to_remove_identifiers.txt', difference_to_remove)

if __name__ == '__main__':
    main()
