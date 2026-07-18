"""Local-date preset boundaries with Monday-based weeks."""

from datetime import date, timedelta
from enum import StrEnum


class DatePreset(StrEnum):
    TODAY = "today"
    LAST_7_DAYS = "last_7_days"
    THIS_WEEK = "this_week"
    LAST_WEEK = "last_week"
    LAST_30_DAYS = "last_30_days"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    THIS_YEAR = "this_year"
    CUSTOM = "custom"


def preset_range(preset: DatePreset, today: date) -> tuple[date, date]:
    if preset is DatePreset.TODAY:
        return today, today
    if preset is DatePreset.LAST_7_DAYS:
        return today - timedelta(days=6), today
    if preset is DatePreset.THIS_WEEK:
        return today - timedelta(days=today.weekday()), today
    if preset is DatePreset.LAST_WEEK:
        monday = today - timedelta(days=today.weekday())
        return monday - timedelta(days=7), monday - timedelta(days=1)
    if preset is DatePreset.LAST_30_DAYS:
        return today - timedelta(days=29), today
    if preset is DatePreset.THIS_MONTH:
        return today.replace(day=1), today
    if preset is DatePreset.LAST_MONTH:
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    if preset is DatePreset.THIS_YEAR:
        return today.replace(month=1, day=1), today
    return today, today
