"""Schedule parsing and retention-tier selection."""

import datetime
import json

def _field_matches_value(pattern: str, current: int) -> bool:
    """Check if a systemd calendar field pattern matches a value."""
    pattern = str(pattern).strip()
    if pattern == "*":
        return True

    # Range: A..B
    if ".." in pattern:
        parts = pattern.split("..")
        try:
            a, b = int(parts[0]), int(parts[1])
            return a <= current <= b
        except (ValueError, IndexError):
            return False

    # Step: A/N
    if "/" in pattern:
        parts = pattern.split("/")
        try:
            start, step = int(parts[0]), int(parts[1])
            if step <= 0:
                return False
            return current >= start and (current - start) % step == 0
        except (ValueError, IndexError):
            return False

    # Comma list: A,B,C
    if "," in pattern:
        try:
            values = [int(v.strip()) for v in pattern.split(",")]
            return current in values
        except ValueError:
            return False

    # Single value — exact match
    try:
        return current == int(pattern)
    except ValueError:
        return False


def _interval_matches_time(interval: dict, now: datetime.datetime) -> bool:
    """Check if a schedule interval matches the current time."""
    minute_val = interval.get("minute", {}).get("value", "*")
    if not _field_matches_value(minute_val, now.minute):
        return False

    hour_val = interval.get("hour", {}).get("value", "*")
    if not _field_matches_value(hour_val, now.hour):
        return False

    day_val = interval.get("day", {}).get("value", "*")
    if not _field_matches_value(day_val, now.day):
        return False

    month_val = interval.get("month", {}).get("value", "*")
    if not _field_matches_value(month_val, now.month):
        return False

    year_val = interval.get("year", {}).get("value", "*")
    if not _field_matches_value(year_val, now.year):
        return False

    dow = interval.get("dayOfWeek", [])
    if dow:
        # Python weekday(): Mon=0 .. Sun=6
        dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        current_dow = dow_names[now.weekday()]
        # Normalize incoming DOW entries to 3-char Title case
        normalized_dow = [str(d).strip()[:3].title() for d in dow]
        if current_dow not in normalized_dow:
            return False

    return True


def _count_specificity(interval: dict) -> int:
    """Count non-wildcard fields. Higher = more specific."""
    count = 0
    for field in ("minute", "hour", "day", "month", "year"):
        val = str(interval.get(field, {}).get("value", "*")).strip()
        if val != "*":
            count += 1
    if interval.get("dayOfWeek", []):
        count += 1
    return count


def match_current_tier(intervals: list, now: datetime.datetime) -> int:
    """
    Given schedule intervals and current time, return the index of the most
    specific matching interval.  Falls back to 0 if nothing matches.
    """
    matched = []
    for idx, interval in enumerate(intervals):
        if _interval_matches_time(interval, now):
            specificity = _count_specificity(interval)
            matched.append((idx, specificity))

    if not matched:
        return 0  # fallback to first interval

    # Most specific wins; on tie, prefer the lower index (more general / higher-priority)
    matched.sort(key=lambda x: (x[1], -x[0]), reverse=True)
    return matched[0][0]


def load_schedule_json(path: str):
    """Load the schedule JSON file. Returns the parsed dict or None."""
    if not path:
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: could not read schedule JSON at {path}: {e}")
        return None

