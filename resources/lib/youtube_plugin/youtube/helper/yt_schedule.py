# -*- coding: utf-8 -*-
"""

    Copyright (C) 2014-2016 bromix (plugin.video.youtube)
    Copyright (C) 2016-2018 plugin.video.youtube

    SPDX-License-Identifier: GPL-2.0-only
    See LICENSES/GPL-2.0-only for more information.
"""

from __future__ import absolute_import, division, unicode_literals

from . import v3
from ...kodion import KodionException
from ...kodion.constants import CONTENT, PATHS
from ...kodion.items import DirectoryItem, menu_items


def _process_list_schedule(provider, context):
    context.set_content(CONTENT.VIDEO_CONTENT)

    schedule_items = [
        DirectoryItem(
            context.localize('schedule.add'),
            context.create_uri((PATHS.SCHEDULE, 'new')),
            image='{media}/watch_later.png',
        ),
    ]

    schedule = context.get_schedule()
    current_tasks = schedule.get_items()
    if not current_tasks:
        return schedule_items

    v3_response = {
        'kind': 'plugin#pluginListResponse',
    }
    task_items = v3_response['items'] = []

    for task in current_tasks:
        task_params = task['params']
        if 'playlist_id' in task_params:
            item = {
                'kind': 'youtube#playlist',
                'id': task_params['playlist_id'],
                '_partial': True,
            }
        elif 'channel_id' in task_params:
            item = {
                'kind': 'youtube#channel',
                'id': task_params['channel_id'],
                '_partial': True,
            }
        elif 'video_id' in task_params:
            item = {
                'kind': 'youtube#video',
                'id': task_params['video_id'],
                '_partial': True,
            }
        elif 'uri' in task_params:
            item = {
                'kind': 'plugin#pluginItem',
                '_params': task_params,
            }
        elif 'command' in task_params:
            item = {
                'kind': 'plugin#commandItem',
                '_params': task_params,
            }
        else:
            continue

        item['_context_menu'] = {
            'context_menu': [
                # menu_items.schedule_edit(
                #     context, item_id
                # ),
                menu_items.schedule_remove(
                    context, task['key']
                ),
                menu_items.schedule_clear(
                    context
                ),
                menu_items.separator(),
            ],
            'position': 0,
            'replace': False,
        }
        task_items.append(item)

    schedule_items.extend(
        v3.response_to_items(provider, context, v3_response)
    )
    return schedule_items


def _process_clear_schedule(context):
    ui = context.get_ui
    localize = context.localize

    if ui.on_yes_no_input(
            context.get_name(),
            localize('schedule.clear.confirm')
    ):
        context.get_schedule().clear()

        task = {
            'type': 'refresh',  # refresh / reminder / play / custom
            'params': {
                'name': 'My Subscriptions',
                'uri': 'plugin://plugin.video.youtube/special/my_subscriptions',
            },
            'timestamp': None,
            'repeat': 1 * 60 * 60,
            'enable': False,
        }
        context.get_schedule().add_item(task)

        task = {
            'type': 'reminder',  # refresh / reminder / play / custom
            'params': {
                'video_id': 'dQw4w9WgXcQ',
            },
            'timestamp': None,
            'repeat': False,
            'enable': False,
        }
        context.get_schedule().add_item(task)

        task = {
            'type': 'play',  # refresh / reminder / play / custom
            'params': {
                'video_id': 'dQw4w9WgXcQ',
            },
            'timestamp': None,
            'repeat': False,
            'enable': False,
        }
        context.get_schedule().add_item(task)

        task = {
            'type': 'play',  # refresh / reminder / play / custom
            'params': {
                'playlist_id': 'OLPPnm121Qlcoo7kKykmswKG0IepmDUVpag',
                'order': 'shuffle',
            },
            'timestamp': None,
            'repeat': False,
            'enable': False,
        }
        context.get_schedule().add_item(task)

        task = {
            'type': 'custom',  # refresh / reminder / play / custom
            'params': {
                'name': 'Trending',
                'command': 'RunPlugin(plugin://plugin.video.youtube/special/popular_right_now)',
            },
            'timestamp': None,
            'repeat': 1 * 60 * 60,
            'enable': False,
        }
        context.get_schedule().add_item(task)

        ui.show_notification(
            localize('succeeded'),
            time_ms=2500,
            audible=False
        )
        ui.refresh_container()
        return True


def _process_new_schedule_item(context):
    return True


def _process_add_schedule_item(context):
    item = context.get_param('item')
    if not item:
        return False

    context.get_schedule().add_item(item)

    context.get_ui().show_notification(
        context.localize('schedule.added'),
        time_ms=2500,
        audible=False
    )
    return True


def _process_remove_schedule_item(context):
    item_id = context.get_param('item_id')
    if not item_id:
        return False

    context.get_schedule().del_item(item_id)
    ui = context.get_ui()
    localize = context.localize

    ui.show_notification(
        localize('removed') % localize('schedule.item'),
        time_ms=2500,
        audible=False
    )
    ui.refresh_container()
    return True


def _process_edit_schedule_item(context):
    params = context.get_params()
    item = params.get('item')
    item_id = params.get('item_id')

    context.get_schedule().del_item(item_id)
    context.get_schedule().add_item(item)

    ui = context.get_ui()
    ui.show_notification(
        context.localize('schedule.added'),
        time_ms=2500,
        audible=False
    )
    ui.refresh_container()
    return True


def process(provider, context, re_match):
    method = re_match.group('method')

    if method == 'list':
        return _process_list_schedule(provider, context)

    if method == 'clear':
        return _process_clear_schedule(context)

    if method == 'remove':
        return _process_remove_schedule_item(context)

    raise KodionException('Unknown method: %s' % method)
