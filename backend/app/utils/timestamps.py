# timestamps.py
#
# Parsing Postgres/Supabase timestamptz strings into Python datetimes,
# safely across Python versions.
#
# WHY THIS FILE EXISTS:
# Postgres stores microsecond precision but STRIPS TRAILING ZEROS when
# serializing to JSON. A stored value of .421080 comes back over the REST
# API as ".42108" — five fractional digits.
#
# Python 3.10 and earlier: datetime.fromisoformat() accepts ONLY exactly
#   3 or 6 fractional digits. Five digits raises:
#       ValueError: Invalid isoformat string: '2026-07-14T21:42:55.42108+00:00'
# Python 3.11+: fromisoformat() was relaxed and accepts any precision.
#
# This makes the bug VERSION-DEPENDENT and INTERMITTENT: it only fires when
# a timestamp's microseconds happen to end in a zero (roughly 1 in 10 rows),
# and only on older runtimes. That combination makes it easy to misdiagnose
# as random corruption.
#
# The fix is to normalize the fractional part to exactly 6 digits before
# parsing, which is valid on every Python version. Do not call
# datetime.fromisoformat() directly on Supabase values anywhere in this
# codebase; call parse_pg_timestamp() instead.

import re
from datetime import datetime, timezone

# Splits an ISO-ish timestamp into (head, fractional_digits, tail).
# head = "2026-07-14T21:42:55", frac = "42108", tail = "+00:00"
_TS_PARTS = re.compile(r"^(.*?T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(.*)$")

# Fallback formats for shapes fromisoformat still rejects after normalizing.
_FALLBACK_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
)


def parse_pg_timestamp(value) -> datetime:
    """
    Parses a Postgres timestamptz value into a timezone-aware datetime.

    Tolerates:
        - any fractional-second precision (0 to 9+ digits)
        - "Z" or "+00:00" timezone suffixes
        - missing timezone (assumed UTC)
        - values already parsed into datetime objects
        - None, empty, or malformed input (falls back to now(), never raises)

    Always returns a timezone-aware datetime. Never raises, because a bad
    timestamp on one chunk must not crash retrieval for a whole query.

    Args:
        value: Raw value from a Supabase row, usually a str.

    Returns:
        Timezone-aware datetime.
    """
    # Already a datetime: just ensure it is timezone-aware.
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if not value:
        return datetime.now(timezone.utc)

    s = str(value).strip().replace("Z", "+00:00")

    # Normalize fractional seconds to exactly 6 digits, which is the only
    # form (besides none at all) that every Python version accepts.
    match = _TS_PARTS.match(s)
    if match:
        head, frac, tail = match.group(1), match.group(2), match.group(3) or ""
        if frac is not None:
            frac = (frac + "000000")[:6]   # pad short values, truncate long ones
            s = f"{head}.{frac}{tail}"
        else:
            s = f"{head}{tail}"

    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        for fmt in _FALLBACK_FORMATS:
            try:
                dt = datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
        else:
            # Unparseable. Return now() rather than raising: a single bad
            # timestamp should degrade that chunk's staleness accuracy,
            # not fail the user's entire query.
            return datetime.now(timezone.utc)

    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)