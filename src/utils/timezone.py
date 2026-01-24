"""
Miss Minutes - Timezone Utilities
"""
from datetime import datetime, time
from typing import Optional, Tuple
import pytz
import re
import logging

logger = logging.getLogger(__name__)

# Common timezone aliases
TIMEZONE_ALIASES = {
    # US
    "est": "America/New_York",
    "edt": "America/New_York",
    "eastern": "America/New_York",
    "us/eastern": "America/New_York",
    "cst": "America/Chicago",
    "cdt": "America/Chicago",
    "central": "America/Chicago",
    "us/central": "America/Chicago",
    "mst": "America/Denver",
    "mdt": "America/Denver",
    "mountain": "America/Denver",
    "us/mountain": "America/Denver",
    "pst": "America/Los_Angeles",
    "pdt": "America/Los_Angeles",
    "pacific": "America/Los_Angeles",
    "us/pacific": "America/Los_Angeles",
    # Other
    "utc": "UTC",
    "gmt": "Europe/London",
    "ist": "Asia/Kolkata",
    "cet": "Europe/Paris",
}


def parse_timezone(tz_str: str) -> Optional[str]:
    """
    Parse timezone string to valid pytz timezone.
    Returns None if invalid.
    """
    tz_lower = tz_str.lower().strip()
    
    # Check aliases first
    if tz_lower in TIMEZONE_ALIASES:
        return TIMEZONE_ALIASES[tz_lower]
    
    # Try direct match
    try:
        pytz.timezone(tz_str)
        return tz_str
    except pytz.exceptions.UnknownTimeZoneError:
        pass
    
    # Try common variations
    variations = [
        tz_str,
        tz_str.replace(" ", "_"),
        tz_str.title(),
        tz_str.replace(" ", "_").title(),
    ]
    
    for tz in variations:
        try:
            pytz.timezone(tz)
            return tz
        except pytz.exceptions.UnknownTimeZoneError:
            continue
    
    return None


def parse_time(time_str: str) -> Optional[str]:
    """
    Parse time string to HH:MM format.
    Supports: "4:30pm", "16:30", "4pm", "4:30 PM"
    Returns None if invalid.
    """
    time_str = time_str.lower().strip()
    
    # Try HH:MM format
    match = re.match(r'^(\d{1,2}):(\d{2})$', time_str)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    
    # Try H:MM AM/PM format
    match = re.match(r'^(\d{1,2}):(\d{2})\s*(am|pm)$', time_str)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        period = match.group(3)
        
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    
    # Try H AM/PM format (no minutes)
    match = re.match(r'^(\d{1,2})\s*(am|pm)$', time_str)
    if match:
        hour = int(match.group(1))
        period = match.group(2)
        
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"
    
    return None


def format_time_12h(time_24h: str) -> str:
    """Convert HH:MM to 12-hour format with AM/PM"""
    try:
        hour, minute = map(int, time_24h.split(":"))
        period = "AM" if hour < 12 else "PM"
        hour_12 = hour % 12
        if hour_12 == 0:
            hour_12 = 12
        return f"{hour_12}:{minute:02d} {period}"
    except:
        return time_24h


def get_current_time_in_timezone(timezone: str) -> datetime:
    """Get current time in specified timezone"""
    tz = pytz.timezone(timezone)
    return datetime.now(tz)


def is_time_match(target_time: str, timezone: str, tolerance_minutes: int = 7) -> bool:
    """
    Check if current time in timezone matches target time (within tolerance).
    
    Args:
        target_time: HH:MM format
        timezone: Timezone string
        tolerance_minutes: Minutes before/after to still match
    
    Returns:
        True if current time is within tolerance of target
    """
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        
        target_hour, target_minute = map(int, target_time.split(":"))
        target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        
        diff_seconds = abs((now - target).total_seconds())
        return diff_seconds <= tolerance_minutes * 60
        
    except Exception as e:
        logger.error(f"Error checking time match: {e}")
        return False


def is_day_match(target_day: str, timezone: str) -> bool:
    """Check if current day in timezone matches target day"""
    day_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        target_weekday = day_map.get(target_day.lower())
        
        if target_weekday is None:
            return False
        
        return now.weekday() == target_weekday
        
    except Exception as e:
        logger.error(f"Error checking day match: {e}")
        return False


def parse_snooze_duration(text: str) -> Optional[int]:
    """
    Parse snooze duration from text.
    Returns minutes or None if invalid.
    
    Supports: "1 hour", "30 minutes", "30 min", "2 hours"
    """
    text = text.lower().strip()
    
    # Try hours
    match = re.match(r'(\d+)\s*(?:hour|hr|h)s?', text)
    if match:
        return int(match.group(1)) * 60
    
    # Try minutes
    match = re.match(r'(\d+)\s*(?:minute|min|m)s?', text)
    if match:
        return int(match.group(1))
    
    return None
