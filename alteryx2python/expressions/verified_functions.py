"""Designer expression functions shared by the runtime and standalone compiler."""

from calendar import monthrange
from datetime import datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from hashlib import md5
import re

import pandas as pd


def get_word(value, index):
    if pd.isna(value) or pd.isna(index):
        return None
    words = re.findall(r'[^ \t\r\n]+', str(value))
    position = max(0, int(index))
    return words[position] if position < len(words) else None


def substring(value, start, length=None):
    if pd.isna(value) or pd.isna(start):
        return None
    start = int(start)
    end = None if pd.isna(length) else max(0, start + int(length))
    return str(value)[max(0, start):end]


def find_string(value, target):
    if pd.isna(value) or pd.isna(target):
        return -1
    return str(value).find(str(target))


def ends_with(value, target, ignore_case=True):
    if pd.isna(value) or pd.isna(target):
        return False
    text, suffix = str(value), str(target)
    return text.casefold().endswith(suffix.casefold()) if ignore_case else text.endswith(suffix)


def regex_count_matches(value, pattern, ignore_case=True):
    if pd.isna(value):
        return 0
    if pd.isna(pattern):
        return None
    flags = re.IGNORECASE if ignore_case else 0
    return sum(1 for _ in re.finditer(str(pattern), str(value), flags))


def md5_ascii(value):
    if pd.isna(value):
        return None
    return md5(str(value).encode('latin-1', errors='replace')).hexdigest()


def _round_multiple(value, multiple, direction, offset=Decimal(0)):
    if pd.isna(value) or pd.isna(multiple):
        return None
    number, step = Decimal(str(value)), Decimal(str(multiple))
    if not number.is_finite() or not step.is_finite() or step <= 0:
        return None
    return float(((number / step) + offset).to_integral_value(rounding=direction) * step)


def ceil(value, multiple=1):
    return _round_multiple(value, multiple, ROUND_CEILING)


def floor(value, multiple=1):
    return _round_multiple(value, multiple, ROUND_FLOOR)


def round_multiple(value, multiple):
    step = None if pd.isna(multiple) else abs(Decimal(str(multiple)))
    return _round_multiple(value, step, ROUND_FLOOR, Decimal('0.5'))


def datetime_parse(value, mask):
    if pd.isna(value) or pd.isna(mask):
        return None
    try:
        parsed = datetime.strptime(str(value), str(mask))
    except ValueError:
        return None
    return parsed.isoformat(sep=' ')


def datetime_trim(value, unit):
    if pd.isna(value) or pd.isna(unit):
        return None
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    period = str(unit).strip().lower()
    if period == 'lastofmonth':
        last_day = monthrange(moment.year, moment.month)[1]
        return moment.replace(day=last_day, hour=23, minute=59, second=59, microsecond=0).isoformat(sep=' ')
    if period == 'firstofmonth':
        period = 'month'
    units = ['year', 'month', 'day', 'hour', 'minute', 'second']
    period = period.rstrip('s')
    if period not in units:
        return None
    defaults = {'month': 1, 'day': 1, 'hour': 0, 'minute': 0, 'second': 0, 'microsecond': 0}
    fields = units[units.index(period) + 1:] + ['microsecond']
    return moment.replace(**{name: defaults[name] for name in fields}).isoformat(sep=' ')


def finance_pmt(rate, periods, present, future, pay_at_begin):
    if any(pd.isna(value) for value in (rate, periods, present, future, pay_at_begin)):
        return None
    rate, periods, present, future = map(float, (rate, periods, present, future))
    if periods == 0 or rate <= -1:
        return None
    if rate == 0:
        return -(present + future) / periods
    growth = (1 + rate) ** periods
    return -rate * (present * growth + future) / ((1 + rate * bool(pay_at_begin)) * (growth - 1))


def finance_mirr(finance_rate, reinvest_rate, *values):
    if len(values) < 2 or any(pd.isna(value) for value in (finance_rate, reinvest_rate, *values)):
        return None
    finance_rate, reinvest_rate = float(finance_rate), float(reinvest_rate)
    if finance_rate <= -1 or reinvest_rate <= -1:
        return None
    values = [float(value) for value in values]
    elapsed = len(values) - 1
    costs = -sum(value / (1 + finance_rate) ** index
                 for index, value in enumerate(values) if value < 0)
    proceeds = sum(value * (1 + reinvest_rate) ** (elapsed - index)
                   for index, value in enumerate(values) if value > 0)
    return (proceeds / costs) ** (1 / elapsed) - 1 if costs and proceeds else None


VERIFIED_FUNCTIONS = {
    'CEIL': ceil,
    'DATETIMEPARSE': datetime_parse,
    'DATETIMETRIM': datetime_trim,
    'ENDSWITH': ends_with,
    'FINANCEMIRR': finance_mirr,
    'FINANCEPMT': finance_pmt,
    'FINDSTRING': find_string,
    'FLOOR': floor,
    'GETWORD': get_word,
    'MD5_ASCII': md5_ascii,
    'REGEX_COUNTMATCHES': regex_count_matches,
    'ROUND': round_multiple,
    'SUBSTRING': substring,
}
