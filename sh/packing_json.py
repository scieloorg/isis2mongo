#!/usr/bin/python2.7
#encode: utf-8

import sys
import os
import json


def packing_journal_json(pid):
    try:
        citations_raw_json = json.loads(open(
            '../output/isos/{0}/{1}_issue.json'.format(pid, pid)).read())

        return json.dumps(citations_raw_json['docs'][0])
    except:
        return None


def packing_issue_json(pid):
    try:
        citations_raw_json = json.loads(open(
            '../output/isos/{0}/{1}_title.json'.format(pid, pid)).read())

        return json.dumps(citations_raw_json['docs'][0])
    except:
        return None


def packing_article_json(pid):
    packed_json = {}
    try:
        citations_raw_json = json.loads(open(
            '../output/isos/{0}/{1}_bib4cit.json'.format(pid, pid)).read())

        packed_json['citations'] = citations_raw_json['docs']
    except:
        packed_json['citations'] = None

    try:
        title_raw_json = json.loads(open(
            '../output/isos/{0}/{1}_title.json'.format(pid, pid)).read())
        packed_json['title'] = title_raw_json['docs'][0]
    except:
        packed_json['title'] = None

    try:
        article_raw_json = json.loads(open(
            '../output/isos/{0}/{1}_artigo.json'.format(pid, pid)).read())
        packed_json['article'] = article_raw_json['docs'][0]
    except:
        packed_json['article'] = None

    return json.dumps(packed_json)

if __name__ == '__main__':
    if sys.argv[1] == 'article':
        print packing_article_json(sys.argv[2])
    if sys.argv[1] == 'journal':
        print packing_journal_json(sys.argv[2])
    if sys.argv[1] == 'issue':
        print packing_journal_json(sys.argv[2])