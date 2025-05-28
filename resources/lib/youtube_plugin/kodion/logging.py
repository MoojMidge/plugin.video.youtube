# -*- coding: utf-8 -*-
"""

    Copyright (C) 2014-2016 bromix (plugin.video.youtube)
    Copyright (C) 2016-2018 plugin.video.youtube

    SPDX-License-Identifier: GPL-2.0-only
    See LICENSES/GPL-2.0-only for more information.
"""

from __future__ import absolute_import, division, unicode_literals

import logging

from .compatibility import xbmc
from .constants import ADDON_ID


__all__ = (
    'critical',
    'debug',
    'error',
    'exception',
    'info',
    'log',
    'warning',
    'CRITICAL',
    'DEBUG',
    'ERROR',
    'INFO',
    'WARNING',
)


class MessageFormatter(object):
    __slots__ = (
        'args',
        'kwargs',
        'msg',
    )

    def __init__(self, msg, *args, **kwargs):
        self.msg = msg
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return self.msg.format(*self.args, **self.kwargs)


class KodiLogger(logging.Logger):
    _component_logging = False
    _stack_info = False

    class Handler(logging.Handler):
        LEVELS = {
            logging.NOTSET: xbmc.LOGNONE,
            logging.DEBUG: xbmc.LOGDEBUG,
            # logging.INFO: xbmc.LOGINFO,
            logging.INFO: xbmc.LOGNOTICE,
            logging.WARN: xbmc.LOGWARNING,
            logging.WARNING: xbmc.LOGWARNING,
            logging.ERROR: xbmc.LOGERROR,
            logging.CRITICAL: xbmc.LOGFATAL,
        }

        _stack_info = False
        STANDARD_FORMATTER = logging.Formatter(
            fmt='[{addon_id}] {module}.{funcName} - {message}',
            style='{',
        )
        DEBUG_FORMATTER = logging.Formatter(
            fmt='[{addon_id}] {module}, line {lineno}, in {funcName}'
                '\n\t{message}',
            style='{',
        )

        def __init__(self, level):
            super(KodiLogger.Handler, self).__init__(level=level)
            self.setFormatter(self.STANDARD_FORMATTER)

        def emit(self, record):
            record.addon_id = ADDON_ID
            xbmc.log(
                msg=self.format(record),
                level=self.LEVELS.get(record.levelno, xbmc.LOGDEBUG),
            )

        def format(self, record):
            if self.stack_info:
                fmt = self.DEBUG_FORMATTER
            else:
                fmt = self.STANDARD_FORMATTER
            return fmt.format(record)

        @property
        def stack_info(self):
            return type(self)._stack_info

        @stack_info.setter
        def stack_info(self, value):
            type(self)._stack_info = value

    def __init__(self, name, level=logging.DEBUG):
        super(KodiLogger, self).__init__(name=name, level=level)
        self.addHandler(self.Handler(level=level))

    def _log(self,
             level,
             msg,
             args,
             exc_info=None,
             extra=None,
             stack_info=False,
             stacklevel=1,
             **kwargs):
        if isinstance(msg, (list, tuple)):
            msg = '\n\t'.join(msg)
        if kwargs or (args and args[0] == '*(' and args[-1] == ')'):
            msg = MessageFormatter(msg, *args, **kwargs)
            args = ()
        super(KodiLogger, self)._log(
            level, msg, args,
            exc_info=exc_info,
            extra=extra,
            stack_info=(stack_info and self.stack_info),
            stacklevel=(stacklevel + 1),
        )

    @property
    def debugging(self):
        return self.isEnabledFor(logging.DEBUG)

    @debugging.setter
    def debugging(self, value):
        if value:
            type(self).Handler.LEVELS[logging.DEBUG] = xbmc.LOGNOTICE
            self.setLevel(logging.DEBUG)
            self.root.setLevel(logging.DEBUG)
        else:
            type(self).Handler.LEVELS[logging.DEBUG] = xbmc.LOGDEBUG
            self.setLevel(logging.INFO)
            self.root.setLevel(logging.INFO)

    @property
    def stack_info(self):
        return type(self)._stack_info

    @stack_info.setter
    def stack_info(self, value):
        cls = type(self)
        if value:
            cls._stack_info = True
            cls.Handler.stack_info = True
        else:
            cls._stack_info = False
            cls.Handler.stack_info = False

    @property
    def component_logging(self):
        return type(self)._component_logging

    @component_logging.setter
    def component_logging(self, value):
        cls = type(self)
        if value:
            cls._component_logging = True
            logging.root = root
            logging.Logger.root = root
            logging.Logger.manager = manager
            logging.Logger.manager.setLoggerClass(KodiLogger)
            logging.setLoggerClass(KodiLogger)
        else:
            if cls._component_logging:
                logging.root = logging.RootLogger(logging.WARNING)
                logging.Logger.root = logging.root
                logging.Logger.manager = logging.Manager(logging.root)
                logging.Logger.manager.setLoggerClass(logging.Logger)
                logging.setLoggerClass(logging.Logger)
            cls._component_logging = False


class RootLogger(KodiLogger):
    def __init__(self, level):
        super(RootLogger, self).__init__('root', level)

    def __reduce__(self):
        return logging.getLogger, ()


root = RootLogger(logging.INFO)
KodiLogger.root = root
manager = logging.Manager(root)
KodiLogger.manager = manager
KodiLogger.manager.setLoggerClass(KodiLogger)

critical = root.critical
error = root.error
warning = root.warning
info = root.info
debug = root.debug
log = root.log

CRITICAL = logging.CRITICAL
ERROR = logging.ERROR
WARNING = logging.WARNING
INFO = logging.INFO
DEBUG = logging.DEBUG


def exception(msg, *args, exc_info=True, **kwargs):
    root.error(msg, *args, exc_info=exc_info, **kwargs)


def getLogger(name=None):
    if not name or isinstance(name, str) and name == root.name:
        return root
    return KodiLogger.manager.getLogger(name)
