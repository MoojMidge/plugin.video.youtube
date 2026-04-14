# -*- coding: utf-8 -*-
"""

    Copyright (C) 2014-2016 bromix (plugin.video.youtube)
    Copyright (C) 2016-2025 plugin.video.youtube

    SPDX-License-Identifier: GPL-2.0-only
    See LICENSES/GPL-2.0-only for more information.
"""

from __future__ import absolute_import, division, unicode_literals

from sys import version_info as sys_version_info

from .kodi import jsonrpc


class SystemVersion(object):
    RELEASE_NAME_MAP = {
        22: 'Piers',
        21: 'Omega',
        20: 'Nexus',
        19: 'Matrix',
        18: 'Leia',
        17: 'Krypton',
        16: 'Jarvis',
        15: 'Isengard',
        14: 'Helix',
        13: 'Gotham',
        12: 'Frodo',
    }

    def __init__(self):
        try:
            result = jsonrpc(
                method='Application.GetProperties',
                params={'properties': ['version', 'name']},
            )['result'] or {}
        except (KeyError, TypeError):
            result = {}
        version = result.get('version') or {}

        tag = version.get('tag')
        if tag == 'stable':
            tag_version = -1
        elif tag:
            try:
                tag_version = int(version.get('tagversion'))
            except ValueError:
                tag_version = 0
        else:
            tag = ''
            tag_version = 0

        self._version = (
            version.get('major', 1),
            version.get('minor', 0),
            tag,
            tag_version
        )

        self._app_name = result.get('name', 'Unknown application')

        self._release_name = self.RELEASE_NAME_MAP.get(
            self._version[0],
            'Unknown release',
        )

        tag_str = ' '.join((
            tag,
            str(tag_version) if tag_version > 0 else ''
        )).strip()

        self._version_str = '{major}.{minor}{_}{tag} ({app} {release})'.format(
            major=self._version[0],
            minor=self._version[1],
            _=' ' if tag_str else '',
            tag=tag_str,
            app=self._app_name,
            release=self._release_name,
        )

        self._python_version = sys_version_info
        self._python_version_str = '{0}.{1}.{2} {3}'.format(*sys_version_info)

    def __str__(self):
        return self._version_str

    def get_app_name(self):
        return self._app_name

    def get_release_name(self):
        return self._release_name

    def get_version(self):
        return self._version

    def compatible(self, *version):
        return self._version >= version

    def get_python_version(self):
        return self._python_version_str

    def python_compatible(self, *version):
        return self._python_version >= version


current_system_version = SystemVersion()
