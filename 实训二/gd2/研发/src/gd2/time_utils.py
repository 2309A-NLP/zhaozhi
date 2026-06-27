from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


BEIJING_TIMEZONE = "Asia/Shanghai"


def get_beijing_now() -> datetime:
    """Return the current Beijing time based on the host system clock."""

    try:
        return datetime.now(ZoneInfo(BEIJING_TIMEZONE))
    except ZoneInfoNotFoundError:
        return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))


def get_beijing_now_text() -> str:
    """Return the current Beijing time as a formatted string."""

    return get_beijing_now().strftime("%Y-%m-%d %H:%M:%S")
