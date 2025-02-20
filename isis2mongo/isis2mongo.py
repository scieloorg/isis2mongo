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
SECURE_ARTICLE_DELETIONS_NUMBER = int(os.environ.get('SECURE_ARTICLE_DELETIONS_NUMBER') or 50)
SECURE_ISSUE_DELETIONS_NUMBER = int(os.environ.get('SECURE_ISSUE_DELETIONS_NUMBER') or 2)
SECURE_JOURNAL_DELETIONS_NUMBER = int(os.environ.get('SECURE_JOURNAL_DELETIONS_NUMBER') or 2)
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


class IssuePidError(Exception):
    pass

def get_field_value(record, field_key, default=None):
    try:
        return record[field_key][0]['_']
    except (IndexError, KeyError, TypeError):
        return default


def log_numbers(name, am_items, legacy_items, legacy_database_name, new_items, to_remove_items):
    # log_numbers("documents", articlemeta_documents, legacy_documents, ctrl.database_name, new_documents, to_remove_documents)
    logger.info("%s - articlemeta = conjunto vazio ou status antes de processar", name)
    logger.info("%s - legacy = base de dados temporaria com items a inserir", name)
    logger.info("%s - %s - articlemeta (thrift ou conjunto vazio)", name, len(am_items))
    logger.info("%s - %s - legacy (%s)", name, len(legacy_items), legacy_database_name)
    logger.info("%s - %s - new (legacy menos articlemeta)", name, len(new_items))
    logger.info("%s - %s - to_remove (articlemeta menos legacy)", name, len(to_remove_items))


def delele_items_incorrect(name, to_remove_items, SECURE_DELETIONS_NUMBER, force_delete, rc_delete):
    # parece incorreto porque apagar os registros sempre
    total_to_remove = len(to_remove_items)
    logger.info(
        '%ss to be removed from articlemeta (%d)',
        name, total_to_remove
    )
    skip_deletion = True
    if total_to_remove > SECURE_DELETIONS_NUMBER:
        logger.info('To many %ss to be removed', name)
        if force_delete is False:
            skip_deletion = True
            logger.info('force_delete is setup to %s, the remove task will be skipped', force_delete)
        else:
            skip_deletion = False

    for ndx, item in enumerate(to_remove_items, 1):
        item = item.split('_')
        if skip_deletion is True:
            logger.debug(
                '%s remove task (%d, %d) will be skipped (%s)',
                name,
                ndx,
                total_to_remove,
                '_'.join([item[0], item[1]])
            )
        try:
            rc_delete(item[1], item[0])
            logger.debug(
                '%s (%d, %d) removed from Articlemeta (%s)',
                name,
                ndx,
                total_to_remove,
                '_'.join([item[0], item[1]])
            )
        except UnauthorizedAccess:
            logger.warning('Unauthorized access to remove itens, check the ArticleMeta admin token')


def delele_items(name, to_remove_items, SECURE_DELETIONS_NUMBER, force_delete, rc_delete): 
    total_to_remove = len(to_remove_items)
    logger.info(
        'Found %ss to be removed from articlemeta (%d)',
        name, total_to_remove
    )
    logger.info(
        '%ss SECURE_DELETIONS_NUMBER (%d)',
        name, SECURE_DELETIONS_NUMBER
    )
    logger.info(
        '%ss force_delete: (%s)',
        name, force_delete
    )

    # o padrão é apagar
    delete = True

    # verifica cancela apagar
    if total_to_remove > SECURE_DELETIONS_NUMBER:
        # inseguro apagar
        logger.info('ALERT: To many %ss to be removed. Force delete: %s', name, force_delete)
        delete = force_delete

    if not delete:
        logger.info('Cancel to delete %ss', name)
        return

    logger.info(
        'Removing %ss (%d)',
        name, total_to_remove
    )
    for ndx, item in enumerate(to_remove_items, 1):
        item = item.split('_')
        try:
            rc_delete(item[1], item[0])
            logger.debug(
                '%s (%d, %d) removed from Articlemeta (%s)',
                name,
                ndx,
                total_to_remove,
                '_'.join([item[0], item[1]])
            )
        except UnauthorizedAccess:
            logger.warning('Unauthorized access to remove itens, check the ArticleMeta admin token')


def add_items(name, new_items, ctrl_load_item, rc_add_item): 
    # Including and Updating ITEMs
    logger.info(
        '%ss being included into articlemeta (%d)',
        name,
        len(new_items)
    )
    for ndx, item in enumerate(new_items, 1):
        item = item.split('_')
        try:
            item_data = ctrl_load_item(item[0], item[1])
        except:
            logger.error(
                'Fail to load %s into Articlemeta (%s)',
                name,
                '_'.join([item[0], item[1]])
            )
            continue

        if not item_data:
            logger.error(
                'Fail to load %s into Articlemeta (%s)',
                name,
                '_'.join([item[0], item[1]])
            )
            continue

        try:
            rc_add_item(json.dumps(item_data))
        except ServerError:
            logger.error(
                'Fail to load %s into Articlemeta (%s)',
                name,
                '_'.join([item[0], item[1]])
            )
            continue

        logger.debug(
            '%s (%d, %d) loaded into Articlemeta (%s)',
            name,
            ndx, len(new_items),
            '_'.join([item[0], item[1]])
        )


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
    field_706 = get_field_value(record, 'v706')
    if field_706 != "i":
        return
    try:
        issn = record.get('v35', [{'_': None}])[0]['_']
        publication_year = record.get('v36', [{'_': None}])[0]['_'][0:4]
        issue_order = REGEX_FIXISSUEID.match(record.get('v36', [{'_': None}])[0]['_'][4:]).group() or 0
        order = "%04d" % int(issue_order)
        return issn+publication_year+order
    except Exception as e:
        raise IssuePidError(
            "Unable to get issue pid from %s: %s %s" % (record, type(e), e)
        )


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
        logger.info('Reading %s', isofile)

        try:
            isis_db = IsisDataBroker(isofile)
        except IOError:
            if iso in ['bib4cit', 'issue']:
                logger.warning('Not found %s.iso for %s, so it is expected to get their records from artigo.iso', iso, collection)
                continue
            raise ValueError('Not found %s.iso for %s' % (iso, collection))

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
    
    logger.info("full_rebuild=%s", full_rebuild)
    logger.info("articlemeta_documents (thrift ou conjunto vazio): %s", len(articlemeta_documents))
    logger.info("articlemeta_issues (thrift ou conjunto vazio): %s", len(articlemeta_issues))
    logger.info("articlemeta_journals (thrift ou conjunto vazio): %s", len(articlemeta_journals))

    with DataBroker(uuid.uuid4()) as ctrl:
        update_issue_id = ''

        fields_to_update_after_loading_documents = []
        bulk = {}

        bulk_count = 0
        total_bulked = 0
        times = 1
        # lê os registros de todas os isos disponíveis: title.iso, artigo.iso, ...
        for coll, record in load_isis_records(collection, issns):
            bulk_count += 1
            bulk.setdefault(coll, [])
            bulk[coll].append(record)
            if bulk_count == bulk_size:
                total_bulked += bulk_count
                logger.info("bulk_data: %s: %s, lote %s", coll, bulk_count, times)
                times += 1
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
        total_bulked += bulk_count
        logger.info("bulk_data: %s: %s, lote %s", coll, bulk_count, times)
        logger.info("total_bulk_data: %s: %s", coll, total_bulked)
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

        log_numbers("documents", articlemeta_documents, legacy_documents, ctrl.database_name, new_documents, to_remove_documents)
        log_numbers("issues", articlemeta_issues, legacy_issues, ctrl.database_name, new_issues, to_remove_issues)
        log_numbers("journals", articlemeta_journals, legacy_journals, ctrl.database_name, new_journals, to_remove_journals)

        # Removing Documents
        delele_items("document", to_remove_documents, SECURE_ARTICLE_DELETIONS_NUMBER, force_delete, rc.delete_document)

        # Including and Updating Documents
        add_items("document", new_documents, ctrl.load_document, rc.add_document)

        # Removing Journals
        delele_items("journal", to_remove_journals, SECURE_JOURNAL_DELETIONS_NUMBER, force_delete, rc.delete_journal)

        # Including and Updating Journals
        add_items("journal", new_journals, ctrl.load_journal, rc.add_journal)

        # Removing Issues
        delele_items("issue", to_remove_issues, SECURE_ISSUE_DELETIONS_NUMBER, force_delete, rc.delete_issue)

        # Including and Updating Issues
        add_items("issue", new_issues, ctrl.load_issue, rc.add_issue)


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
