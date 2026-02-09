# -*- coding: utf-8 -*-
"""

    Copyright (C) 2014-2016 bromix (plugin.video.youtube)
    Copyright (C) 2016-2025 plugin.video.youtube

    SPDX-License-Identifier: GPL-2.0-only
    See LICENSES/GPL-2.0-only for more information.
"""

from __future__ import absolute_import, division, unicode_literals

from math import floor, log
from re import DOTALL, compile as re_compile


__all__ = (
    'channel_filter_split',
    'custom_filter_split',
    'fix_subtitle_stream',
    'friendly_number',
    'strip_html_from_text',
    'urls_in_text',
)


__RE_URL = re_compile(r'(https?://\S+)')


def urls_in_text(text, process=None, count=0, url_marker=None):
    if url_marker:
        url_re = re_compile(r'(https?://\S+|(?=%s)\S+)' % url_marker)
    else:
        url_re = __RE_URL
    if process:
        return url_re.sub(process, text, count=count)
    return url_re.findall(text)


def strip_html_from_text(text, tag_re=re_compile('<[^<]+?>')):
    """
    Removes html tags
    :param text: html text
    :param tag_re: RE pattern object used to match html tags
    :return:
    """
    return tag_re.sub('', text)


def friendly_number(value, precision=3, scale=('', 'K', 'M', 'B'), as_str=True):
    value = float('{value:.{precision}g}'.format(
        value=float(value),
        precision=precision,
    ))
    abs_value = abs(value)
    magnitude = 0 if abs_value < 1000 else int(log(floor(abs_value), 1000))
    output = '{output:f}'.format(
        output=value / 1000 ** magnitude
    ).rstrip('0').rstrip('.') + scale[magnitude]
    return output if as_str else (output, value)


def _srt_to_vtt(content,
                srt_re=re_compile(
                    br'\d+[\r\n]'
                    br'(?P<start>[\d:,]+) --> '
                    br'(?P<end>[\d:,]+)[\r\n]'
                    br'(?P<text>.+?)[\r\n][\r\n]',
                    flags=DOTALL,
                )):
    subtitle_iter = srt_re.finditer(content)
    try:
        subtitle = next(subtitle_iter).groupdict()
        start = subtitle['start'].replace(b',', b'.')
        end = subtitle['end'].replace(b',', b'.')
        text = subtitle['text']
    except StopIteration:
        return content
    next_subtitle = next_start = next_end = next_text = None
    output = [b'WEBVTT\n\n']
    while 1:
        if next_start and next_end:
            start = next_start
            end = next_end
        if next_subtitle:
            subtitle = next_subtitle
            text = next_text
        elif not subtitle:
            break

        try:
            next_subtitle = next(subtitle_iter).groupdict()
            next_start = next_subtitle['start'].replace(b',', b'.')
            next_end = next_subtitle['end'].replace(b',', b'.')
            next_text = next_subtitle['text']
        except StopIteration:
            if subtitle == next_subtitle:
                break
            subtitle = None
            next_subtitle = None

        if next_subtitle and end > next_start:
            if end > next_end:
                fill_start, fill_end = next_start, next_end
                end, next_start, next_end = fill_start, fill_end, end
                next_subtitle = None
            else:
                fill_start, fill_end = next_start, end
                end, next_start = fill_start, fill_end
                subtitle = None
            output.append(b'%s --> %s\n%s\n\n'
                          b'%s --> %s\n%s\n%s\n\n'
                          % (
                              start, end, text,
                              fill_start, fill_end, text, next_text,
                          ))
        elif end > start:
            output.append(b'%s --> %s\n%s\n\n' % (start, end, text))
    return b''.join(output)


def fix_subtitle_stream(stream_type,
                        content,
                        vtt_re=re_compile(
                            br'(\d+:\d+:\d+\.\d+ --> \d+:\d+:\d+\.\d+)'
                            br'(?: (?:'
                            br'align:start'
                            br'|position:0%'
                            br'|position:63%'
                            br'|line:0%'
                            br'))+'
                        ),
                        vtt_repl=br'\1'):
    content_type, sub_format, sub_type = stream_type
    if content_type != 'track':
        pass
    elif sub_format == 'vtt':
        content = vtt_re.sub(vtt_repl, content)
    elif sub_format == 'srt':
        content = _srt_to_vtt(content)
    return content


def channel_filter_split(filters_string):
    custom_filters = []
    channel_filters = {
        filter_string
        for filter_string in filters_string.split(',')
        if filter_string and custom_filter_split(filter_string, custom_filters)
    }
    return filters_string, channel_filters, custom_filters


def custom_filter_split(filter_string,
                        custom_filters,
                        criteria_re=re_compile(
                            r'{?{([^}]+)}{([^}]+)}{([^}]+)}}?'
                        )):
    criteria = criteria_re.findall(filter_string)
    if not criteria:
        return True
    custom_filters.append(criteria)
    return False
