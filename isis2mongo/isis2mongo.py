# coding: utf-8

import argparse
import subprocess
import logging
import os
from datetime import datetime
import uuid

from articlemeta.client import ThriftClient
from articlemeta.client import UnauthorizedAccess

from controller import DataBroker, Isis2Json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger(__name__)

DATABASES = (
    ('title', 'journals'),
    ('issue', 'issues'),
    ('artigo', 'articles'),
    ('bib4cit', 'references'),
)


def issue_pid(record):

    issn = record.get('v35', [{'_': None}])[0]['_']
    publication_year = record.get('v36', [{'_': None}])[0]['_'][0:4]
    order = "%04d" % int(record.get('v36', [{'_': None}])[0]['_'][4:])

    pid = issn+publication_year+order

    return pid


def load_isis_records(collections):

    def prepare_record(record):
        for tag in tuple(record):  # iterate over a fixed sequence of tags
            if str(tag).isdigit():
                record['v'+tag] = record[tag]
                del record[tag]  # this is why we iterate over a tuple
                # with the tags, and not directly on the record dict

        pid = record.get('v880', [{'_': None}])[0]['_'] or record.get('v400', [{'_': None}])[0]['_'] or issue_pid(record)

        if not pid:
            return None

        record['v992'] = [{'_': collection}]
        record['collection'] = collection
        record['code'] = pid
        record['processing_date'] = datetime.strptime(record.get('v91', [{'_': datetime.now().isoformat()[:10]}])[0]['_'].replace('-', ''), '%Y%m%d').isoformat()[:10]

        if len(pid) == 9:
            record['journal'] = pid

        if len(pid) == 17:
            record['journal'] = pid[:9]
            record['issue'] = pid

        if len(pid) == 23:
            record['journal'] = pid[1:10]
            record['issue'] = pid[1:18]
            record['document'] = pid

        if len(pid) == 28:
            record['journal'] = pid[1:10]
            record['issue'] = pid[1:18]
            record['document'] = pid[:23]

        return record

    for collection in collections:
        for iso, coll in DATABASES:
            logger.info('Recording (%s) records for collection (%s)' % (coll, collection))
            isis2json = Isis2Json('%s/../isos/%s/%s.iso' % (BASE_DIR, collection, iso))
            for record in isis2json.read():
                record = prepare_record(record)
                if not record:
                    continue

                yield (coll, record)


def load_articlemeta_issues_ids(collections):
    rc = ThriftClient()

    issues_pids = []
    logger.info('Loading articlemeta issues ids')
    for collection in collections:
        for issue in rc.issues(collection, only_identifiers=True):
            issues_pids.append('_'.join([issue.collection, issue.code, issue.processing_date.replace('-', '')]))

    return issues_pids


def load_articlemeta_documents_ids(collections):
    rc = ThriftClient()

    documents_pids = []
    logger.info('Loading articlemeta documents ids')
    for collection in collections:
        for document in rc.documents(collection, only_identifiers=True):
            documents_pids.append('_'.join([document.collection, document.code, document.processing_date.replace('-', '')]))

    return documents_pids


def load_articlemeta_journals_ids(collections):
    rc = ThriftClient()

    journals_pids = []
    logger.info('Loading articlemeta journals ids')
    for collection in collections:
        for journal in rc.journals(collection, only_identifiers=True):
            journals_pids.append('_'.join([journal.collection, journal.code]))

    return journals_pids


def run(collections):
    admintoken = os.environ.get('ARTICLEMETA_ADMINTOKEN', 'admin')

    rc = ThriftClient(admintoken=admintoken)

    logger.info('Running Isis2mongo')
    logger.debug('Admin Token: %s' % admintoken)

    if not isinstance(collections, list):
        collections = [collections]

    articlemeta_documents = set(load_articlemeta_documents_ids(collections))
    articlemeta_issues = set(load_articlemeta_issues_ids(collections))
    articlemeta_journals = set(load_articlemeta_journals_ids(collections))

    with DataBroker(uuid.uuid4()) as ctrl:
        for coll, record in load_isis_records(collections):
            ctrl.write_record(coll, record)

        legacy_documents = set(ctrl.articles_ids)
        legacy_issues = set(ctrl.issues_ids)
        legacy_journals = set(ctrl.journals_ids)

        new_documents = list(legacy_documents - articlemeta_documents)
        new_issues = list(legacy_issues - articlemeta_issues)
        new_journals = list(legacy_journals - articlemeta_journals)

        to_remove_documents = list(articlemeta_documents - legacy_documents)
        to_remove_issues = list(articlemeta_issues - legacy_issues)
        to_remove_journals = list(articlemeta_journals - legacy_journals)

        logger.info('Documents to be included in articlemeta (%d)' % len(new_documents))

        logger.info('Documents to be removed from articlemeta (%d)' % len(to_remove_documents))
        for item in to_remove_documents:
            item = item.split('_')
            try:
                rc.delete_document(item[1], item[0])
            except UnauthorizedAccess:
                logger.warning('Unauthorized access to remove itens, check the ArticleMeta admin token')

        logger.info('Journals to be included in articlemeta (%d)' % len(new_journals))
        logger.info('Journals to be removed from articlemeta (%d)' % len(to_remove_journals))
        for item in to_remove_journals:
            item = item.split('_')
            try:
                rc.delete_journal(item[1], item[0])
            except UnauthorizedAccess:
                logger.warning('Unauthorized access to remove itens, check the ArticleMeta admin token')

        logger.info('Issues to be included in articlemeta (%d)' % len(new_issues))
        logger.info('Issues to be removed from articlemeta (%d)' % len(to_remove_issues))
        for item in to_remove_issues:
            item = item.split('_')
            try:
                rc.delete_issue(item[1], item[0])
            except UnauthorizedAccess:
                logger.warning('Unauthorized access to remove itens, check the ArticleMeta admin token')



def main():
    parser = argparse.ArgumentParser(
        description='Dump accesses'
    )

    parser.add_argument(
        '--collection',
        '-c',
        help='Collection Acronym'
    )

    parser.add_argument(
        '--output_file',
        '-r',
        help='File to receive the dumped data'
    )

    parser.add_argument(
        '--logging_file',
        '-o',
        help='Full path to the log file'
    )

    parser.add_argument(
        '--logging_level',
        '-l',
        default='DEBUG',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logggin level'
    )

    args = parser.parse_args()
    logger.setLevel(args.logging_level)
    logging.basicConfig()

    run(args.collection)
