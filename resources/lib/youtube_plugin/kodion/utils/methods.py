# -*- coding: utf-8 -*-
"""

    Copyright (C) 2014-2016 bromix (plugin.video.youtube)
    Copyright (C) 2016-2025 plugin.video.youtube

    SPDX-License-Identifier: GPL-2.0-only
    See LICENSES/GPL-2.0-only for more information.
"""

from __future__ import absolute_import, division, unicode_literals

import json

from ..compatibility import generate_hash, string_type, xbmc


__all__ = (
    'generate_hash',
    'get_kodi_setting_bool',
    'get_kodi_setting_value',
    'jsonrpc',
    'loose_version',
    'merge_dicts',
    'wait',
)


def loose_version(v):
    return [point.zfill(8) for point in v.split('.')]


def merge_dicts(*dicts, **kwargs):
    new_dict = {}

    update_refs = kwargs.get('update_refs', False)
    if update_refs is False:
        ref_id = None
        _update_refs = False
    else:
        ref_id = str(id(new_dict)) + '.%s'
        if update_refs is True:
            _update_refs = {}
        else:
            _update_refs = update_refs

    index = 1
    num_dicts = len(dicts)
    while index <= num_dicts:
        try:
            dict2 = dicts[-index]
            index += 1
        except IndexError:
            break

        try:
            dict1 = dicts[-index]
            index += 1
        except IndexError:
            dict1 = dict2
            dict2 = new_dict
            new_dict = {}

        if isinstance(dict1, dict):
            keys = set(dict1)
            if isinstance(dict2, dict):
                keys.update(dict2)
        elif isinstance(dict2, dict):
            keys = set(dict2)
        else:
            return new_dict

        for key in keys:
            item1 = dict1.get(key, Ellipsis)
            item2 = dict2.get(key, Ellipsis)

            if item1 is KeyError or item2 is KeyError:
                continue
            elif item2 is Ellipsis:
                if item1 is Ellipsis:
                    continue
                value = item1
            elif isinstance(item1, dict) and isinstance(item2, dict):
                kwargs['update_refs'] = _update_refs
                value = merge_dicts(item1, item2, **kwargs)
                if value is Ellipsis:
                    continue
            elif (kwargs.get('str_compare')
                  and isinstance(item1, string_type)
                  and isinstance(item2, string_type)
                  and len(item1) > len(item2)):
                value = item1
            else:
                value = item2

            if ref_id and isinstance(value, string_type) and '{' in value:
                _update_refs[ref_id % key] = (new_dict, key, value)

            new_dict[key] = value

    if update_refs is True and _update_refs:
        for _dict, _key, _value in _update_refs.values():
            if _key not in _dict:
                continue
            try:
                _dict[_key] = _value.format(**new_dict)
            except (KeyError, TypeError, ValueError):
                del _dict[_key]

    return new_dict


def get_kodi_setting_value(setting, process=None):
    response = jsonrpc(method='Settings.GetSettingValue',
                       params={'setting': setting})
    try:
        value = response['result']['value']
        if process:
            return process(value)
    except (KeyError, TypeError, ValueError):
        return None
    return value


def get_kodi_setting_bool(setting):
    return xbmc.getCondVisibility(setting.join(('System.GetBool(', ')')))


def jsonrpc(batch=None, **kwargs):
    """
    Perform JSONRPC calls
    """

    if not batch and not kwargs:
        return None

    do_response = False
    for request_id, kwargs in enumerate(batch or (kwargs,)):
        do_response = (not kwargs.pop('no_response', False)) or do_response
        if do_response and 'id' not in kwargs:
            kwargs['id'] = request_id
        kwargs['jsonrpc'] = '2.0'

    request = json.dumps(batch or kwargs, default=tuple, ensure_ascii=False)
    response = xbmc.executeJSONRPC(request)
    return json.loads(response) if do_response else None


def wait(timeout=None):
    if not timeout:
        timeout = 0
    elif timeout < 0:
        timeout = 0.1
    return xbmc.Monitor().waitForAbort(timeout)
