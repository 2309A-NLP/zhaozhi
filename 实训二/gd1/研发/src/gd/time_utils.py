from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# 固定使用北京时间，避免 agent 误解“今天/昨天/本周”
BEIJING_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")


@dataclass(frozen=True)
class BeijingTimeContext:
    # 给 agent 使用的北京时间上下文
    iso_datetime: str
    date: str
    time: str
    timezone_name: str


def get_beijing_time_context() -> BeijingTimeContext:
    # 获取当前北京时间，并拆成多个字段方便注入 prompt
    now = datetime.now(BEIJING_TIMEZONE)
    return BeijingTimeContext(
        iso_datetime=now.strftime("%Y-%m-%d %H:%M:%S"),
        date=now.strftime("%Y-%m-%d"),
        time=now.strftime("%H:%M:%S"),
        timezone_name="Asia/Shanghai",
    )
