import calendar
import contextlib
import datetime as dt
import email.utils
import functools
import json
import re
import sys
import traceback
from importlib import import_module

try:
    from ....kodion.logger import log_debug
except ImportError:
    log_debug = print


class NO_DEFAULT:
    pass


def IDENTITY(x):
    return x


class YoutubeDLError(Exception):
    """Base exception for YoutubeDL errors."""
    msg = None

    def __init__(self, msg=None):
        if msg is not None:
            self.msg = msg
        elif self.msg is None:
            self.msg = type(self).__name__
        super().__init__(self.msg)


class ExtractorError(YoutubeDLError):
    """Error during info extraction."""

    def __init__(self, msg, tb=None, expected=False, cause=None, video_id=None, ie=None):
        """ tb, if given, is the original traceback (so that it can be printed out).
        If expected is set, this is a normal error message and most likely not a bug in yt-dlp.
        """
        # from ..networking.exceptions import network_exceptions
        # if sys.exc_info()[0] in network_exceptions:
        #     expected = True

        self.orig_msg = str(msg)
        self.traceback = tb
        self.expected = expected
        self.cause = cause
        self.video_id = video_id
        self.ie = ie
        self.exc_info = sys.exc_info()  # preserve original exception
        if isinstance(self.exc_info[1], ExtractorError):
            self.exc_info = self.exc_info[1].exc_info
        super().__init__(self.__msg)

    @property
    def __msg(self):
        return ''.join((
            format_field(self.ie, None, '[%s] '),
            format_field(self.video_id, None, '%s: '),
            self.orig_msg,
            format_field(self.cause, None, ' (caused by %r)'),
            # '' if self.expected else bug_reports_message(),
        ))

    def format_traceback(self):
        return join_nonempty(
            self.traceback and ''.join(traceback.format_tb(self.traceback)),
            self.cause and ''.join(traceback.format_exception(None, self.cause, self.cause.__traceback__)[1:]),
            delim='\n') or None

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if getattr(self, 'msg', None) and name not in ('msg', 'args'):
            self.msg = self.__msg or type(self).__name__
            self.args = (self.msg, )  # Cannot be property


class function_with_repr:
    def __init__(self, func, repr_=None):
        functools.update_wrapper(self, func)
        self.func, self.__repr = func, repr_

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    @classmethod
    def set_repr(cls, repr_):
        return functools.partial(cls, repr_=repr_)

    def __repr__(self):
        if self.__repr:
            return self.__repr
        return f'{self.func.__module__}.{self.func.__qualname__}'


DATE_FORMATS = (
    '%d %B %Y',
    '%d %b %Y',
    '%B %d %Y',
    '%B %dst %Y',
    '%B %dnd %Y',
    '%B %drd %Y',
    '%B %dth %Y',
    '%b %d %Y',
    '%b %dst %Y',
    '%b %dnd %Y',
    '%b %drd %Y',
    '%b %dth %Y',
    '%b %dst %Y %I:%M',
    '%b %dnd %Y %I:%M',
    '%b %drd %Y %I:%M',
    '%b %dth %Y %I:%M',
    '%Y %m %d',
    '%Y-%m-%d',
    '%Y.%m.%d.',
    '%Y/%m/%d',
    '%Y/%m/%d %H:%M',
    '%Y/%m/%d %H:%M:%S',
    '%Y%m%d%H%M',
    '%Y%m%d%H%M%S',
    '%Y%m%d',
    '%Y-%m-%d %H:%M',
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M:%S.%f',
    '%Y-%m-%d %H:%M:%S:%f',
    '%d.%m.%Y %H:%M',
    '%d.%m.%Y %H.%M',
    '%Y-%m-%dT%H:%M:%SZ',
    '%Y-%m-%dT%H:%M:%S.%fZ',
    '%Y-%m-%dT%H:%M:%S.%f0Z',
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%dT%H:%M:%S.%f',
    '%Y-%m-%dT%H:%M',
    '%b %d %Y at %H:%M',
    '%b %d %Y at %H:%M:%S',
    '%B %d %Y at %H:%M',
    '%B %d %Y at %H:%M:%S',
    '%H:%M %d-%b-%Y',
)

DATE_FORMATS_DAY_FIRST = list(DATE_FORMATS)
DATE_FORMATS_DAY_FIRST.extend([
    '%d-%m-%Y',
    '%d.%m.%Y',
    '%d.%m.%y',
    '%d/%m/%Y',
    '%d/%m/%y',
    '%d/%m/%Y %H:%M:%S',
    '%d-%m-%Y %H:%M',
    '%H:%M %d/%m/%Y',
])

DATE_FORMATS_MONTH_FIRST = list(DATE_FORMATS)
DATE_FORMATS_MONTH_FIRST.extend([
    '%m-%d-%Y',
    '%m.%d.%Y',
    '%m/%d/%Y',
    '%m/%d/%y',
    '%m/%d/%Y %H:%M:%S',
])

# From https://github.com/python/cpython/blob/3.11/Lib/email/_parseaddr.py#L36-L42
TIMEZONE_NAMES = {
    'UT': 0, 'UTC': 0, 'GMT': 0, 'Z': 0,
    'AST': -4, 'ADT': -3,  # Atlantic (used in Canada)
    'EST': -5, 'EDT': -4,  # Eastern
    'CST': -6, 'CDT': -5,  # Central
    'MST': -7, 'MDT': -6,  # Mountain
    'PST': -8, 'PDT': -7   # Pacific
}


def date_formats(day_first=True):
    return DATE_FORMATS_DAY_FIRST if day_first else DATE_FORMATS_MONTH_FIRST


def extract_timezone(date_str):
    m = re.search(
        r'''(?x)
            ^.{8,}?                                              # >=8 char non-TZ prefix, if present
            (?P<tz>Z|                                            # just the UTC Z, or
                (?:(?<=.\b\d{4}|\b\d{2}:\d\d)|                   # preceded by 4 digits or hh:mm or
                   (?<!.\b[a-zA-Z]{3}|[a-zA-Z]{4}|..\b\d\d))     # not preceded by 3 alpha word or >= 4 alpha or 2 digits
                   [ ]?                                          # optional space
                (?P<sign>\+|-)                                   # +/-
                (?P<hours>[0-9]{2}):?(?P<minutes>[0-9]{2})       # hh[:]mm
            $)
        ''', date_str)
    if not m:
        m = re.search(r'\d{1,2}:\d{1,2}(?:\.\d+)?(?P<tz>\s*[A-Z]+)$', date_str)
        timezone = TIMEZONE_NAMES.get(m and m.group('tz').strip())
        if timezone is not None:
            date_str = date_str[:-len(m.group('tz'))]
        timezone = dt.timedelta(hours=timezone or 0)
    else:
        date_str = date_str[:-len(m.group('tz'))]
        if not m.group('sign'):
            timezone = dt.timedelta()
        else:
            sign = 1 if m.group('sign') == '+' else -1
            timezone = dt.timedelta(
                hours=sign * int(m.group('hours')),
                minutes=sign * int(m.group('minutes')))
    return timezone, date_str


def format_field(obj, field=None, template='%s', ignore=NO_DEFAULT, default='', func=IDENTITY):
    # val = traversal.traverse_obj(obj, *variadic(field))
    # if not val if ignore is NO_DEFAULT else val in variadic(ignore):
    #     return default
    val = obj.get(field, default) if field else obj
    return template % func(val)


def js_to_json(code, vars={}, *, strict=False):
    # vars is a dict of var, val pairs to substitute
    STRING_QUOTES = '\'"`'
    STRING_RE = '|'.join(rf'{q}(?:\\.|[^\\{q}])*{q}' for q in STRING_QUOTES)
    COMMENT_RE = r'/\*(?:(?!\*/).)*?\*/|//[^\n]*\n'
    SKIP_RE = fr'\s*(?:{COMMENT_RE})?\s*'
    INTEGER_TABLE = (
        (fr'(?s)^(0[xX][0-9a-fA-F]+){SKIP_RE}:?$', 16),
        (fr'(?s)^(0+[0-7]+){SKIP_RE}:?$', 8),
    )

    def process_escape(match):
        JSON_PASSTHROUGH_ESCAPES = R'"\bfnrtu'
        escape = match.group(1) or match.group(2)

        return (Rf'\{escape}' if escape in JSON_PASSTHROUGH_ESCAPES
                else R'\u00' if escape == 'x'
                else '' if escape == '\n'
                else escape)

    def template_substitute(match):
        evaluated = js_to_json(match.group(1), vars, strict=strict)
        if evaluated[0] == '"':
            return json.loads(evaluated)
        return evaluated

    def fix_kv(m):
        v = m.group(0)
        if v in ('true', 'false', 'null'):
            return v
        elif v in ('undefined', 'void 0'):
            return 'null'
        elif v.startswith('/*') or v.startswith('//') or v.startswith('!') or v == ',':
            return ''

        if v[0] in STRING_QUOTES:
            v = re.sub(r'(?s)\${([^}]+)}', template_substitute, v[1:-1]) if v[0] == '`' else v[1:-1]
            escaped = re.sub(r'(?s)(")|\\(.)', process_escape, v)
            return f'"{escaped}"'

        for regex, base in INTEGER_TABLE:
            im = re.match(regex, v)
            if im:
                i = int(im.group(1), base)
                return f'"{i}":' if v.endswith(':') else str(i)

        if v in vars:
            try:
                if not strict:
                    json.loads(vars[v])
            except json.JSONDecodeError:
                return json.dumps(vars[v])
            else:
                return vars[v]

        if not strict:
            return f'"{v}"'

        raise ValueError(f'Unknown value: {v}')

    def create_map(mobj):
        return json.dumps(dict(json.loads(js_to_json(mobj.group(1) or '[]', vars=vars))))

    code = re.sub(r'(?:new\s+)?Array\((.*?)\)', r'[\g<1>]', code)
    code = re.sub(r'new Map\((\[.*?\])?\)', create_map, code)
    if not strict:
        code = re.sub(rf'new Date\(({STRING_RE})\)', r'\g<1>', code)
        code = re.sub(r'new \w+\((.*?)\)', lambda m: json.dumps(m.group(0)), code)
        code = re.sub(r'parseInt\([^\d]+(\d+)[^\d]+\)', r'\1', code)
        code = re.sub(r'\(function\([^)]*\)\s*\{[^}]*\}\s*\)\s*\(\s*(["\'][^)]*["\'])\s*\)', r'\1', code)

    return re.sub(rf'''(?sx)
        {STRING_RE}|
        {COMMENT_RE}|,(?={SKIP_RE}[\]}}])|
        void\s0|(?:(?<![0-9])[eE]|[a-df-zA-DF-Z_$])[.a-zA-Z_$0-9]*|
        \b(?:0[xX][0-9a-fA-F]+|0+[0-7]+)(?:{SKIP_RE}:)?|
        [0-9]+(?={SKIP_RE}:)|
        !+
        ''', fix_kv, code)


def join_nonempty(*values, delim='-', from_dict=None):
    # if from_dict is not None:
    #     values = (traversal.traverse_obj(from_dict, variadic(v)) for v in values)
    return delim.join(map(str, filter(None, values)))


def remove_quotes(s):
    if s is None or len(s) < 2:
        return s
    for quote in ('"', "'", ):
        if s[0] == quote and s[-1] == quote:
            return s[1:-1]
    return s


def strptime(datetime_str, fmt):
    try:
        return dt.datetime.strptime(datetime_str, fmt)
    except TypeError:
        pass

    if '_strptime' not in sys.modules:
        sys.modules['_strptime'] = import_module('_strptime')

    return sys.modules['_strptime']._strptime_datetime(
        dt.datetime, datetime_str, fmt
    )


def truncate_string(s, left, right=0):
    assert left > 3 and right >= 0
    if s is None or len(s) <= left + right:
        return s
    return f'{s[:left - 3]}...{s[-right:] if right else ""}'


def unified_timestamp(date_str, day_first=True):
    if not isinstance(date_str, str):
        return None

    date_str = re.sub(r'\s+', ' ', re.sub(
        r'(?i)[,|]|(mon|tues?|wed(nes)?|thu(rs)?|fri|sat(ur)?)(day)?', '', date_str))

    pm_delta = 12 if re.search(r'(?i)PM', date_str) else 0
    timezone, date_str = extract_timezone(date_str)

    # Remove AM/PM + timezone
    date_str = re.sub(r'(?i)\s*(?:AM|PM)(?:\s+[A-Z]+)?', '', date_str)

    # Remove unrecognized timezones from ISO 8601 alike timestamps
    m = re.search(r'\d{1,2}:\d{1,2}(?:\.\d+)?(?P<tz>\s*[A-Z]+)$', date_str)
    if m:
        date_str = date_str[:-len(m.group('tz'))]

    # Python only supports microseconds, so remove nanoseconds
    m = re.search(r'^([0-9]{4,}-[0-9]{1,2}-[0-9]{1,2}T[0-9]{1,2}:[0-9]{1,2}:[0-9]{1,2}\.[0-9]{6})[0-9]+$', date_str)
    if m:
        date_str = m.group(1)

    for expression in date_formats(day_first):
        with contextlib.suppress(ValueError):
            dt_ = strptime(date_str, expression) - timezone + dt.timedelta(hours=pm_delta)
            return calendar.timegm(dt_.timetuple())

    timetuple = email.utils.parsedate_tz(date_str)
    if timetuple:
        return calendar.timegm(timetuple) + pm_delta * 3600 - timezone.total_seconds()


write_string = log_debug
