# coding: utf-8

import argparse
import subprocess
import logging
import os
from datetime import datetime
import uuid
import json

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

ADMINTOKEN = os.environ.get('ARTICLEMETA_ADMINTOKEN', 'admin')
ARTICLEMETA_THRIFTSERVER = os.environ.get('ARTICLEMETA_THRIFTSERVER', 'admin')


def issue_pid(record):

    try:
        issn = record.get('v35', [{'_': None}])[0]['_']
        publication_year = record.get('v36', [{'_': None}])[0]['_'][0:4]
        order = "%04d" % int(record.get('v36', [{'_': None}])[0]['_'][4:])
    except TypeError:
        return None

    pid = issn+publication_year+order

    return pid


def load_isis_records(collection, issns=None):

    def prepare_record(collection, record):
        for tag in tuple(record):  # iterate over a fixed sequence of tags
            if str(tag).isdigit():
                record['v'+tag] = record[tag]
                del record[tag]  # this is why we iterate over a tuple
                # with the tags, and not directly on the record dict

        pid = record.get('v880', [{'_': None}])[0]['_'] or issue_pid(record) or record.get('v400', [{'_': None}])[0]['_']

        if not pid:
            return None

        record['v992'] = [{'_': collection}]
        record['collection'] = collection
        record['code'] = pid
        record['v880'] = [{'_': pid}]  # rewriting pid in case the v880 do not exists in record.
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

    for iso, coll in DATABASES:
        logger.info('Recording (%s) records for collection (%s)' % (coll, collection))
        isofile = '%s/../isos/%s/%s.iso' % (BASE_DIR, collection, iso)
        try:
            isis2json = Isis2Json(isofile)
        except IOError:
            raise ValueError('ISO file do not exists for the collection (%s), check the collection acronym or the path to the ISO file (%s)' % (collection, isofile))

        for record in isis2json.read():
            record = prepare_record(collection, record)
            if not record:
                continue

            if issns and not record['journal'] in issns:
                continue

            yield (coll, record)


def load_articlemeta_issues_ids(collection, issns=None):
    rc = ThriftClient(domain=ARTICLEMETA_THRIFTSERVER, admintoken=ADMINTOKEN)

    issues_pids = []
    logger.info('Loading articlemeta issues ids')
    for issn in issns or [None]:
        for issue in rc.issues(collection, issn=issn, only_identifiers=True):
            issues_pids.append('_'.join([issue.collection, issue.code, issue.processing_date.replace('-', '')]))

    return issues_pids


def load_articlemeta_documents_ids(collection, issns=None):
    rc = ThriftClient(domain=ARTICLEMETA_THRIFTSERVER, admintoken=ADMINTOKEN)

    documents_pids = []
    logger.info('Loading articlemeta documents ids')
    for issn in issns or [None]:
        for document in rc.documents(collection, issn=issn, only_identifiers=True):
            documents_pids.append('_'.join([document.collection, document.code, document.processing_date.replace('-', '')]))

    return documents_pids


def load_articlemeta_journals_ids(collection, issns=None):
    rc = ThriftClient(domain=ARTICLEMETA_THRIFTSERVER, admintoken=ADMINTOKEN)

    journals_pids = []
    logger.info('Loading articlemeta journals ids')
    for issn in issns or [None]:
        for journal in rc.journals(collection, issn=issn, only_identifiers=True):
            journals_pids.append('_'.join([journal.collection, journal.code]))

    return journals_pids


def run(collection, issns):

    rc = ThriftClient(domain=ARTICLEMETA_THRIFTSERVER, admintoken=ADMINTOKEN)

    logger.info('Running Isis2mongo')
    logger.debug('Thrift Server: %s' % ARTICLEMETA_THRIFTSERVER)
    logger.debug('Admin Token: %s' % ADMINTOKEN)
    logger.info('Loading data for collection: %s' % collection)

    articlemeta_documents = set(load_articlemeta_documents_ids(collection, issns))
    articlemeta_issues = set(load_articlemeta_issues_ids(collection, issns))
    articlemeta_journals = set(load_articlemeta_journals_ids(collection, issns))

    with DataBroker(uuid.uuid4()) as ctrl:
        for coll, record in load_isis_records(collection, issns):
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

        # Including and Updating Documents
        logger.info('Documents to be included in articlemeta (%d)' % len(new_documents))
        for item in new_documents:
            item = item.split('_')
            document_meta = ctrl.load_document(item[0], item[1])
            rc.add_document(json.dumps(document_meta))

        # Removing Documents
        if not len(to_remove_documents) > 2000:
            logger.info('Documents to be removed from articlemeta (%d)' % len(to_remove_documents))
            for item in to_remove_documents:
                item = item.split('_')
                try:
                    rc.delete_document(item[1], item[0])
                except UnauthorizedAccess:
                    logger.warning('Unauthorized access to remove itens, check the ArticleMeta admin token')
        else:
            logger.info('To many documents to be removed, the remove task will be skipped')

        # Including and Updating Journals
        logger.info('Journals to be included in articlemeta (%d)' % len(new_journals))
        for item in new_journals:
            item = item.split('_')
            journal_meta = ctrl.load_journal(item[0], item[1])
            rc.add_journal(json.dumps(journal_meta))

        # Removing Journals
        if not len(to_remove_journals) > 10:
            logger.info('Journals to be removed from articlemeta (%d)' % len(to_remove_journals))
            for index, item in enumerate(to_remove_journals):
                item = item.split('_')
                try:
                    rc.delete_journal(item[1], item[0])
                except UnauthorizedAccess:
                    logger.warning('Unauthorized access to remove itens, check the ArticleMeta admin token')
        else:
            logger.info('To many journals to be removed, the remove task will be skipped')

        # Including and Updating Issues
        logger.info('Issues to be included in articlemeta (%d)' % len(new_issues))
        for item in new_issues:
            item = item.split('_')
            issue_meta = ctrl.load_issue(item[0], item[1])
            rc.add_issue(json.dumps(issue_meta))

        # Removing Issues
        if not len(to_remove_issues) > 200:
            logger.info('Issues to be removed from articlemeta (%d)' % len(to_remove_issues))
            for item in to_remove_issues:
                item = item.split('_')
                try:
                    rc.delete_issue(item[1], item[0])
                except UnauthorizedAccess:
                    logger.warning('Unauthorized access to remove itens, check the ArticleMeta admin token')
        else:
            logger.info('To many issues to be removed, the remove task will be skipped')


def main():
    parser = argparse.ArgumentParser(
        description='Dump accesses'
    )

    parser.add_argument(
        'issns',
        nargs='*',
        help='ISSN\'s separated by spaces'
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

    run(args.collection, args.issns)
