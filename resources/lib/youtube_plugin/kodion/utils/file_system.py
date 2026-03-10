# -*- coding: utf-8 -*-
"""

    Copyright (C) 2014-2016 bromix (plugin.video.youtube)
    Copyright (C) 2016-2025 plugin.video.youtube

    SPDX-License-Identifier: GPL-2.0-only
    See LICENSES/GPL-2.0-only for more information.
"""

from __future__ import absolute_import, division, unicode_literals

from os import makedirs as os_makedirs
from shutil import rmtree as shutil_rmtree

from .. import logging
from ..compatibility import xbmcvfs


def make_dirs(path):
    if not path.endswith('/'):
        path = ''.join((path, '/'))
    path = xbmcvfs.translatePath(path)

    if xbmcvfs.exists(path) or xbmcvfs.mkdirs(path):
        return path

    try:
        os_makedirs(path)
    except OSError:
        if not xbmcvfs.exists(path):
            logging.exception(('Failed', 'Path: %r'), path)
            return False
    return path


def rm_dir(path):
    if not path.endswith('/'):
        path = ''.join((path, '/'))
    path = xbmcvfs.translatePath(path)

    if not xbmcvfs.exists(path) or xbmcvfs.rmdir(path, force=True):
        return True

    try:
        shutil_rmtree(path)
    except OSError:
        logging.exception(('Failed', 'Path: %r'), path)
    return not xbmcvfs.exists(path)
