# -*- coding: utf-8 -*-
"""

    Copyright (C) 2014-2016 bromix (plugin.video.youtube)
    Copyright (C) 2016-2018 plugin.video.youtube

    SPDX-License-Identifier: GPL-2.0-only
    See LICENSES/GPL-2.0-only for more information.
"""

from __future__ import absolute_import, division, unicode_literals

import re

from .constants import content, paths
from .exceptions import KodionException
from .items import (
    DirectoryItem,
    NewSearchItem,
    SearchHistoryItem,
)
from .utils import to_unicode


class AbstractProvider(object):
    RESULT_CACHE_TO_DISC = 'cache_to_disc'  # (bool)
    RESULT_UPDATE_LISTING = 'update_listing'

    def __init__(self):
        # map for regular expression (path) to method (names)
        self._dict_path = {}

        # register some default paths
        self.register_path(r''.join((
            '^',
            '(?:', paths.HOME, ')?/?$'
        )), '_internal_root')

        self.register_path(r''.join((
            '^',
            paths.WATCH_LATER,
            '/(?P<command>add|clear|list|remove)/?$'
        )), 'on_watch_later')

        self.register_path(r''.join((
            '^',
            paths.BOOKMARKS,
            '/(?P<command>add|clear|list|remove)/?$'
        )), 'on_bookmarks')

        self.register_path(r''.join((
            '^',
            '(', paths.SEARCH, '|', paths.EXTERNAL_SEARCH, ')',
            '/(?P<command>input|query|list|remove|clear|rename)?/?$'
        )), '_internal_search')

        self.register_path(r''.join((
            '^',
            paths.HISTORY,
            '/?$'
        )), 'on_playback_history')

        self.register_path(r'(?P<path>.*\/)extrafanart\/([\?#].+)?$',
                           '_internal_on_extra_fanart')

        """
        Test each method of this class for the appended attribute '_re_match' by the
        decorator (RegisterProviderPath).
        The '_re_match' attributes describes the path which must match for the decorated method.
        """

        for method_name in dir(self):
            method = getattr(self, method_name, None)
            path = method and getattr(method, 'kodion_re_path', None)
            if path:
                self.register_path(path, method_name)

    def register_path(self, re_path, method_name):
        """
        Registers a new method by name (string) for the given regular expression
        :param re_path: regular expression of the path
        :param method_name: name of the method
        :return:
        """
        self._dict_path[re_path] = method_name

    def run_wizard(self, context):
        settings = context.get_settings()
        ui = context.get_ui()

        context.send_notification('check_settings', 'defer')

        wizard_steps = self.get_wizard_steps(context)

        step = 0
        steps = len(wizard_steps)

        try:
            if wizard_steps and ui.on_yes_no_input(
                    context.localize('setup_wizard'),
                    (context.localize('setup_wizard.prompt')
                     % context.localize('setup_wizard.prompt.settings'))
            ):
                for wizard_step in wizard_steps:
                    if callable(wizard_step):
                        step = wizard_step(self, context, step, steps)
                    else:
                        step += 1
        finally:
            settings.set_bool(settings.SETUP_WIZARD, False)
            context.send_notification('check_settings', 'process')

    def get_wizard_steps(self, context):
        # can be overridden by the derived class
        return []

    def navigate(self, context):
        path = context.get_path()

        for key in self._dict_path:
            re_match = re.search(key, path, re.UNICODE)
            if re_match is not None:
                method_name = self._dict_path.get(key, '')
                method = getattr(self, method_name, None)
                if method is not None:
                    result = method(context, re_match)
                    refresh = context.get_param('refresh', False)
                    if not isinstance(result, tuple):
                        options = {
                            self.RESULT_CACHE_TO_DISC: True,
                            self.RESULT_UPDATE_LISTING: refresh,
                        }
                    else:
                        result, options = result
                        if refresh:
                            options[self.RESULT_UPDATE_LISTING] = refresh
                    return result, options

        raise KodionException("Mapping for path '%s' not found" % path)

    # noinspection PyUnusedLocal
    @staticmethod
    def on_extra_fanart(context, re_match):
        """
        The implementation of the provider can override this behavior.
        :param context:
        :param re_match:
        :return:
        """
        return

    def _internal_on_extra_fanart(self, context, re_match):
        path = re_match.group('path')
        new_context = context.clone(new_path=path)
        return self.on_extra_fanart(new_context, re_match)

    def on_playback_history(self, context, re_match):
        raise NotImplementedError()

    def on_search(self, search_text, context, re_match):
        raise NotImplementedError()

    def on_root(self, context, re_match):
        raise NotImplementedError()

    def _internal_root(self, context, re_match):
        return self.on_root(context, re_match)

    def on_bookmarks(self, context, re_match):
        raise NotImplementedError()

    def on_watch_later(self, context, re_match):
        raise NotImplementedError()

    def _internal_search(self, context, re_match):
        params = context.get_params()
        ui = context.get_ui()

        command = re_match.group('command')
        search_history = context.get_search_history()

        if not command or command == 'query':
            query = to_unicode(params.get('q', ''))
            if not params.get('incognito') and not params.get('channel_id'):
                search_history.update(query)
            return self.on_search(query, context, re_match)

        if command == 'remove':
            query = params.get('q', '')
            search_history.remove(query)
            ui.refresh_container()
            return True

        if command == 'rename':
            query = params.get('q', '')
            result, new_query = ui.on_keyboard_input(
                context.localize('search.rename'), query
            )
            if result:
                search_history.rename(query, new_query)
                ui.refresh_container()
            return True

        if command == 'clear':
            search_history.clear()
            ui.refresh_container()
            return True

        if command == 'input':
            data_cache = context.get_data_cache()

            folder_path = context.get_infolabel('Container.FolderPath')
            query = None
            #  came from page 1 of search query by '..'/back
            #  user doesn't want to input on this path
            if (not params.get('refresh')
                    and folder_path.startswith('plugin://%s' % context.get_id())
                    and re.match('.+/(?:query|input)/.*', folder_path)):
                cached = data_cache.get_item('search_query', data_cache.ONE_DAY)
                if cached:
                    query = to_unicode(cached)
            else:
                result, input_query = ui.on_keyboard_input(
                    context.localize('search.title')
                )
                if result:
                    query = input_query

            if not query:
                return False

            data_cache.set_item('search_query', query)

            if not params.get('incognito') and not params.get('channel_id'):
                search_history.update(query)
            context.set_path(paths.SEARCH, 'query')
            return self.on_search(query, context, re_match)

        context.set_content(content.LIST_CONTENT)
        result = []

        location = context.get_param('location', False)

        # 'New Search...'
        new_search_item = NewSearchItem(
            context, location=location
        )
        result.append(new_search_item)

        for search in search_history.get_items():
            # little fallback for old history entries
            if isinstance(search, DirectoryItem):
                search = search.get_name()

            # we create a new instance of the SearchItem
            search_history_item = SearchHistoryItem(
                context, search, location=location
            )
            result.append(search_history_item)

        return result, {self.RESULT_CACHE_TO_DISC: False}

    def handle_exception(self, context, exception_to_handle):
        return True

    def tear_down(self, context):
        pass


class RegisterProviderPath(object):
    def __init__(self, re_path):
        self._kodion_re_path = re_path

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            # only use a wrapper if you need extra code to be run here
            return func(*args, **kwargs)

        wrapper.kodion_re_path = self._kodion_re_path
        return wrapper
