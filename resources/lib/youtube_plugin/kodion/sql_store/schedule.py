# -*- coding: utf-8 -*-
"""

    Copyright (C) 2018-2018 plugin.video.youtube

    SPDX-License-Identifier: GPL-2.0-only
    See LICENSES/GPL-2.0-only for more information.
"""

from __future__ import absolute_import, division, unicode_literals

from .storage import Storage, fromtimestamp


class Schedule(Storage):
    _table_name = 'storage_v2'
    _table_created = False
    _table_updated = False
    _sql = {
        '_partial': True,
        'create_table': (
            'CREATE TABLE'
            ' IF NOT EXISTS {table} ('
            '  key INTEGER PRIMARY KEY,'
            '  timestamp REAL,'
            '  value BLOB,'
            '  size INTEGER'
            ' );'
        ),
        'set': (
            'INSERT'
            ' INTO {table}'
            ' (timestamp, value, size)'
            ' VALUES (?,?,?);'
        ),
    }

    def __init__(self, filepath, migrate=False):
        super(Schedule, self).__init__(filepath, migrate=migrate)

    @staticmethod
    def _process_item(value, item):
        value['key'] = item[0]
        value['timestamp'] = item[1]
        return value

    def get_items(self, keys=None, limit=-1, process=None):
        if process is None:
            process = self._process_item
        result = self._get_by_ids(keys,
                                  oldest_first=False,
                                  process=process,
                                  as_dict=False,
                                  values_only=True,
                                  limit=limit)
        return result

    def get_item(self, key):
        result = self._get(key, process=self._process_item)
        return result

    def add_item(self, item):
        self._set(None, item, item['timestamp'])

    def del_item(self, item_id):
        self._remove(item_id)

    def update_item(self, item):
        self._update(item['key'], item, item['timestamp'])

    def _optimize_item_count(self, limit=-1, defer=False):
        return False

    def _optimize_file_size(self, limit=-1, defer=False):
        return False
