# -*- coding: utf-8 -*-
"""

    Copyright (C) 2014-2016 bromix (plugin.video.youtube)
    Copyright (C) 2016-2018 plugin.video.youtube

    SPDX-License-Identifier: GPL-2.0-only
    See LICENSES/GPL-2.0-only for more information.
"""

from __future__ import absolute_import, division, unicode_literals

import logging
from os.path import normcase
from sys import exc_info as sys_exc_info
from traceback import extract_stack, format_list, print_exception

from .compatibility import StringIO, string_type, xbmc
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


class RecordFormatter(logging.Formatter):
    def formatException(self, ei):
        tb_obj = ei[2]
        while tb_obj:
            next_tb_obj = tb_obj.tb_next
            if next_tb_obj:
                tb_obj = next_tb_obj
                continue
            with StringIO() as output:
                output.write('Stack (most recent call last):\n')
                for item in format_list(extract_stack(tb_obj.tb_frame)[:-1]):
                    output.write(item)
                print_exception(*ei, file=output)
                stack_info = output.getvalue()
                if stack_info[-1] == '\n':
                    stack_info = stack_info[:-1]
                return stack_info
        else:
            return None


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
    STANDARD_FORMATTER = RecordFormatter(
        fmt='[{addon_id}] {module}:{lineno}({funcName}) - {message}',
        style='{',
    )
    DEBUG_FORMATTER = RecordFormatter(
        fmt='[{addon_id}] {module}, line {lineno}, in {funcName}'
            '\n\t{message}',
        style='{',
    )

    _stack_info = False

    def __init__(self, level):
        super(Handler, self).__init__(level=level)
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


class KodiLogger(logging.Logger):
    _component_logging = False
    _stack_info = False

    def __init__(self, name, level=logging.DEBUG):
        super(KodiLogger, self).__init__(name=name, level=level)
        self.propagate = False
        self.addHandler(Handler(level=logging.DEBUG))

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
        if kwargs:
            msg = MessageFormatter(msg, *args, **kwargs)
            args = ()
        elif args and args[0] == '*(' and args[-1] == ')':
            msg = MessageFormatter(msg, *args[1:-1], **kwargs)
            args = ()

        stack_info = stack_info and self.stack_info
        sinfo = None
        if _srcfiles:
            try:
                fn, lno, func, sinfo = self.findCaller(stack_info, stacklevel)
            except ValueError:
                fn, lno, func = '(unknown file)', 0, '(unknown function)'
        else:
            fn, lno, func = '(unknown file)', 0, '(unknown function)'

        if exc_info:
            if isinstance(exc_info, BaseException):
                exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
            elif not isinstance(exc_info, tuple):
                exc_info = sys_exc_info()

        record = self.makeRecord(self.name, level, fn, lno, msg, args,
                                 exc_info, func, extra, sinfo)
        self.handle(record)

    def findCaller(self, stack_info=False, stacklevel=1):
        target_frame = logging.currentframe()
        if target_frame is None:
            return '(unknown file)', 0, '(unknown function)', None

        end_offset = 1
        last_frame = None
        while stacklevel > 0:
            next_frame = target_frame.f_back
            if next_frame is None:
                break
            target_frame = next_frame
            if _is_internal_frame(target_frame):
                continue
            if end_offset > 0:
                end_offset -= 1
            elif last_frame is None:
                last_frame = target_frame
            stacklevel -= 1

        if stack_info:
            with StringIO() as output:
                output.write('Stack (most recent call last):\n')
                for item in format_list(extract_stack(last_frame)[:-1]):
                    output.write(item)
                stack_info = output.getvalue()
                if stack_info[-1] == '\n':
                    stack_info = stack_info[:-1]
        else:
            stack_info = None

        target_frame_code = target_frame.f_code
        return (target_frame_code.co_filename,
                target_frame.f_lineno,
                target_frame_code.co_name,
                stack_info)

    def error_trace(self, msg, *args, stack_info=True, stacklevel=1, **kwargs):
        if self.isEnabledFor(ERROR):
            self._log(
                ERROR,
                msg,
                args,
                stack_info=stack_info,
                stacklevel=(stacklevel + 1),
                **kwargs
            )

    def debug_trace(self, msg, *args, stack_info=True, stacklevel=1, **kwargs):
        if self.isEnabledFor(DEBUG):
            self._log(
                DEBUG,
                msg,
                args,
                stack_info=stack_info,
                stacklevel=(stacklevel + 1),
                **kwargs
            )

    @property
    def debugging(self):
        return self.isEnabledFor(logging.DEBUG)

    @debugging.setter
    def debugging(self, value):
        if value:
            Handler.LEVELS[logging.DEBUG] = xbmc.LOGNOTICE
            self.setLevel(logging.DEBUG)
            root.setLevel(logging.DEBUG)
        else:
            Handler.LEVELS[logging.DEBUG] = xbmc.LOGDEBUG
            self.setLevel(logging.INFO)
            root.setLevel(logging.INFO)

    @property
    def stack_info(self):
        return type(self)._stack_info

    @stack_info.setter
    def stack_info(self, value):
        if value:
            type(self)._stack_info = True
            Handler.stack_info = True
        else:
            type(self)._stack_info = False
            Handler.stack_info = False

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
        return getLogger, ()


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


def error_trace(msg, *args, stack_info=True, stacklevel=1, **kwargs):
    root.error(msg,
               *args,
               stack_info=stack_info,
               stacklevel=(stacklevel + 1),
               **kwargs)


def debug_trace(msg, *args, stack_info=True, stacklevel=1, **kwargs):
    root.debug(msg,
               *args,
               stack_info=stack_info,
               stacklevel=(stacklevel + 1),
               **kwargs)


def getLogger(name=None):
    if not name or isinstance(name, string_type) and name == root.name:
        return root
    return KodiLogger.manager.getLogger(name)


_srcfiles = {
    normcase(getLogger.__code__.co_filename),
    normcase(logging.getLogger.__code__.co_filename),
}


def _is_internal_frame(frame):
    filename = normcase(frame.f_code.co_filename)
    return filename in _srcfiles or (
            'importlib' in filename and '_bootstrap' in filename
    )
