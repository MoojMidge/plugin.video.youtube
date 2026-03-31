# -*- coding: utf-8 -*-
"""

    Copyright (C) 2014-2016 bromix (plugin.video.youtube)
    Copyright (C) 2016-2025 plugin.video.youtube

    SPDX-License-Identifier: GPL-2.0-only
    See LICENSES/GPL-2.0-only for more information.
"""

from __future__ import absolute_import, division, unicode_literals

from ..abstract_plugin import AbstractPlugin
from ... import logging
from ...compatibility import string_type, xbmc, xbmcgui, xbmcplugin
from ...constants import (
    ACTION,
    BUSY_FLAG,
    CONTAINER_FOCUS,
    CONTAINER_ID,
    CONTAINER_POSITION,
    CONTEXT_MENU,
    PATHS,
    PLAYBACK_FAILED,
    PLAYER_VIDEO_ID,
    PLAYLIST_PATH,
    PLAYLIST_POSITION,
    PLAY_CANCELLED,
    PLAY_FORCED,
    PLAY_FORCE_AUDIO,
    PLAY_PROMPT_QUALITY,
    PLAY_PROMPT_SUBTITLES,
    PLAY_TIMESHIFT,
    PLAY_USING,
    PLUGIN_SLEEPING,
    PLUGIN_WAKEUP,
    REFRESH_CONTAINER,
    RELOAD_ACCESS_MANAGER,
    REROUTE_PATH,
    SYNC_API_KEYS,
    SYNC_LISTITEM,
    TRAKT_PAUSE_FLAG,
    VIDEO_ID,
    WINDOW_FALLBACK,
    WINDOW_REPLACE,
    WINDOW_RETURN,
)
from ...exceptions import KodionException
from ...items import (
    CommandItem,
    directory_listitem,
    image_listitem,
    media_listitem,
    playback_item,
    uri_listitem,
)
from ...utils.redact import parse_and_redact_uri


class XbmcPlugin(AbstractPlugin):
    _LIST_ITEM_MAP = {
        'AudioItem': media_listitem,
        'BookmarkItem': directory_listitem,
        'CommandItem': directory_listitem,
        'DirectoryItem': directory_listitem,
        'ImageItem': image_listitem,
        'SearchItem': directory_listitem,
        'SearchHistoryItem': directory_listitem,
        'NewSearchItem': directory_listitem,
        'NextPageItem': directory_listitem,
        'VideoItem': media_listitem,
        'WatchLaterItem': directory_listitem,
    }

    _PLAY_ITEM_MAP = {
        'AudioItem': playback_item,
        'BookmarkItem': playback_item,
        'UriItem': uri_listitem,
        'VideoItem': playback_item,
    }

    def __init__(self):
        super(XbmcPlugin, self).__init__()

    @staticmethod
    def end(context,
            handle=None,
            succeeded=True,
            update_listing=False,
            cache_to_disc=True,
            clear_props=None,
            post_run_operations=None):
        context.pop_param(CONTEXT_MENU)

        ui = context.get_ui()
        _clear_prop = ui.clear_property

        if clear_props is None:
            clear_props = {}
        if not clear_props.get('none', False):
            clear_all_props = clear_props.get('all', False)
            if clear_all_props:
                _clear_prop(PLAY_CANCELLED)
                _clear_prop(PLAY_FORCED)
                _clear_prop(PLAY_TIMESHIFT)
            if clear_all_props or not ui.busy_dialog_active():
                _clear_prop(BUSY_FLAG)
            if clear_all_props or clear_props.get('start_play', True):
                _clear_prop(PLAY_FORCE_AUDIO)
                _clear_prop(PLAY_TIMESHIFT)
                _clear_prop(PLAY_PROMPT_QUALITY)
                _clear_prop(PLAY_PROMPT_SUBTITLES)
            if clear_all_props or clear_props.get('end_play', True):
                _clear_prop(PLAY_USING)
                _clear_prop(TRAKT_PAUSE_FLAG, raw=True)

        handle = context.get_handle() if handle is None else handle
        if handle != -1:
            xbmcplugin.endOfDirectory(
                handle=handle,
                succeeded=succeeded,
                updateListing=update_listing,
                cacheToDisc=cache_to_disc,
            )
        return succeeded, post_run_operations

    def run(self,
            provider,
            context,
            plugin_globals,
            forced=False,
            is_same_path=False,
            refresh_target=None,
            **kwargs):
        handle = context.get_handle()
        ui = context.get_ui()

        uri = context.get_uri()
        path = context.get_path().rstrip('/')

        is_play_path = path == PATHS.PLAY
        force_play = plugin_globals.get(PLAY_FORCED)
        if force_play:
            plugin_globals[PLAY_FORCED] = None
            context.set_global(PLAY_FORCED, None)

        route = ui.pop_property(REROUTE_PATH)
        _post_run_operation = None
        post_run_operations = []
        succeeded = False

        was_busy = ui.get_property(BUSY_FLAG)
        if not was_busy:
            pass
        elif route:
            if not ui.busy_dialog_active():
                ui.clear_property(BUSY_FLAG)
        else:
            if not ui.busy_dialog_active():
                ui.clear_property(BUSY_FLAG)

            playlist_player = context.playlist_player()
            if is_play_path and playlist_player.is_playing():
                logging.warning('Multiple busy dialogs active'
                                ' - Playlist cleared to avoid Kodi crash')
                post_run_operations.append((
                    self.busy_playing_post_run_operation,
                    {
                        'context': context,
                        'items': playlist_player.get_items(),
                        'playlist_position': playlist_player.get_position(),
                    }
                ))
                playlist_player.clear()
            else:
                logging.warning('Multiple busy dialogs active'
                                ' - Plugin call ended to avoid Kodi crash')
                result, _post_run_operation = self.uri_operation(context, uri)
                succeeded = result
                if _post_run_operation:
                    post_run_operations.append(_post_run_operation)
                    _post_run_operation = None

            return self.end(
                context,
                handle=handle,
                succeeded=succeeded,
                update_listing=True,
                cache_to_disc=False,
                clear_props={'none': True},
                post_run_operations=post_run_operations,
            )

        if ui.get_property(PLUGIN_SLEEPING):
            context.ipc_exec(PLUGIN_WAKEUP)

        api_store = context.get_api_store()
        if api_store.loaded < plugin_globals.get(SYNC_API_KEYS, 0):
            api_store.sync(from_store=True)

        access_manager = context.get_access_manager()
        if access_manager.loaded < plugin_globals.get(RELOAD_ACCESS_MANAGER, 0):
            context.reload_access_manager()

        settings = context.settings()
        setup_wizard_required = settings.setup_wizard_enabled()
        if setup_wizard_required:
            provider.run_wizard(context, last_run=setup_wizard_required)
        show_fanart = settings.fanart_selection()

        try:
            if route:
                function_cache = context.get_function_cache()
                result, options = function_cache.run(
                    provider.navigate,
                    _oneshot=True,
                    _scope=function_cache.SCOPE_NONE,
                    context=context.clone(route),
                )
            else:
                result, options = provider.navigate(context)
                logging.debug('Plugin runner options: {options!r}',
                              options=options)
                if ui.get_property(REROUTE_PATH):
                    return self.end(
                        context,
                        handle=handle,
                        succeeded=False,
                        update_listing=True,
                        cache_to_disc=False,
                        clear_props={'none': True},
                        post_run_operations=post_run_operations,
                    )
        except KodionException as exc:
            result = None
            options = {}
            if not provider.handle_exception(context, exc):
                logging.exception('Error')
                ui.on_ok('Error in ContentProvider', exc.__str__())

        if refresh_target == uri:
            refresh_target = None
            ui.clear_property(REFRESH_CONTAINER)
            if not context.refresh_requested():
                post_run_operations.append((
                    context.send_notification,
                    {
                        'method': REFRESH_CONTAINER,
                        'data': {'target': uri},
                    },
                ))
        elif refresh_target is True:
            ui.clear_property(REFRESH_CONTAINER)
        else:
            refresh_target = None
        if not refresh_target and forced:
            played_video_id = plugin_globals.get(PLAYER_VIDEO_ID)
            if played_video_id:
                plugin_globals[PLAYER_VIDEO_ID] = None
                context.set_global(PLAYER_VIDEO_ID, None)
                focused_video_id = None
            else:
                focused_video_id = None if route else ui.get_property(VIDEO_ID)
                played_video_id = None
        else:
            focused_video_id = None
            played_video_id = None
        sync_items = (focused_video_id, played_video_id)

        play_cancelled = plugin_globals.get(PLAY_CANCELLED)
        if play_cancelled:
            plugin_globals[PLAY_CANCELLED] = None
            context.set_global(PLAY_CANCELLED, None)
            result = None

        force_refresh = options.get(provider.FORCE_REFRESH)
        force_resolve = options.get(provider.FORCE_RESOLVE)
        force_return = (
            options.get(provider.FORCE_RETURN)
            if force_refresh is None else
            True
        )

        result_item = None
        result_item_type = None
        items = None
        if isinstance(result, (list, tuple)):
            if not result:
                result = [
                    CommandItem(
                        name=context.localize('page.back'),
                        command='Action(Back)',
                        context=context,
                        image='DefaultFolderBack.png',
                        plot=context.localize('page.empty'),
                    )
                ]
                if force_return:
                    _, _post_run_operation = self.uri_operation(
                        context,
                        'command://Action(Back)'
                    )
                    if _post_run_operation:
                        post_run_operations.append(_post_run_operation)
                        _post_run_operation = None

            items = []
            for item in result:
                item_type = item.__class__.__name__

                if (force_resolve
                        and not result_item
                        and item_type in self._PLAY_ITEM_MAP
                        and item.playable):
                    result_item = item
                    result_item_type = item_type

                listitem_type = self._LIST_ITEM_MAP.get(item_type)
                if (not listitem_type
                        or (listitem_type == directory_listitem
                            and not item.available)):
                    continue

                items.append(listitem_type(
                    context,
                    item,
                    show_fanart=show_fanart,
                    to_sync=sync_items,
                ))
        else:
            result_item_type = result.__class__.__name__
            if result_item_type in self._PLAY_ITEM_MAP:
                result_item = result

        if items:
            content_type = options.get(provider.CONTENT_TYPE)
            if content_type:
                context.apply_content(**content_type)
            else:
                context.apply_content()
            succeeded = xbmcplugin.addDirectoryItems(
                handle, items, len(items)
            )
            cache_to_disc = options.get(provider.CACHE_TO_DISC, True)
            update_listing = options.get(provider.UPDATE_LISTING, False)

            fallback = options.get(provider.FALLBACK)
            if not fallback or fallback != ui.get_property(provider.FALLBACK):
                ui.clear_property(provider.FALLBACK)
        else:
            succeeded = bool(result)
            cache_to_disc = options.get(provider.CACHE_TO_DISC, False)
            update_listing = options.get(provider.UPDATE_LISTING, True)

        if result_item:
            if force_play and force_resolve and result_item.playable:
                pass
            elif (
                    (not forced and not force_resolve and not is_play_path)
                    or (force_resolve and not is_play_path)
                    or (not force_play and options.get(provider.FORCE_PLAY))
                    or not result_item.playable
            ):
                _, _post_run_operation = self.uri_operation(
                    context,
                    result_item.get_uri()
                )
                if _post_run_operation:
                    post_run_operations.append(_post_run_operation)
                    _post_run_operation = None
                    force_play = False
                    succeeded = bool(items)
            else:
                item = self._PLAY_ITEM_MAP[result_item_type](
                    context,
                    result_item,
                    show_fanart=show_fanart,
                )
                xbmcplugin.setResolvedUrl(
                    handle, succeeded=True, listitem=item
                )
        elif not items or force_return:
            fallback = options.get(provider.FALLBACK, not force_return)
            if force_refresh:
                _post_run_operation = (
                    context.send_notification,
                    {
                        'method': REFRESH_CONTAINER,
                        'data': {
                            'target': (
                                force_refresh
                                if isinstance(force_refresh, string_type) else
                                None
                            ),
                        },
                    },
                )
            elif not fallback:
                pass
            elif isinstance(fallback, string_type) and fallback != uri:
                if options.get(provider.POST_RUN):
                    _, _post_run_operation = self.uri_operation(
                        context,
                        fallback,
                    )
                else:
                    path, params = context.parse_uri(fallback, update=True)
                    logging.info(('Handle: {handle}',
                                  'Path:   {path!r} (new)',
                                  'Params: {params!p}',
                                  'Forced: False'),
                                 handle=handle,
                                 path=path,
                                 params=params)
                    return self.run(
                        provider,
                        context,
                        plugin_globals,
                        forced=False,
                        is_same_path=False,
                    )
            elif play_cancelled:
                _, _post_run_operation = self.uri_operation(context, uri)
            elif is_play_path:
                context.send_notification(
                    PLAYBACK_FAILED,
                    {VIDEO_ID: context.get_param(VIDEO_ID)},
                )
                # May not prevent the playback attempt from occurring and
                # subsequently failing
                item = xbmcgui.ListItem()
                item.setContentLookup(False)
                item.setProperties({
                    'isPlayable': 'false',
                })
                xbmcplugin.setResolvedUrl(
                    handle,
                    succeeded=False,
                    listitem=item,
                )
            elif context.is_plugin_folder():
                _, _post_run_operation = self.uri_operation(
                    context,
                    context.get_parent_uri(params={
                        WINDOW_FALLBACK: True,
                        WINDOW_REPLACE: True,
                        WINDOW_RETURN: False,
                    }),
                )
            else:
                _, _post_run_operation = self.uri_operation(
                    context,
                    'command://Action(Back)',
                )
            if _post_run_operation:
                post_run_operations.append(_post_run_operation)
                _post_run_operation = None

        if force_play:
            if result_item and not is_play_path:
                play_uri = result_item.get_uri()
            else:
                play_uri = uri
            path, params = context.parse_uri(
                play_uri,
                replace={'path': PATHS.PLAY},
                update=True,
            )
            logging.info(('Handle: {handle}',
                          'Path:   {path!r} (new)',
                          'Params: {params!p}',
                          'Forced: False'),
                         handle=handle,
                         path=path,
                         params=params)
            return self.run(
                provider,
                context,
                plugin_globals,
                forced=False,
                is_same_path=False,
            )

        if not force_return:
            if any(sync_items):
                context.send_notification(SYNC_LISTITEM, sync_items)

            container = ui.get_property(CONTAINER_ID)
            position = ui.get_property(CONTAINER_POSITION)

            if is_same_path:
                if (container and position
                        and (forced or position == 'current')
                        and (not played_video_id or route)):
                    post_run_operations.append((
                        context.send_notification,
                        {
                            'method': CONTAINER_FOCUS,
                            'data': {
                                CONTAINER_ID: container,
                                CONTAINER_POSITION: position,
                            },
                        },
                    ))

        return self.end(
            context,
            handle=handle,
            succeeded=succeeded,
            update_listing=update_listing,
            cache_to_disc=cache_to_disc,
            clear_props={
                'start_play': True,
                'end_play': not succeeded,
            },
            post_run_operations=post_run_operations,
        )

    @staticmethod
    def post_run(context, operations, **kwargs):
        ui = context.get_ui()

        timeout = kwargs.get('timeout', 30)
        interval = kwargs.get('interval', 0.1)
        busy = True

        while operations:
            _operations = operations
            operations = []
            for operation in _operations:
                while not ui.get_container(
                        container_type=False,
                        check_ready=True,
                ):
                    timeout -= interval
                    if timeout < 0:
                        logging.error('Container not ready'
                                      ' - Post run operation unable to execute')
                        break
                    context.sleep(interval)
                else:
                    if busy:
                        busy = ui.clear_property(BUSY_FLAG)
                    if isinstance(operation, tuple):
                        operation, operation_kwargs = operation
                    else:
                        operation_kwargs = None
                    logging.debug(('Executing queued post-run operation',
                                   'Operation: {operation}',
                                   'Arguments: {operation_kwargs!p}'),
                                  operation=operation,
                                  operation_kwargs=operation_kwargs,
                                  stacklevel=2)
                    if callable(operation):
                        if operation_kwargs:
                            result = operation(**operation_kwargs)
                        else:
                            result = operation()
                        if isinstance(result, dict):
                            new_operation = result.get('__new_operation__')
                            if new_operation:
                                operations.append(new_operation)
                    else:
                        context.execute(operation)
                    context.sleep(interval)

    @staticmethod
    def uri_operation(context, uri):
        if uri.startswith('script://'):
            _uri = uri[len('script://'):]
            log_operation = 'RunScript queued'
            log_uri = _uri
            operation = 'RunScript({0})'.format(_uri)
            result = True

        elif uri.startswith('command://'):
            _uri = uri[len('command://'):]
            log_operation = 'Builtin command queued'
            log_uri = _uri
            operation = _uri
            result = True

        elif uri.startswith('PlayMedia('):
            log_operation = 'PlayMedia queued'
            log_uri = uri[len('PlayMedia('):-1].split(',')
            log_uri[0] = parse_and_redact_uri(
                log_uri[0],
                redact_only=True,
            )
            log_uri = ','.join(log_uri)
            operation = uri
            result = True

        elif uri.startswith('RunPlugin('):
            log_operation = 'RunPlugin queued'
            log_uri = parse_and_redact_uri(
                uri[len('RunPlugin('):-1],
                redact_only=True,
            )
            operation = uri
            result = True

        elif uri.startswith('ActivateWindow('):
            log_operation = 'ActivateWindow queued'
            log_uri = uri[len('ActivateWindow('):-1].split(',')
            if len(log_uri) >= 2:
                log_uri[1] = parse_and_redact_uri(
                    log_uri[1],
                    redact_only=True,
                )
            log_uri = ','.join(log_uri)
            operation = uri
            result = False

        elif uri.startswith('ReplaceWindow('):
            log_operation = 'ReplaceWindow queued'
            log_uri = uri[len('ReplaceWindow('):-1].split(',')
            if len(log_uri) >= 2:
                log_uri[1] = parse_and_redact_uri(
                    log_uri[1],
                    redact_only=True,
                )
            log_uri = ','.join(log_uri)
            operation = uri
            result = False

        elif uri.startswith('Container.Update('):
            log_operation = 'Container.Update queued'
            log_uri = uri[len('Container.Update('):-1].split(',')
            if log_uri[0]:
                log_uri[0] = parse_and_redact_uri(
                    log_uri[0],
                    redact_only=True,
                )
            log_uri = ','.join(log_uri)
            operation = uri
            result = False

        elif uri.startswith('Container.Refresh('):
            log_operation = 'Container.Refresh queued'
            log_uri = uri[len('Container.Refresh('):-1].split(',')
            if log_uri[0]:
                log_uri[0] = parse_and_redact_uri(
                    log_uri[0],
                    redact_only=True,
                )
            log_uri = ','.join(log_uri)
            operation = uri
            result = False

        elif context.is_plugin_path(uri):
            parts, params, log_uri, _, _ = parse_and_redact_uri(uri)
            path = parts.path.rstrip('/')

            if path != PATHS.PLAY:
                log_operation = 'Redirect queued'
                operation = context.create_uri(
                    (PATHS.ROUTE, path or PATHS.HOME),
                    params,
                    run=True,
                )
                result = False

            elif params.get(ACTION, [None])[0] == 'list':
                log_operation = 'Redirect for listing queued'
                operation = context.create_uri(
                    (PATHS.ROUTE, path),
                    params,
                    run=True,
                )
                result = False

            else:
                log_operation = 'Redirect for playback queued'
                audio_only = context.get_ui().get_property(
                    PLAY_FORCE_AUDIO,
                    as_bool=True,
                )
                if audio_only is None:
                    audio_only = context.settings().audio_only()
                operation = context.create_uri(
                    path,
                    params,
                    play=(xbmc.PLAYLIST_MUSIC
                          if audio_only else
                          xbmc.PLAYLIST_VIDEO),
                )
                result = True

        else:
            operation = None
            result = False
            return result, operation

        logging.debug('{operation}: {uri!r}',
                      operation=log_operation,
                      uri=log_uri,
                      stacklevel=2)
        return result, operation

    @classmethod
    def busy_playing_post_run_operation(cls, context, items, playlist_position):
        ui = context.get_ui()
        position, remaining = playlist_position
        if position:
            path = items[position - 1]['file']
            old_path = ui.pop_property(PLAYLIST_PATH)
            old_position = ui.pop_property(PLAYLIST_POSITION)
            if (old_position and position == int(old_position)
                    and old_path and path == old_path):
                if not remaining:
                    return None
                position += 1

        timeout = 30
        while ui.busy_dialog_active():
            timeout -= 1
            if timeout < 0:
                logging.error('Multiple busy dialogs active'
                              ' - Extended busy period')
                break
            context.sleep(1)

        logging.warning('Multiple busy dialogs active'
                        ' - Reloading playlist...')

        playlist_player = context.playlist_player()
        num_items = playlist_player.add_items(items)
        if position:
            timeout = min(position, num_items)
        else:
            position = 1
            timeout = num_items

        retry = False
        while ui.busy_dialog_active() or playlist_player.size() < position:
            timeout -= 1
            if timeout < 0:
                logging.error('Multiple busy dialogs active'
                              ' - Playback restart failed, retrying...')
                retry = True
                break
            context.sleep(1)

        result = playlist_player.play_playlist_item(position, defer=retry)
        if result:
            _, new_operation = cls.uri_operation(context, result)
            if new_operation:
                result = {'__new_operation__': new_operation}
        return result
