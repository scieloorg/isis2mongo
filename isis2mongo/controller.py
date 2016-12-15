import logging
import pymongo
from pymongo import MongoClient

from isis2json import isis2json

logger = logging.getLogger(__name__)


class Isis2Json(object):

    def __init__(self, database):

        self.database = database

    def read(self):

        for item in isis2json.iterIsoRecords(self.database, 3):
            yield item


class DataBroker(object):

    def __init__(self, database_id, drop=True):

        self.database_name = 'isis2mongo_%s' % database_id
        self.drop = drop
        self.journals_ids = []
        self.issues_ids = []
        self.articles_ids = []
        self.collections_ids = []

    def __enter__(self):
        self.mongoconn = None
        self.mongocl = None
        self.mongodb
        self._ensure_indexes()
        return self

    def __exit__(self, *args):
        if self.drop:
            self.mongocl.drop_database(self.database_name)

    @property
    def mongoclient(self):
        if not self.mongocl:
            self.mongocl = MongoClient(
                'mongo', 27017)

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
            ('code', pymongo.ASCENDING)], unique=True)
        self.mongodb['references'].ensure_index([
            ('collection', pymongo.ASCENDING)])
        self.mongodb['references'].ensure_index([
            ('document', pymongo.ASCENDING)])
        self.mongodb['issues'].ensure_index([
            ('journal', pymongo.ASCENDING)])

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
            self.journals_ids.append('_'.join([record['collection'], record['code']]))

        try:
            logger.debug('Recording (%s)' % record['collection']+record['code'])
            self.mongodb[database_collection].update(fltr, record, upsert=True)
            logger.debug('Recorded (%s)' % record['collection']+record['code'])
        except:
            logger.exception()
