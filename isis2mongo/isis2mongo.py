# coding: utf-8

import argparse
import subprocess
import logging
import logging.config
import os
from datetime import datetime
import uuid
import json
import re

from articlemeta.client import ThriftClient
from articlemeta.client import UnauthorizedAccess
from articlemeta.client import ServerError

from controller import DataBroker, IsisDataBroker

logger = logging.getLogger(__name__)

# Do not change this order
DATABASES = (
    ('title', 'journals'),
    ('issue', 'issues'),
    ('artigo', 'articles'),
    ('bib4cit', 'references'),
)
BULK_SIZE = 100000
SECURE_ARTICLE_DELETIONS_NUMBER = 2000
SECURE_ISSUE_DELETIONS_NUMBER = 20
SECURE_JOURNAL_DELETIONS_NUMBER = 5
ADMINTOKEN = os.environ.get('ARTICLEMETA_ADMINTOKEN', 'admin')
ARTICLEMETA_THRIFTSERVER = os.environ.get('ARTICLEMETA_THRIFTSERVER', 'admin')
ISO_PATH = os.environ.get('ISO_PATH', os.path.dirname(os.path.abspath(__file__)))
SENTRY_HANDLER = os.environ.get('SENTRY_HANDLER', None)
LOGGING_LEVEL = os.environ.get('LOGGING_LEVEL', None)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,

    'formatters': {
        'console': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%H:%M:%S',
            },
        },
    'handlers': {
        'console': {
            'level': LOGGING_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'console'
            }
        },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': LOGGING_LEVEL,
            'propagate': False,
            },
        'isis2mongo.isis2mongo': {
            'level': LOGGING_LEVEL,
            'propagate': True,
        },
    }
}

if SENTRY_HANDLER:
    LOGGING['handlers']['sentry'] = {
        'level': 'ERROR',
        'class': 'raven.handlers.logging.SentryHandler',
        'dsn': SENTRY_HANDLER,
    }
    LOGGING['loggers']['']['handlers'].append('sentry')


REGEX_FIXISSUEID = re.compile(r'^[0-9]*')


def issue_pid(record):
    """
    This method returns the ISSUE PID according to values registered in
    v35 and v36.
    input: v35: 0032-281X v36: 20023
    output: 0032-281X20020003

    input: v35: 0032-281X v36: 200221
    output: 0032-281X20020021

    input: v35: 0032-281X v36: 20021-4
    output: 0032-281X20020001

    input: v35: 0032-281X v36: 2002
    output: 0032-281X20020000
    """

    try:
        issn = record.get('v35', [{'_': None}])[0]['_']
        publication_year = record.get('v36', [{'_': None}])[0]['_'][0:4]
        issue_order = REGEX_FIXISSUEID.match(record.get('v36', [{'_': None}])[0]['_'][4:]).group() or 0
        order = "%04d" % int(issue_order)
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
        processing_date = record.get('v91', record.get('v941', [{'_': datetime.now().isoformat()[:10]}]))[0]['_'].replace('-', '') or datetime.now().isoformat()[:10].replace('-', '')
        record['processing_date'] = datetime.strptime(processing_date, '%Y%m%d').isoformat()[:10]

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
        rec_coll = coll
        logger.info('Recording (%s) records for collection (%s)', coll, collection)
        isofile = '%s/../isos/%s/%s.iso' % (ISO_PATH, collection, iso)

        try:
            isis_db = IsisDataBroker(isofile)
        except IOError:
            if iso in ['bib4cit', 'issue']:
                logger.warning('No %s found, it will continue without this file. The references or issues must be in article database otherwise no references or issues will be recorded', iso)
                continue
            raise ValueError('ISO file do not exists for the collection (%s), check the collection acronym or the path to the ISO file (%s)' % (collection, isofile))

        temp_processing_date = [{'_': datetime.now().strftime("%Y%m%d")}]

        for ndx, record in enumerate(isis_db.read(), 1):
            logger.debug('Reading record (%d) from iso (%s)', ndx, isofile)

            """
            Some records from the database artigo comes with invalid metadata
            This "if" is ignoring records withour the field 706 in the article
            database.
            ex:
            mfn= 15968
            936  "^i0044-5967^y2010^o2"
            9999  "../bases-work/aa/aa"
            880  "S"
            ..
            mfn= 15969
            936  "^i0044-5967^y2010^o2"
            9999  "../bases-work/aa/aa"
            880  "S"
            ...
            """
            if coll == 'articles':

                field_706 = record.get('706', [{'_': None}])[0]['_']

                if field_706 is None:
                    continue

                if field_706 == 'o':
                    temp_processing_date = record.get('91', temp_processing_date)
                    continue

                if field_706 not in ['h', 'c', 'i']:
                    continue

                if field_706 == 'i':
                    record['91'] = record.get('91', temp_processing_date)
                    rec_coll = 'issues'

                if field_706 == 'h':
                    record['91'] = record.get('91', temp_processing_date)
                    rec_coll = 'articles'

                if field_706 == 'c':
                    rec_coll = 'references'

            try:
                record = prepare_record(collection, record)
            except:
                logger.error('Fail to load document. Integrity error.')
                continue

            if not record:
                continue

            if issns and not record['journal'] in issns:
                continue

            yield (rec_coll, record)


def load_articlemeta_issues_ids(collection, issns=None):
    rc = ThriftClient(domain=ARTICLEMETA_THRIFTSERVER, admintoken=ADMINTOKEN)

    issues_pids = []
    logger.info('Loading articlemeta issues ids')
    for issn in issns or [None]:
        for issue in rc.issues(collection, issn=issn, only_identifiers=True):
            logger.debug(
                'Loading articlemeta issue id (%s)',
                '_'.join([issue.collection, issue.code, issue.processing_date.replace('-', '')])
            )
            issues_pids.append('_'.join([issue.collection, issue.code, issue.processing_date.replace('-', '')]))

    return issues_pids


def load_articlemeta_documents_ids(collection, issns=None):
    rc = ThriftClient(domain=ARTICLEMETA_THRIFTSERVER, admintoken=ADMINTOKEN)

    documents_pids = []
    logger.info('Loading articlemeta documents ids')
    for issn in issns or [None]:
        for document in rc.documents(collection, issn=issn, only_identifiers=True):
            logger.debug(
                'Loading articlemeta document id (%s)',
                '_'.join([document.collection, document.code, document.processing_date.replace('-', '')])
            )
            documents_pids.append('_'.join([document.collection, document.code, document.processing_date.replace('-', '')]))

    return documents_pids


def load_articlemeta_journals_ids(collection, issns=None):
    rc = ThriftClient(domain=ARTICLEMETA_THRIFTSERVER, admintoken=ADMINTOKEN)

    journals_pids = []
    logger.info('Loading articlemeta journals ids')
    for issn in issns or [None]:
        for journal in rc.journals(collection, issn=issn, only_identifiers=True):
            logger.debug(
                'Loading articlemeta journal id (%s)',
                '_'.join([journal.collection, journal.code])
            )
            journals_pids.append('_'.join([journal.collection, journal.code, journal.processing_date.replace('-', '')]))

    return journals_pids


def run(collection, issns, full_rebuild=False, force_delete=False, bulk_size=BULK_SIZE):

    rc = ThriftClient(domain=ARTICLEMETA_THRIFTSERVER, admintoken=ADMINTOKEN)

    logger.info('Running Isis2mongo')
    logger.debug('Thrift Server: %s', ARTICLEMETA_THRIFTSERVER)
    logger.debug('Admin Token: %s', ADMINTOKEN)
    logger.info('Loading ArticleMeta identifiers for collection: %s', collection)

    if full_rebuild is True:
        articlemeta_documents = set([])
        articlemeta_issues = set([])
        articlemeta_journals = set([])

    else:
        articlemeta_documents = set(
            load_articlemeta_documents_ids(collection, issns))
        articlemeta_issues = set(
            load_articlemeta_issues_ids(collection, issns))
        articlemeta_journals = set(
            load_articlemeta_journals_ids(collection, issns))

    with DataBroker(uuid.uuid4()) as ctrl:
        update_issue_id = ''

        fields_to_update_after_loading_documents = []
        bulk = {}

        bulk_count = 0
        for coll, record in load_isis_records(collection, issns):
            bulk_count += 1
            bulk.setdefault(coll, [])
            bulk[coll].append(record)
            if bulk_count == bulk_size:
                bulk_count = 0
                ctrl.bulk_data(dict(bulk))
                bulk = {}

            # ctrl.write_record(coll, record)
            # Write field 4 in issue database
            rec_type = record.get('v706', [{'_': ''}])[0]['_']
            if rec_type == 'h':
                if update_issue_id == record['v880'][0]['_'][1:18]:
                    continue
                fields_to_update_after_loading_documents.append([
                    'issues',
                    record['v880'][0]['_'][1:18],
                    'v4',
                    record['v4'][0]['_']
                ])
        # bulk residual data
        ctrl.bulk_data(dict(bulk))

        logger.info('Updating fields metadata')
        ctrl.bulk_update_field('issues', fields_to_update_after_loading_documents)
        logger.info('Loading legacy identifiers')
        legacy_documents = set(ctrl.articles_ids)
        legacy_issues = set(ctrl.issues_ids)
        legacy_journals = set(ctrl.journals_ids)

        logger.info('Producing lists of differences between ArticleMeta and Legacy databases')
        new_documents = list(legacy_documents - articlemeta_documents)
        new_issues = list(legacy_issues - articlemeta_issues)
        new_journals = list(legacy_journals - articlemeta_journals)

        am_document_pids_only = set([i[0:27] for i in articlemeta_documents])
        lg_document_pids_only = set([i[0:27] for i in legacy_documents])
        to_remove_documents = list(am_document_pids_only - lg_document_pids_only)

        am_issue_pids_only = set([i[0:21] for i in articlemeta_issues])
        lg_issue_pids_only = set([i[0:21] for i in legacy_issues])
        to_remove_issues = list(am_issue_pids_only - lg_issue_pids_only)

        am_journals_pids_only = set([i[0:13] for i in articlemeta_journals])
        lg_journals_pids_only = set([i[0:13] for i in legacy_journals])
        to_remove_journals = list(am_journals_pids_only - lg_journals_pids_only)

        # Removing Documents
        total_to_remove_documents = len(to_remove_documents)
        logger.info(
            'Documents to be removed from articlemeta (%d)',
            total_to_remove_documents
        )

        skip_deletion = True
        if total_to_remove_documents > SECURE_ARTICLE_DELETIONS_NUMBER:
            logger.info('To many documents to be removed')
            if force_delete is False:
                skip_deletion = True
                logger.info('force_delete is setup to %s, the remove task will be skipped', force_delete)
            else:
                skip_deletion = False

        for ndx, item in enumerate(to_remove_documents, 1):
            item = item.split('_')
            if skip_deletion is True:
                logger.debug(
                    'Document remove task (%d, %d) will be skipped (%s)',
                    ndx,
                    total_to_remove_documents,
                    '_'.join([item[0], item[1]])
                )
            try:
                rc.delete_document(item[1], item[0])
                logger.debug(
                    'Document (%d, %d) removed from Articlemeta (%s)',
                    ndx,
                    total_to_remove_documents,
                    '_'.join([item[0], item[1]])
                )
            except UnauthorizedAccess:
                logger.warning('Unauthorized access to remove itens, check the ArticleMeta admin token')

        # Including and Updating Documents
        logger.info(
            'Documents being included into articlemeta (%d)',
            len(new_documents)
        )
        for ndx, item in enumerate(new_documents, 1):
            item = item.split('_')
            try:
                document_meta = ctrl.load_document(item[0], item[1])
            except:
                logger.error(
                    'Fail to load document into Articlemeta (%s)',
                    '_'.join([item[0], item[1]])
                )
                continue

            if not document_meta:
                logger.error(
                    'Fail to load document into Articlemeta (%s)',
                    '_'.join([item[0], item[1]])
                )
                continue

            try:
                rc.add_document(json.dumps(document_meta))
            except ServerError:
                logger.error(
                    'Fail to load document into Articlemeta (%s)',
                    '_'.join([item[0], item[1]])
                )
                continue

            logger.debug(
                'Document (%d, %d) loaded into Articlemeta (%s)',
                ndx, len(new_documents),
                '_'.join([item[0], item[1]])
            )

        # Removing Journals
        total_to_remove_journals = len(to_remove_journals)
        logger.info(
            'Journals to be removed from articlemeta (%d)',
            total_to_remove_journals
        )

        skip_deletion = True
        if total_to_remove_journals > SECURE_JOURNAL_DELETIONS_NUMBER:
            logger.info('To many journals to be removed')
            if force_delete is False:
                skip_deletion = True
                logger.info('force_delete is setup to %s, the remove task will be skipped', force_delete)
            else:
                skip_deletion = False

        for ndx, item in enumerate(to_remove_journals, 1):
            item = item.split('_')
            if skip_deletion is True:
                logger.debug(
                    'Journal remove task (%d, %d) will be skipped (%s)',
                    ndx,
                    total_to_remove_journals,
                    '_'.join([item[0], item[1]])
                )
            try:
                rc.delete_journal(item[1], item[0])
                logger.debug(
                    'Journal (%d, %d) removed from Articlemeta (%s)',
                    ndx,
                    total_to_remove_journals,
                    '_'.join([item[0], item[1]])
                )
            except UnauthorizedAccess:
                logger.warning('Unauthorized access to remove itens, check the ArticleMeta admin token')

        # Including and Updating Journals
        logger.info(
            'Journals being included into articlemeta (%d)',
            len(new_journals)
        )
        for ndx, item in enumerate(new_journals, 1):
            item = item.split('_')
            try:
                journal_meta = ctrl.load_journal(item[0], item[1])
            except:
                logger.error(
                    'Fail to load journal into Articlemeta (%s)',
                    '_'.join([item[0], item[1]])
                )
                continue
            if not journal_meta:
                logger.error(
                    'Fail to load journal into Articlemeta (%s)',
                    '_'.join([item[0], item[1]])
                )
                continue

            try:
                rc.add_journal(json.dumps(journal_meta))
            except ServerError:
                logger.error(
                    'Fail to load journal into Articlemeta (%s)',
                    '_'.join([item[0], item[1]])
                )
                continue

            logger.debug(
                'Journal (%d, %d) loaded into Articlemeta (%s)',
                ndx,
                len(new_journals),
                '_'.join([item[0], item[1]])
            )

        # Removing Issues
        total_to_remove_issues = len(to_remove_issues)
        logger.info(
            'Issues to be removed from articlemeta (%d)',
            total_to_remove_issues
        )

        skip_deletion = True
        if total_to_remove_issues > SECURE_ISSUE_DELETIONS_NUMBER:
            logger.info('To many issues to be removed')
            if force_delete is False:
                skip_deletion = True
                logger.info('force_delete is setup to %s, the remove task will be skipped', force_delete)
            else:
                skip_deletion = False

        for ndx, item in enumerate(to_remove_issues, 1):
            item = item.split('_')
            if skip_deletion is True:
                logger.debug(
                    'Issue remove task (%d, %d) will be skipped (%s)',
                    ndx,
                    total_to_remove_issues,
                    '_'.join([item[0], item[1]])
                )
            try:
                rc.delete_issue(item[1], item[0])
                logger.debug(
                    'Issue (%d, %d) removed from Articlemeta (%s)',
                    ndx,
                    total_to_remove_issues,
                    '_'.join([item[0], item[1]])
                )
            except UnauthorizedAccess:
                logger.warning('Unauthorized access to remove itens, check the ArticleMeta admin token')

        # Including and Updating Issues
        logger.info(
            'Issues being included into articlemeta (%d)',
            len(new_issues)
        )
        for ndx, item in enumerate(new_issues, 1):
            item = item.split('_')

            try:
                issue_meta = ctrl.load_issue(item[0], item[1])
            except:
                logger.error(
                    'Fail to load issue into Articlemeta (%s)',
                    '_'.join([item[0], item[1]])
                )
                continue

            if not issue_meta:
                logger.error(
                    'Fail to load issue into Articlemeta (%s)',
                    '_'.join([item[0], item[1]])
                )
                continue

            try:
                rc.add_issue(json.dumps(issue_meta))
            except ServerError:
                logger.error(
                    'Fail to load issue into Articlemeta (%s)',
                    '_'.join([item[0], item[1]])
                )
                continue

            logger.debug(
                'Issue (%d, %d) loaded into Articlemeta (%s)',
                ndx,
                len(new_issues),
                '_'.join([item[0], item[1]])
            )

    logger.info('Process Isis2mongo Finished')


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
        '--full_rebuild',
        '-f',
        action='store_true',
        help='Update all documents'
    )

    parser.add_argument(
        '--bulk_size',
        '-b',
        type=int,
        default=BULK_SIZE,
        help='Max size to bulk data'
    )

    parser.add_argument(
        '--force_delete',
        '-d',
        action='store_true',
        help='Force delete records when the number of deletions excedes the number of secure deletions'
    )

    parser.add_argument(
        '--logging_file',
        '-o',
        help='Full path to the log file'
    )

    parser.add_argument(
        '--logging_level',
        '-l',
        default=LOGGING_LEVEL,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Loggin level'
    )

    args = parser.parse_args()
    LOGGING['handlers']['console']['level'] = args.logging_level
    for lg, content in LOGGING['loggers'].items():
        content['level'] = args.logging_level
    logging.config.dictConfig(LOGGING)

    run(args.collection, args.issns, args.full_rebuild, args.force_delete, args.bulk_size)
