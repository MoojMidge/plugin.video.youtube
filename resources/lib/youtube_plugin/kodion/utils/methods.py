# -*- coding: utf-8 -*-
"""

    Copyright (C) 2014-2016 bromix (plugin.video.youtube)
    Copyright (C) 2016-2025 plugin.video.youtube

    SPDX-License-Identifier: GPL-2.0-only
    See LICENSES/GPL-2.0-only for more information.
"""

from __future__ import absolute_import, division, unicode_literals

from atexit import register as atexit_register
from weakref import ref as weakref_ref

from .. import logging
from ..compatibility import generate_hash, string_type, xbmc


__all__ = (
    'generate_hash',
    'loose_version',
    'merge_dicts',
    'register_clean_up',
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


def _clean_up(obj=None, weak_ref=None, attrs=None, class_attrs=None):
    if weak_ref:
        obj = weak_ref()
    if obj is None:
        return

    logging.verbose(('Cleaning up {obj}',
                     'Attrs:       {attrs}',
                     'Class attrs: {class_attrs}'),
                    obj=obj,
                    attrs=attrs,
                    class_attrs=class_attrs)

    if class_attrs:
        if attrs:
            attrs += class_attrs
        else:
            attrs = class_attrs

    if attrs:
        for name in attrs:
            try:
                clean_up = getattr(getattr(obj, name), 'clean_up', None)
                if clean_up:
                    clean_up()
                else:
                    setattr(obj, name, None)
            except AttributeError:
                pass

    if class_attrs:
        for name in class_attrs:
            try:
                obj_class = obj.__class__
                clean_up = getattr(getattr(obj_class, name), 'clean_up', None)
                if clean_up:
                    clean_up()
                else:
                    setattr(obj_class, name, None)
            except AttributeError:
                pass


def register_clean_up(*args, **kwargs):
    def _func(*_args, **_kwargs):
        if getattr(_func, '__completed__', False):
            return
        func(*args, **kwargs)
        _func.__completed__ = True

    obj = kwargs.pop('ref_obj', None)
    if obj:
        kwargs['weak_ref'] = weakref_ref(obj)

    func = kwargs.pop('func', _clean_up)
    atexit_register(_func, *args, **kwargs)

    return _func


def wait(timeout=None):
    if not timeout:
        timeout = 0
    elif timeout < 0:
        timeout = 0.1
    return xbmc.Monitor().waitForAbort(timeout)
