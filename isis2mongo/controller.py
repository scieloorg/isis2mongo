import logging
import os
from datetime import datetime
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

class JsonBroker:

    def __init__(self, data={}):
        self._data = data

    def __exit__(self):
        pass

    def __enter__(self):
        pass

    def bulk_data(self, bulk):
        for collection, records in bulk.items():
                self._data[collection] = records
                print("Adicionando %s" % collection)

    @property
    def journals_ids(self):
        journals = []
        for journal in self._data['journals']:
            journals.append(
              '_'.join(
                [journal['collection'], journal['code'], journal['processing_date'].replace('-', '')])
            )

        return journals


    @property
    def issues_ids(self):
        issues = []
        for issue in self._data['issues']:
            issues.append(
              '_'.join(
                [issue['collection'], issue['code'], issue['processing_date'].replace('-', '')])
            )

        return issues

    @property
    def articles_ids(self):
        articles = []
        for article in self._data['articles']:
            articles.append(
              '_'.join(
                [article['collection'], article['code'], article['processing_date'].replace('-', '')])
            )
        return articles

    @property
    def references_ids(self):
        references = []
        for reference in self._data['references']:
            references.append(
              '_'.join(
                [reference['collection'], reference['code'], reference['processing_date'].replace('-', '')])
            )

        return references


    def load_journal(self, collection, pid):
        for journal in self._data['journals']:
            if journal["code"] == pid and \
                journal["collection"] == collection:
                return journal

    def load_issue(self, collection, pid):

        metadata = {}
        issue_metadata = None

        for issue in self._data['issues']:
            if issue["code"] == pid and \
                issue["collection"] == collection:
                issue_metadata = issue
                break # too ugly

        journal_metadata = self.load_journal(collection, pid[:9])

        try:
            del(journal_metadata['_id'])
            del(issue_metadata['_id'])
            del(journal_metadata['journal'])
            del(issue_metadata['journal'])
            del(issue_metadata['issue'])
        except KeyError:
            pass

        metadata['title'] = journal_metadata
        metadata['issue'] = issue_metadata

        return metadata