#!/usr/bin/python
# coding: utf-8

import sys
import os
import json
from articlemeta.client import ThriftClient
import logging

logger = logging.getLogger(__name__)


def articlemeta_identifiers(offset_range=1000):
    identifiers = []
    offset = 0

    cl = ThriftClient(
        domain=os.environ.get('ARTICLEMETA_THRIFTSERVER', None),
        admintoken=os.environ.get('ARTICLEMETA_ADMINTOKEN', None)
    )

    with open('articlemeta_article_identifiers.txt', 'w') as f:
        for document in cl.documents(only_identifiers=True):
            line = document.collection.strip()+document.code.strip()+document.processing_date.replace('-','').strip()
            f.write('{0}\n'.format(line))
            identifiers.append(line)


def articlemeta_identifiers_from_file(with_processing_date=False):
    identifiers = []
    with open('articlemeta_article_identifiers.txt', 'r') as f:
        for identifier in f:
            id = identifier.strip() if with_processing_date else identifier.strip()[0:26]
            identifiers.append(id)

    return identifiers


def legacy_identifiers(with_processing_date=False):
    identifiers = []
    with open('legacy_article_identifiers.txt', 'r') as f:
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

    write_to_file('new_article_identifiers.txt', difference_new)

    legacy_ids = legacy_identifiers(with_processing_date=False)
    articlemeta_ids = articlemeta_identifiers_from_file(with_processing_date=False)

    difference_to_remove = to_remove_identifiers(
        set(legacy_ids), set(articlemeta_ids)
    )

    write_to_file('to_remove_article_identifiers.txt', difference_to_remove)

if __name__ == '__main__':
    main()
