# -*- coding: utf-8 -*-
"""

    Copyright (C) 2014-2016 bromix (plugin.video.youtube)
    Copyright (C) 2016-2025 plugin.video.youtube

    SPDX-License-Identifier: GPL-2.0-only
    See LICENSES/GPL-2.0-only for more information.
"""

from __future__ import absolute_import, division, unicode_literals

from .utils import get_thumbnail
from ...kodion import KodionException, logging
from ...kodion.constants import (
    CHANNEL_ID,
    CONTEXT_MENU,
    KEYMAP,
    FOLDER_URI,
    ITEM_NAME,
    PATHS,
    PLAYLIST_ID,
    PLAYLIST_ITEM_ID,
    REFRESH_CONTAINER,
    RELOAD_PATH,
    TITLE,
    URI,
    VIDEO_ID,
)


def _process_add_video(provider,
                       context,
                       playlist_id=None,
                       video_id=None,
                       confirmed=None):
    ui = context.get_ui()
    if confirmed:
        li_path = None
        li_video_id = None
    else:
        li_path = ui.get_listitem_info(URI)
        li_video_id = ui.get_listitem_property(VIDEO_ID)

    client = provider.get_client(context)
    if not client.logged_in:
        raise KodionException('Playlist/Add: not logged in')

    params = context.get_params()
    if confirmed is None:
        confirmed = params.pop('confirmed', False)

    if playlist_id is None:
        playlist_id = params.get(PLAYLIST_ID)
    if not playlist_id:
        if confirmed:
            return False, {provider.FORCE_RETURN: True}
        raise KodionException('Playlist/Add: missing playlist_id')

    position = 0
    playlist_id_upper = playlist_id.upper()
    if playlist_id == 'watch_later' or playlist_id_upper == 'WL':
        playlist_id = 'WL'
        _playlist_id = context.get_access_manager().get_watch_later_id()
        playlist_id_upper = _playlist_id.upper()
    elif playlist_id == 'history' or playlist_id_upper == 'HL':
        playlist_id = 'HL'
        _playlist_id = context.get_access_manager().get_watch_history_id()
        playlist_id_upper = _playlist_id.upper()
    elif playlist_id == 'liked' or playlist_id_upper == 'LL':
        playlist_id = 'LL'
        _playlist_id = playlist_id
        playlist_id_upper = playlist_id
    else:
        position = None
        _playlist_id = playlist_id

    if video_id is None:
        video_id = params.get(VIDEO_ID, li_video_id)
    if not video_id and li_path:
        video_id = context.parse_item_ids(li_path).get(VIDEO_ID)
    if not video_id:
        if confirmed:
            return False, {provider.FORCE_RETURN: True}
        raise KodionException('Playlist/Add: missing video_id')

    if playlist_id_upper != 'HL':
        success = client.add_video_to_playlist(
            _playlist_id,
            video_id,
            playlist_position=position,
        )

        if not confirmed:
            ui.show_notification(
                message=context.localize(
                    ('added.to.x', 'playlist')
                    if success else
                    ('failed.x', ('add.to.x', 'playlist'))
                ),
                time_ms=2500,
                audible=False,
            )

        if not success:
            logging.debug(('Failed',
                           'Video:    {video_id!r}',
                           'Playlist: {playlist_id!r}'),
                          video_id=video_id,
                          playlist_id=_playlist_id)
            return False, {provider.FORCE_RETURN: True}

    if playlist_id == 'HL':
        context.get_watch_later_list().add_item(video_id)

    data_cache = context.get_data_cache()
    playlist_cache = data_cache.get_items_like(
        ','.join((_playlist_id, '%')),
        limit=-1 if position == 0 else 1,
    )
    for cache_key, _, _ in playlist_cache:
        data_cache.del_item(cache_key)

    if params.get(KEYMAP) or not params.get(CONTEXT_MENU):
        ui.set_focus_next_item()

    return True, {provider.FORCE_RETURN: True}


def _process_remove_video(provider,
                          context,
                          playlist_id=None,
                          playlist_item_id=None,
                          video_id=None,
                          video_name=None,
                          confirmed=None):
    ui = context.get_ui()
    container_uri = ui.get_container_info(FOLDER_URI)
    if confirmed:
        li_path = None
        li_playlist_id = None
        li_playlist_item_id = None
        li_video_id = None
        li_video_name = None
    else:
        li_path = ui.get_listitem_info(URI)
        li_playlist_id = ui.get_listitem_property(PLAYLIST_ID)
        li_playlist_item_id = ui.get_listitem_property(PLAYLIST_ITEM_ID)
        li_video_id = ui.get_listitem_property(VIDEO_ID)
        li_video_name = ui.get_listitem_info(TITLE)

    client = provider.get_client(context)
    if not client.logged_in:
        raise KodionException('Playlist/Remove: not logged in')

    params = context.get_params()
    if confirmed is None:
        confirmed = params.pop('confirmed', False)

    if playlist_id is None:
        playlist_id = params.get(PLAYLIST_ID, li_playlist_id)
    if not playlist_id:
        if confirmed:
            return False, {provider.FORCE_RETURN: True}
        raise KodionException('Playlist/Remove: missing playlist ID')

    playlist_id_upper = playlist_id.upper()
    if playlist_id == 'watch_later' or playlist_id_upper == 'WL':
        playlist_id = 'WL'
        _playlist_id = context.get_access_manager().get_watch_later_id()
        playlist_id_upper = _playlist_id.upper()
    elif playlist_id == 'history' or playlist_id_upper == 'HL':
        playlist_id = 'HL'
        _playlist_id = context.get_access_manager().get_watch_history_id()
        playlist_id_upper = _playlist_id.upper()
    elif playlist_id == 'liked' or playlist_id_upper == 'LL':
        playlist_id = 'LL'
        _playlist_id = playlist_id
        playlist_id_upper = playlist_id
    else:
        _playlist_id = playlist_id

    if video_id is None:
        video_id = params.get(VIDEO_ID, li_video_id)
    if not video_id and li_path:
        video_id = context.parse_item_ids(li_path).get(VIDEO_ID)
    if not video_id:
        if confirmed:
            return False, {provider.FORCE_RETURN: True}
        raise KodionException('Playlist/Remove: missing video_id')

    if playlist_item_id is None:
        playlist_item_id = params.get(PLAYLIST_ITEM_ID, li_playlist_item_id)

    if video_name is None:
        video_name = params.get(ITEM_NAME, li_video_name)

    if not confirmed and not ui.on_remove_content(video_name):
        return False, {provider.FORCE_RETURN: True}

    if playlist_id_upper != 'HL':
        success = client.remove_video_from_playlist(
            playlist_id=_playlist_id,
            playlist_item_id=playlist_item_id,
            video_id=video_id,
        )

        if not confirmed:
            ui.show_notification(
                message=context.localize(
                    ('removed.from.x', 'playlist')
                    if success else
                    ('failed.x', ('remove.from.x', 'playlist'))
                ),
                time_ms=2500,
                audible=False,
            )

        if not success:
            logging.debug(('Failed',
                           'Video:         {video_id!r}',
                           'Playlist:      {playlist_id!r}',
                           'Playlist item: {playlist_item_id!r}'),
                          video_id=video_id,
                          playlist_id=_playlist_id,
                          playlist_item_id=playlist_item_id)
            return False, {provider.FORCE_RETURN: True}

    if playlist_id == 'WL':
        context.get_watch_later_list().del_item(video_id)

    data_cache = context.get_data_cache()
    playlist_cache = data_cache.get_items_like(
        ','.join((_playlist_id, '%')),
        oldest_first=False,
    )
    for cache_key, _, cached_page in playlist_cache:
        data_cache.del_item(cache_key)
        if not cached_page:
            continue
        for item in cached_page.get('items', []):
            if item.get('id') == video_id:
                break
        else:
            continue
        break

    if not container_uri:
        return False, {provider.FORCE_RETURN: True}

    if params.get(KEYMAP) or not params.get(CONTEXT_MENU):
        ui.set_focus_next_item()

    path, _ = context.parse_uri(container_uri)
    if path.rstrip('/').endswith((
            '/'.join((PATHS.PLAYLIST, playlist_id)),
            '/'.join((PATHS.PLAYLIST, _playlist_id)),
    )):
        if context.get_handle() == -1:
            context.send_notification(
                REFRESH_CONTAINER,
                {'target': container_uri},
            )
            options = None
        else:
            options = {
                provider.FORCE_REFRESH: True,
            }
    else:
        options = {
            provider.FALLBACK: params.pop(RELOAD_PATH, False),
            provider.FORCE_RETURN: True,
        }

    return True, options


def _process_remove_playlist(provider, context):
    ui = context.get_ui()
    channel_id = ui.get_listitem_property(CHANNEL_ID)
    li_playlist_id = ui.get_listitem_property(PLAYLIST_ID)
    li_playlist_name = ui.get_listitem_info(TITLE)

    params = context.get_params()
    localize = context.localize

    playlist_id = params.get(PLAYLIST_ID, li_playlist_id)
    if not playlist_id:
        raise KodionException('Playlist/Remove: missing playlist_id')

    playlist_name = params.get(ITEM_NAME, li_playlist_name) or ''

    if ui.on_delete_content(playlist_name):
        success = provider.get_client(context).remove_playlist(playlist_id)
    else:
        return False, {provider.FORCE_RETURN: True}

    ui.show_notification(
        message=(
            localize('removed.name.x', playlist_name)
            if success else
            localize(('failed.x', ('remove.x', 'playlist')))
        ),
        time_ms=2500,
        audible=False,
    )

    if not success:
        logging.debug(('Failed',
                       'Playlist: {playlist_name!r} ({playlist_id!r})'),
                      playlist_name=playlist_name,
                      playlist_id=playlist_id)
        return False, {provider.FORCE_RETURN: True}

    if channel_id:
        data_cache = context.get_data_cache()
        data_cache.del_item(channel_id)

    return (
        True,
        {
            provider.FORCE_REFRESH: context.is_plugin_folder(
                PATHS.MY_PLAYLISTS,
            ),
        },
    )


def _process_select_playlist(provider, context):
    ui = context.get_ui()
    li_path = ui.get_listitem_info(URI)
    li_video_id = ui.get_listitem_property(VIDEO_ID)

    params = context.get_params()
    localize = context.localize
    page_token = ''
    current_page = 0

    video_id = params.get(VIDEO_ID, li_video_id)
    if not video_id:
        item_ids = context.parse_item_ids(li_path)
        if item_ids and VIDEO_ID in item_ids:
            context.set_params(**item_ids)
        else:
            raise KodionException('Playlist/Select: missing video_id')

    function_cache = context.get_function_cache()
    client = provider.get_client(context)
    resource_manager = provider.get_resource_manager(context)

    # add the 'Watch Later' playlist
    playlists = resource_manager.get_related_playlists('mine')
    if playlists and 'watchLater' in playlists:
        watch_later_id = playlists['watchLater'] or 'WL'
    else:
        watch_later_id = context.get_access_manager().get_watch_later_id()

    # add the 'History' playlist
    if playlists and 'watchHistory' in playlists:
        watch_history_id = playlists['watchHistory'] or 'HL'
    else:
        watch_history_id = context.get_access_manager().get_watch_history_id()

    account_playlists = {watch_later_id, watch_history_id}

    thumb_size = context.settings().get_thumbnail_size()
    default_thumb = context.create_resource_path('media', 'playlist.png')

    while 1:
        current_page += 1
        json_data = function_cache.run(
            client.get_playlists_of_channel,
            function_cache.ONE_MINUTE // 3,
            _refresh=context.refresh_requested(),
            channel_id='mine',
            page_token=page_token,
        )
        if not json_data:
            break
        playlists = json_data.get('items', [])
        page_token = json_data.get('nextPageToken', '')

        items = []
        if current_page == 1:
            # Create a new playlist
            items.append((
                ui.bold(localize('playlist.create')), '',
                'playlist.create',
                default_thumb,
            ))

            # Add the 'Watch Later' playlist
            if watch_later_id:
                items.append((
                    ui.bold(localize('watch_later')), '',
                    watch_later_id,
                    context.create_resource_path('media', 'watch_later.png')
                ))

            # Add the custom 'History' playlist
            # Can't directly add items to the YouTube Watch History list
            if watch_history_id and watch_history_id.upper() != 'HL':
                items.append((
                    ui.bold(localize('history')), '',
                    watch_history_id,
                    context.create_resource_path('media', 'history.png')
                ))

        for playlist in playlists:
            playlist_id = playlist.get('id')
            if playlist_id in account_playlists:
                continue
            snippet = playlist.get('snippet', {})
            title = snippet.get('title')
            if title and playlist_id:
                items.append((
                    title,
                    snippet.get('description', ''),
                    playlist_id,
                    get_thumbnail(
                        thumb_size, snippet.get('thumbnails'), default_thumb
                    )
                ))

        if page_token:
            next_page = current_page + 1
            items.append((
                ui.bold(localize('page.next', next_page)), '',
                'playlist.next',
                'DefaultFolder.png',
            ))

        playlist_id = None
        result = ui.on_select(localize('playlist.select'), items)
        if result == 'playlist.next':
            continue
        elif result == 'playlist.create':
            result, text = ui.on_keyboard_input(localize('playlist.create'))
            if result and text:
                json_data = client.create_playlist(title=text)
                if not json_data:
                    break
                playlist_id = json_data.get('id', '')
        elif result != -1:
            playlist_id = result

        if playlist_id:
            new_params = dict(params, playlist_id=playlist_id)
            new_context = context.clone(new_params=new_params)
            _process_add_video(provider, new_context)
        break
    return True, {provider.FORCE_RETURN: True}


def _process_rename_playlist(provider, context):
    ui = context.get_ui()
    li_playlist_id = ui.get_listitem_property(PLAYLIST_ID)
    li_playlist_name = ui.get_listitem_info(TITLE)

    params = context.get_params()
    localize = context.localize

    playlist_id = params.get(PLAYLIST_ID, li_playlist_id)
    if not playlist_id:
        raise KodionException('Playlist/Rename: missing playlist_id')

    playlist_name = params.get(ITEM_NAME, li_playlist_name) or ''

    result, text = ui.on_keyboard_input(
        localize('rename'),
        default=playlist_name,
    )
    if not result or not text:
        return False, {provider.FORCE_RETURN: True}

    success = provider.get_client(context).rename_playlist(
        playlist_id=playlist_id,
        new_title=text,
    )

    ui.show_notification(
        message=(
            localize('succeeded')
            if success else
            localize(('failed.x', ('rename', 'playlist')))
        ),
        time_ms=2500,
        audible=False,
    )

    if not success:
        logging.debug(('Failed',
                       'Playlist: {playlist_name!r} ({playlist_id!r})'),
                      playlist_name=playlist_name,
                      playlist_id=playlist_id)
        return False, {provider.FORCE_RETURN: True}

    data_cache = context.get_data_cache()
    data_cache.del_item(playlist_id)
    return (
        True,
        {
            provider.FORCE_REFRESH: context.is_plugin_folder(
                PATHS.MY_PLAYLISTS,
            ),
        },
    )


def _playlist_id_change(provider, context, playlist, command):
    ui = context.get_ui()
    li_playlist_id = ui.get_listitem_property(PLAYLIST_ID)
    li_playlist_name = ui.get_listitem_info(TITLE)

    playlist_id = context.get_param(PLAYLIST_ID, li_playlist_id)
    if not playlist_id:
        raise KodionException('{type}/{command}: missing playlist_id'
                              .format(type=playlist, command=command))

    playlist_name = context.get_param(ITEM_NAME, li_playlist_name)
    if not playlist_name:
        raise KodionException('{type}/{command}: missing item_name'
                              .format(type=playlist, command=command))

    if not ui.on_yes_no_input(
            context.get_name(),
            context.localize(
                '{type}.list.{command}.check'.format(
                    type=playlist,
                    command=command,
                ),
                playlist_name
            ),
    ):
        return False, {provider.FORCE_RETURN: True}

    if command == 'unassign':
        playlist_id = None
    if playlist == 'watch_later':
        context.get_access_manager().set_watch_later_id(playlist_id)
    elif playlist == 'history':
        context.get_access_manager().set_watch_history_id(playlist_id)

    return (
        True,
        {
            provider.FORCE_REFRESH: context.is_plugin_folder(
                PATHS.MY_PLAYLISTS,
            ),
        },
    )


def _process_rate_playlist(provider,
                           context,
                           rating,
                           playlist_id=None,
                           playlist_name=None,
                           confirmed=None):
    ui = context.get_ui()
    container_uri = ui.get_container_info(FOLDER_URI)
    if confirmed:
        li_path = None
        li_playlist_id = None
        li_playlist_name = None
    else:
        li_path = ui.get_listitem_info(URI)
        li_playlist_id = ui.get_listitem_property(PLAYLIST_ID)
        li_playlist_name = ui.get_listitem_info(TITLE)

    client = provider.get_client(context)
    if not client.logged_in:
        raise KodionException('Playlist/Remove: not logged in')

    params = context.get_params()
    localize = context.localize
    save_playlist = rating == 'like'
    if confirmed is None:
        confirmed = params.pop('confirmed', False)

    if playlist_id is None:
        playlist_id = params.pop(PLAYLIST_ID, li_playlist_id)
    if not playlist_id:
        playlist_id = context.parse_item_ids(li_path).get(PLAYLIST_ID)
    if not playlist_id:
        if confirmed:
            return False, {provider.FORCE_RETURN: True}
        raise KodionException('Playlist/Rate: missing playlist_id')

    if playlist_name is None:
        playlist_name = params.pop(ITEM_NAME, li_playlist_name) or ''

    if (confirmed
            or save_playlist
            or ui.on_remove_content(playlist_name)):
        success = client.rate_playlist(playlist_id, rating)
    else:
        return False, {provider.FORCE_RETURN: True}

    if not confirmed:
        if success:
            msg = (
                localize('saved')
                if save_playlist else
                localize('removed.name.x', playlist_name)
            )
        elif success is False:
            msg = localize((
                'failed.x',
                'save' if save_playlist else 'remove',
            ))
        else:
            msg = None

        if msg:
            ui.show_notification(
                message=msg,
                time_ms=2500,
                audible=False,
            )

    if not success:
        logging.debug(('Failed',
                       'Playlist: {playlist_name!r} ({playlist_id!r})'),
                      playlist_name=playlist_name,
                      playlist_id=playlist_id)
        return False, {provider.FORCE_RETURN: True}

    if not container_uri:
        return False, {provider.FORCE_RETURN: True}

    if params.get(KEYMAP) or not params.get(CONTEXT_MENU):
        ui.set_focus_next_item()

    path, params = context.parse_uri(container_uri)
    if path.startswith(PATHS.SAVED_PLAYLISTS):
        options = {
            provider.FORCE_REFRESH: True,
        }
    else:
        options = {
            provider.FALLBACK: params.pop(RELOAD_PATH, False),
            provider.FORCE_RETURN: True,
        }

    return True, options


def process(provider,
            context,
            re_match=None,
            command=None,
            category=None,
            **kwargs):
    if re_match:
        if command is None:
            command = re_match.group('command')
        if category is None:
            category = re_match.group('category')

    if category == 'video':
        if command == 'add':
            return _process_add_video(provider, context, **kwargs)

        if command == 'remove':
            return _process_remove_video(provider, context, **kwargs)

    elif category == 'playlist':
        if command == 'remove':
            return _process_remove_playlist(provider, context)

        if command == 'select':
            return _process_select_playlist(provider, context)

        if command == 'rename':
            return _process_rename_playlist(provider, context)

        if command in {'like', 'unlike'}:
            return _process_rate_playlist(provider, context, command)

    elif category in {'watch_later', 'history'}:
        if command in {'assign', 'unassign'}:
            return _playlist_id_change(provider, context, category, command)

    raise KodionException('Unknown playlist category {0!r} or command {1!r}'
                          .format(category, command))
