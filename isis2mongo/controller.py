import logging
import pymongo
import os
from datetime import datetime

from pymongo import MongoClient
from pymongo import errors
from pymongo.operations import UpdateOne

from isis2json import isis2json

logger = logging.getLogger(__name__)


class IsisDataBroker(object):

    def __init__(self, database):

        if not os.path.exists(database):
            raise IOError('File do not exists (%s)', database)

        self.database = database

    def read(self):

        for item in isis2json.iterIsoRecords(self.database, 3):
            yield item


class DataBroker(object):

    def __init__(self, database_id, drop=True):

        self.database_name = 'isis2mongo_%s' % database_id
        self.drop = drop

    def __enter__(self):
        logger.info('Creating temporary database (%s)', self.database_name)
        self.mongoconn = None
        self.mongocl = None
        self.mongodb
        self._ensure_indexes()
        return self

    def __exit__(self, *args):
        logger.info('Deleting temporary database (%s)', self.database_name)
        if self.drop:
            self.mongocl.drop_database(self.database_name)

    @property
    def journals_ids(self):
        journals = []
        for journal in self.mongodb['journals'].find({}, {'collection': 1, 'code': 1, 'processing_date': 1}):
            journals.append(
              '_'.join(
                [journal['collection'], journal['code'], journal['processing_date'].replace('-', '')])
            )

        return journals

    @property
    def issues_ids(self):
        issues = []
        for issue in self.mongodb['issues'].find({}, {'collection': 1, 'code': 1, 'processing_date': 1}):
            issues.append(
              '_'.join(
                [issue['collection'], issue['code'], issue['processing_date'].replace('-', '')])
            )

        return issues

    @property
    def articles_ids(self):
        articles = []
        for article in self.mongodb['articles'].find({}, {'collection': 1, 'code': 1, 'processing_date': 1}):
            articles.append(
              '_'.join(
                [article['collection'], article['code'], article['processing_date'].replace('-', '')])
            )
        return articles

    @property
    def references_ids(self):
        references = []
        for reference in self.mongodb['references'].find({}, {'collection': 1, 'code': 1, 'processing_date': 1}):
            references.append(
              '_'.join(
                [reference['collection'], reference['code'], reference['processing_date'].replace('-', '')])
            )

        return references

    @property
    def mongoclient(self):

        uri = os.environ.get('MONGODB_URI', "mongodb://mongo")
        port = os.environ.get('MONGODB_PORT', 27017)

        if not self.mongocl:
            self.mongocl = MongoClient(uri, int(port))

        return self.mongocl

    @property
    def mongodb(self):

        if not self.mongoconn:
            self.mongoconn = self.mongoclient[self.database_name]

        return self.mongoconn

    def _ensure_indexes(self):

        # Article Indexes
        self.mongodb['articles'].ensure_index([
            ('collection', pymongo.ASCENDING),
            ('code', pymongo.ASCENDING)], unique=True)
        self.mongodb['articles'].ensure_index([
            ('collection', pymongo.ASCENDING)])
        self.mongodb['articles'].ensure_index([
            ('document', pymongo.ASCENDING)])
        self.mongodb['articles'].ensure_index([
            ('issue', pymongo.ASCENDING)])
        self.mongodb['articles'].ensure_index([
            ('journal', pymongo.ASCENDING)])

        # Issues Indexes
        self.mongodb['issues'].ensure_index([
            ('collection', pymongo.ASCENDING),
            ('code', pymongo.ASCENDING)], unique=True)
        self.mongodb['issues'].ensure_index([
            ('collection', pymongo.ASCENDING)])
        self.mongodb['issues'].ensure_index([
            ('journal', pymongo.ASCENDING)])

        # Journals Indexes
        self.mongodb['journals'].ensure_index([
            ('collection', pymongo.ASCENDING),
            ('code', pymongo.ASCENDING)], unique=True)
        self.mongodb['journals'].ensure_index([
            ('collection', pymongo.ASCENDING)])
        self.mongodb['issues'].ensure_index([
            ('journal', pymongo.ASCENDING)])

        # References Indexes
        self.mongodb['references'].ensure_index([
            ('collection', pymongo.ASCENDING),
            ('document', pymongo.ASCENDING)])
        self.mongodb['references'].ensure_index([
            ('collection', pymongo.ASCENDING),
            ('code', pymongo.ASCENDING)], unique=True)
        self.mongodb['references'].ensure_index([
            ('collection', pymongo.ASCENDING)])
        self.mongodb['references'].ensure_index([
            ('document', pymongo.ASCENDING)])
        self.mongodb['issues'].ensure_index([
            ('journal', pymongo.ASCENDING)])

    def load_journal(self, collection, pid):

        metadata = self.mongodb['journals'].find_one(
            {'code': pid, 'collection': collection})
        del(metadata['_id'])
        del(metadata['journal'])

        return metadata

    def load_issue(self, collection, pid):

        metadata = {}

        issue_metadata = self.mongodb['issues'].find_one(
            {'code': pid, 'collection': collection})
        journal_metadata = self.mongodb['journals'].find_one(
            {'code': pid[:9], 'collection': collection})
        del(journal_metadata['_id'])
        del(journal_metadata['journal'])
        del(issue_metadata['_id'])
        del(issue_metadata['journal'])
        del(issue_metadata['issue'])

        metadata['title'] = journal_metadata
        metadata['issue'] = issue_metadata

        return metadata

    def load_document(self, collection, pid):

        metadata = {}

        document_metadata = self.mongodb['articles'].find_one(
            {'code': pid, 'collection': collection})
        journal_metadata = self.mongodb['journals'].find_one(
            {'code': pid[1:10], 'collection': collection})
        del(document_metadata['_id'])
        del(document_metadata['journal'])
        del(document_metadata['issue'])
        del(document_metadata['document'])
        del(journal_metadata['_id'])
        del(journal_metadata['journal'])

        metadata['title'] = journal_metadata
        metadata['article'] = document_metadata
        metadata['citations'] = []

        for citation in self.mongodb['references'].find(
                {'document': pid, 'collection': collection}):
            del(citation['_id'])
            del(citation['document'])
            del(citation['journal'])
            del(citation['issue'])
            metadata['citations'].append(citation)

        return metadata

    def bulk_update_field(self, collection, updates):
        bk_updates = []
        for collection, document_id, field, value in updates:
            bk_updates.append(
                UpdateOne({'code': document_id}, {'$set': {field: value}}, upsert=False)
            )

        try:
            self.mongodb[collection].bulk_write(bk_updates, ordered=False)
        except errors.BulkWriteError as e:
            # Ignore bulk erros, the errors are mainly related to legacy issues like duplicated keys in the legacy databases.
            pass

    def update_field(self, collection, document_id, field, value):
        try:
            self.mongodb[collection].update({'code': document_id}, {'$set': {field: value}})
        except:
            logger.error('Fail to update field %s' % str([collection, document_id, field, value]))

    def bulk_data(self, bulk):

        for collection, records in bulk.items():
            try:
                self.mongodb[collection].insert_many(records, ordered=False)
            except errors.BulkWriteError as e:
                # Ignore bulk erros, the errors are mainly related to legacy issues like duplicated keys in the legacy databases.
                pass

    def write_record(self, database_collection, record):

        fltr = {
            'code': record['code'],
            'collection': record['collection']
        }

        if len(record['code']) == 23:
            self.articles_ids.append('_'.join([record['collection'], record['code'], record['processing_date'].replace('-', '')]))

        if len(record['code']) == 17:
            self.issues_ids.append('_'.join([record['collection'], record['code'], record['processing_date'].replace('-', '')]))

        if len(record['code']) == 9:
            self.journals_ids.append('_'.join([record['collection'], record['code'], record['processing_date'].replace('-', '')]))

        try:
            logger.debug('Recording (%s)', record['collection']+record['code'])
            self.mongodb[database_collection].update(fltr, record, upsert=True)
            logger.debug('Recorded (%s)', record['collection']+record['code'])
        except:
            logger.exception('Fail to write record (%s)', record['collection']+record['code'])
