#!/usr/bin/python2.7
#encode: utf-8

import sys
import os
import json
import urllib2

ARTICLEMETAAPI = 'http://articlemeta.scielo.org'


def articlemeta_identifiers(offset_range=1000):
    identifiers = []
    offset = 0

    with open('articlemeta_issue_identifiers.txt', 'w') as f:
        while True:
            url = '{0}/api/v1/issue/identifiers?offset={1}'.format(
                ARTICLEMETAAPI, str(offset)
            )
            print url
            request = json.loads(urllib2.urlopen(url).read())
            if len(request['objects']) == 0:
                return identifiers

            for identifier in request['objects']:
                line = identifier['collection'].strip()+identifier['code'].strip()+identifier['processing_date'].replace('-','').strip()
                f.write('{0}\n'.format(line))
                identifiers.append(line)

            offset += offset_range


def articlemeta_identifiers_from_file(with_processing_date=False):
    identifiers = []
    with open('articlemeta_issue_identifiers.txt', 'r') as f:
        for identifier in f:
            id = identifier.strip() if with_processing_date else identifier.strip()[0:26]
            identifiers.append(id)

    return identifiers


def legacy_identifiers(with_processing_date=False):
    identifiers = []
    with open('legacy_issue_identifiers.txt', 'r') as f:
        for identifier in f:
            id = identifier.strip() if with_processing_date else identifier.strip()[0:26]
            identifiers.append(id)

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
    articlemeta_identifiers()
    legacy_ids = legacy_identifiers(with_processing_date=True)
    articlemeta_ids = articlemeta_identifiers_from_file(with_processing_date=True)

    difference_new = new_identifiers(
        set(legacy_ids), set(articlemeta_ids)
    )

    write_to_file('new_issue_identifiers.txt', difference_new)

    legacy_ids = legacy_identifiers(with_processing_date=False)
    articlemeta_ids = articlemeta_identifiers_from_file(with_processing_date=False)

    difference_to_remove = to_remove_identifiers(
        set(legacy_ids), set(articlemeta_ids)
    )

    write_to_file('to_remove_issue_identifiers.txt', difference_to_remove)

if __name__ == '__main__':
    main()
