# -*- coding: utf-8 -*-
"""

    Copyright (C) 2014-2016 bromix (plugin.video.youtube)
    Copyright (C) 2016-2018 plugin.video.youtube

    SPDX-License-Identifier: GPL-2.0-only
    See LICENSES/GPL-2.0-only for more information.
"""

from __future__ import absolute_import, division, unicode_literals

from . import logging
from .constants import CHECK_SETTINGS, PATHS
from .context import XbmcContext
from .debug import Profiler
from .plugin import XbmcPlugin
from ..youtube import Provider


__all__ = ('run',)

_context = XbmcContext()
_log = logging.getLogger(__name__)
_plugin = XbmcPlugin()
_provider = Provider()
_profiler = Profiler(enabled=False, print_callees=False, num_lines=20)


def run(context=_context,
        log=_log,
        plugin=_plugin,
        provider=_provider,
        profiler=_profiler):

    if context.get_ui().pop_property(CHECK_SETTINGS):
        provider.reset_client()
        settings = context.get_settings(refresh=True)
    else:
        settings = context.get_settings()

    debug = settings.logging_enabled()
    if debug:
        log.debugging = True
        if debug & 2:
            log.stack_info = True
            log.component_logging = True
        else:
            log.stack_info = False
            log.component_logging = False
        profiler.enable(flush=True)
    else:
        log.debugging = False
        log.stack_info = False
        log.component_logging = False
        profiler.disable()

    current_path = context.get_path().rstrip('/')
    current_params = context.get_params()
    current_handle = context.get_handle()
    context.init()
    new_path = context.get_path().rstrip('/')
    new_params = context.get_params()
    new_handle = context.get_handle()

    forced = False
    if new_handle != -1:
        if current_path == PATHS.PLAY:
            forced = True
        elif current_path == new_path:
            if current_path:
                if current_params == new_params:
                    forced = True
                else:
                    if 'refresh' in current_params:
                        del current_params['refresh']
                    if 'refresh' in new_params:
                        del new_params['refresh']
                    if current_params == new_params:
                        forced = True
        elif current_handle == -1 or current_handle == new_handle:
            if not current_path and not current_params:
                forced = True
    if forced:
        refresh = context.refresh_requested(force=True, off=True)
        if refresh:
            new_params['refresh'] = refresh

    log_params = new_params.copy()
    for key in ('api_key', 'client_id', 'client_secret'):
        if key in log_params:
            log_params[key] = '<redacted>'

    system_version = context.get_system_version()
    log.info(('Running v{version}',
              'Kodi:   v{kodi}',
              'Python: v{python}',
              'Handle: {handle}',
              'Path:   |{path}|',
              'Params: |{params}|',
              'Forced: |{forced}|'),
             version=context.get_version(),
             kodi=str(system_version),
             python=system_version.get_python_version(),
             handle=new_handle,
             path=new_path,
             params=log_params,
             forced=forced)

    plugin.run(provider, context, forced=forced)

    if debug:
        profiler.print_stats()
