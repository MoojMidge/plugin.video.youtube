# -*- coding: utf-8 -*-
"""

    Copyright (C) 2014-2016 bromix (plugin.video.youtube)
    Copyright (C) 2016-2025 plugin.video.youtube

    SPDX-License-Identifier: GPL-2.0-only
    See LICENSES/GPL-2.0-only for more information.
"""

from __future__ import absolute_import, division, unicode_literals


from ..abstract_settings import AbstractSettings
from ... import logging
from ...constants import BOOL_FROM_STR
from ...utils.datetime import current_timestamp
from ...utils.system_version import current_system_version


class SettingsProxy(object):
    def __init__(self, instance):
        self.ref = instance

    if current_system_version.compatible(21):
        def get_bool(self, *args, **kwargs):
            return self.ref.getBool(*args, **kwargs)

        def set_bool(self, *args, **kwargs):
            return self.ref.setBool(*args, **kwargs)

        def get_int(self, *args, **kwargs):
            return self.ref.getInt(*args, **kwargs)

        def set_int(self, *args, **kwargs):
            return self.ref.setInt(*args, **kwargs)

        def get_str(self, *args, **kwargs):
            return self.ref.getString(*args, **kwargs)

        def set_str(self, *args, **kwargs):
            return self.ref.setString(*args, **kwargs)

        def get_str_list(self, *args, **kwargs):
            return self.ref.getStringList(*args, **kwargs)

        def set_str_list(self, *args, **kwargs):
            return self.ref.setStringList(*args, **kwargs)

    else:
        def get_bool(self, *args, **kwargs):
            return self.ref.getSettingBool(*args, **kwargs)

        def set_bool(self, *args, **kwargs):
            return self.ref.setSettingBool(*args, **kwargs)

        def get_int(self, *args, **kwargs):
            return self.ref.getSettingInt(*args, **kwargs)

        def set_int(self, *args, **kwargs):
            return self.ref.setSettingInt(*args, **kwargs)

        def get_str(self, *args, **kwargs):
            return self.ref.getSettingString(*args, **kwargs)

        def set_str(self, *args, **kwargs):
            return self.ref.setSettingString(*args, **kwargs)

        def get_str_list(self, setting):
            value = self.ref.getSetting(setting)
            return value.split(',') if value else []

        def set_str_list(self, setting, value):
            value = ','.join(value)
            return self.ref.setSetting(setting, value)


class XbmcPluginSettings(AbstractSettings):
    log = logging.getLogger(__name__)

    _proxy = None

    def __init__(self, xbmc_addon):
        self.init(xbmc_addon)


    def init(self, xbmc_addon):
        self._cache = {}
        if current_system_version.compatible(21):
            self.__class__._proxy = SettingsProxy(xbmc_addon.getSettings())
            # set methods in new Settings class are documented as returning a
            # bool, True if value was set, False otherwise, similar to how the
            # old set setting methods of the Addon class function. Except they
            # don't actually return anything...
            # Ignore return value until bug is fixed in Kodi
            self._check_set = False
        else:
            self.__class__._proxy = SettingsProxy(xbmc_addon)

        self._echo_level = self.log_level()
        self.loaded = current_timestamp()

    def reinit(self, *args, **kwargs):
        self.init(*args, **kwargs)

    def get_bool(self, setting, default=None, echo_level=2):
        if setting in self._cache:
            return self._cache[setting]

        error = False
        try:
            value = bool(self._proxy.get_bool(setting))
        except (TypeError, ValueError) as exc:
            error = exc
            try:
                value = self.get_string(setting, echo_level=0)
                value = BOOL_FROM_STR.get(value, default)
            except TypeError as exc:
                error = exc
                value = default
        except RuntimeError as exc:
            error = exc
            value = default

        if echo_level and self._echo_level:
            self.log.debug_trace('Get setting {name!r}:'
                                 ' {value!r} (bool, {state})',
                                 name=setting,
                                 value=value,
                                 state=(error if error else 'success'),
                                 stacklevel=echo_level)
        self._cache[setting] = value
        return value

    def set_bool(self, setting, value, echo_level=2):
        try:
            error = not self._proxy.set_bool(setting, value)
            if error and self._check_set:
                error = 'failed'
            else:
                error = False
                self._cache[setting] = value
        except (RuntimeError, TypeError) as exc:
            error = exc

        if echo_level and self._echo_level:
            self.log.debug_trace('Set setting {name!r}:'
                                 ' {value!r} (bool, {state})',
                                 name=setting,
                                 value=value,
                                 state=(error if error else 'success'),
                                 stacklevel=echo_level)
        return not error

    def get_int(self, setting, default=-1, process=None, echo_level=2):
        if setting in self._cache:
            return self._cache[setting]

        error = False
        try:
            value = int(self._proxy.get_int(setting))
            if process:
                value = process(value)
        except (TypeError, ValueError) as exc:
            error = exc
            try:
                value = self.get_string(setting, echo_level=0)
                value = int(value)
            except (TypeError, ValueError) as exc:
                error = exc
                value = default
        except RuntimeError as exc:
            error = exc
            value = default

        if echo_level and self._echo_level:
            self.log.debug_trace('Get setting {name!r}:'
                                 ' {value!r} (int, {state})',
                                 name=setting,
                                 value=value,
                                 state=(error if error else 'success'),
                                 stacklevel=echo_level)
        self._cache[setting] = value
        return value

    def set_int(self, setting, value, echo_level=2):
        try:
            error = not self._proxy.set_int(setting, value)
            if error and self._check_set:
                error = 'failed'
            else:
                error = False
                self._cache[setting] = value
        except (RuntimeError, TypeError) as exc:
            error = exc

        if echo_level and self._echo_level:
            self.log.debug_trace('Set setting {name!r}:'
                                 ' {value!r} (int, {state})',
                                 name=setting,
                                 value=value,
                                 state=(error if error else 'success'),
                                 stacklevel=echo_level)
        return not error

    def get_string(self, setting, default='', echo_level=2):
        if setting in self._cache:
            return self._cache[setting]

        error = False
        try:
            value = self._proxy.get_str(setting) or default
        except (RuntimeError, TypeError) as exc:
            error = exc
            value = default

        if echo_level and self._echo_level:
            log_setting = {setting: value}
            self.log.debug_trace('Get setting {setting!q} (str, {state})',
                                 setting=log_setting,
                                 state=(error if error else 'success'),
                                 stacklevel=echo_level)
        self._cache[setting] = value
        return value

    def set_string(self, setting, value, echo_level=2):
        try:
            error = not self._proxy.set_str(setting, value)
            if error and self._check_set:
                error = 'failed'
            else:
                error = False
                self._cache[setting] = value
        except (RuntimeError, TypeError) as exc:
            error = exc

        if echo_level and self._echo_level:
            log_setting = {setting: value}
            self.log.debug_trace('Set setting {setting!q} (str, {state})',
                                 setting=log_setting,
                                 state=(error if error else 'success'),
                                 stacklevel=echo_level)
        return not error

    def get_string_list(self, setting, default=None, echo_level=2):
        if setting in self._cache:
            return self._cache[setting]

        error = False
        try:
            value = self._proxy.get_str_list(setting)
            if not isinstance(value, list):
                value = [] if default is None else default
        except (RuntimeError, TypeError) as exc:
            error = exc
            value = [] if default is None else default

        if echo_level and self._echo_level:
            self.log.debug_trace('Get setting {name!r}:'
                                 ' {value} (list[str], {state})',
                                 name=setting,
                                 value=value,
                                 state=(error if error else 'success'),
                                 stacklevel=echo_level)
        self._cache[setting] = value
        return value

    def set_string_list(self, setting, value, echo_level=2):
        try:
            error = not self._proxy.set_str_list(setting, value)
            if error and self._check_set:
                error = 'failed'
            else:
                error = False
                self._cache[setting] = value
        except (RuntimeError, TypeError) as exc:
            error = exc

        if echo_level and self._echo_level:
            self.log.debug_trace('Set setting {name!r}:'
                                 ' {value} (list[str], {state})',
                                 name=setting,
                                 value=value,
                                 state=(error if error else 'success'),
                                 stacklevel=echo_level)
        return not error
