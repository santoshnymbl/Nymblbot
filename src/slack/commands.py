"""
Miss Minutes - Slack Command Handlers
Parse and handle user commands
"""
import re
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta

from src.models import (
    get_user,
    update_user,
    acknowledge_reminder,
    snooze_reminder
)
from src.utils import (
    parse_timezone,
    parse_time,
    format_time_12h,
    parse_snooze_duration,
    get_current_time_in_timezone
)
from src.config import (
    get_status_message,
    get_help_message,
    settings
)

logger = logging.getLogger(__name__)


async def handle_command(text: str, user_id: str, user_name: str) -> Optional[dict]:
    """
    Parse and handle commands. Returns Slack message dict or None if not a command.
    
    Commands:
    - subscribe / unsubscribe
    - status
    - help
    - set timezone <tz>
    - set reminder <time>
    - done
    - snooze <duration>
    """
    text_lower = text.lower().strip()
    
    # Subscribe
    if text_lower in ["subscribe", "opt in", "opt-in", "yes", "start reminders"]:
        return await handle_subscribe(user_id)
    
    # Unsubscribe
    if text_lower in ["unsubscribe", "opt out", "opt-out", "stop", "stop reminders"]:
        return await handle_unsubscribe(user_id)
    
    # Status
    if text_lower in ["status", "settings", "my settings", "preferences"]:
        return await handle_status(user_id, user_name)
    
    # Help
    if text_lower in ["help", "commands", "?"]:
        return get_help_message()
    
    # Done (acknowledge reminder)
    if text_lower in ["done", "logged", "finished", "complete", "dismiss"]:
        return await handle_done(user_id)
    
    # Snooze
    if text_lower.startswith("snooze"):
        duration_text = text_lower.replace("snooze", "").strip()
        return await handle_snooze(user_id, duration_text)
    
    # Set timezone
    match = re.match(r'^set\s+timezone\s+(.+)$', text_lower)
    if match:
        tz_input = match.group(1).strip()
        return await handle_set_timezone(user_id, user_name, tz_input)
    
    # Set reminder time
    match = re.match(r'^set\s+reminder(?:\s+time)?\s+(.+)$', text_lower)
    if match:
        time_input = match.group(1).strip()
        return await handle_set_reminder_time(user_id, user_name, time_input)
    
    # Not a command
    return None


async def handle_subscribe(user_id: str) -> dict:
    """Handle subscribe command"""
    user = await get_user(user_id)
    
    if user and user.subscribed:
        return {
            "text": "✅ You're already subscribed to Friday reminders! Say `status` to see your settings."
        }
    
    await update_user(user_id, subscribed=True)
    
    return {
        "text": "✅ *Subscribed!* You'll get Friday reminders to log your time.\n\n💡 Say `status` to see your settings or `set timezone US/Pacific` to change your timezone."
    }


async def handle_unsubscribe(user_id: str) -> dict:
    """Handle unsubscribe command"""
    user = await get_user(user_id)
    
    if user and not user.subscribed:
        return {
            "text": "You're already unsubscribed from reminders. Say `subscribe` anytime to opt back in!"
        }
    
    await update_user(user_id, subscribed=False)
    
    return {
        "text": "✅ *Unsubscribed.* You won't receive Friday reminders anymore.\n\nYou can still ask me questions anytime! Say `subscribe` to opt back in."
    }


async def handle_status(user_id: str, user_name: str) -> dict:
    """Handle status command"""
    user = await get_user(user_id)
    
    if not user:
        return {
            "text": "I don't have any settings for you yet! Say `subscribe` to get started with Friday reminders."
        }
    
    return get_status_message(
        user_name=user.user_name or user_name,
        subscribed=user.subscribed,
        timezone=user.timezone,
        reminder_time=format_time_12h(user.reminder_time)
    )


async def handle_done(user_id: str) -> dict:
    """Handle done/acknowledge command"""
    await acknowledge_reminder(user_id)
    
    return {
        "text": "✅ Great job logging your time! Have a wonderful weekend! 🎉"
    }


async def handle_snooze(user_id: str, duration_text: str) -> dict:
    """Handle snooze command"""
    # Default to 1 hour if no duration specified
    if not duration_text:
        duration_text = "1 hour"
    
    minutes = parse_snooze_duration(duration_text)
    
    if minutes is None:
        return {
            "text": "❌ I didn't understand that duration. Try: `snooze 1 hour` or `snooze 30 minutes`"
        }
    
    if minutes > 240:  # Max 4 hours
        return {
            "text": "❌ Maximum snooze is 4 hours. Try: `snooze 1 hour` or `snooze 2 hours`"
        }
    
    # Get user's timezone for accurate snooze
    user = await get_user(user_id)
    tz = user.timezone if user else settings.default_timezone
    
    snooze_until = get_current_time_in_timezone(tz) + timedelta(minutes=minutes)
    await snooze_reminder(user_id, snooze_until)
    
    if minutes >= 60:
        duration_str = f"{minutes // 60} hour{'s' if minutes >= 120 else ''}"
    else:
        duration_str = f"{minutes} minutes"
    
    return {
        "text": f"⏰ Snoozed for {duration_str}. I'll remind you again later!"
    }


async def handle_set_timezone(user_id: str, user_name: str, tz_input: str) -> dict:
    """Handle set timezone command"""
    parsed_tz = parse_timezone(tz_input)
    
    if not parsed_tz:
        return {
            "text": f"❌ I don't recognize `{tz_input}` as a timezone.\n\nTry one of these:\n• `US/Eastern`, `US/Pacific`, `US/Central`\n• `EST`, `PST`, `CST`\n• `Europe/London`, `Asia/Tokyo`"
        }
    
    await update_user(user_id, timezone=parsed_tz)
    
    # Show current time in new timezone
    now = get_current_time_in_timezone(parsed_tz)
    current_time = now.strftime("%I:%M %p")
    
    return {
        "text": f"✅ Timezone updated to *{parsed_tz}*\n\nYour current time: {current_time}\n\nReminders will be sent based on this timezone."
    }


async def handle_set_reminder_time(user_id: str, user_name: str, time_input: str) -> dict:
    """Handle set reminder time command"""
    parsed_time = parse_time(time_input)
    
    if not parsed_time:
        return {
            "text": f"❌ I didn't understand `{time_input}` as a time.\n\nTry one of these formats:\n• `4:30pm` or `4:30 PM`\n• `16:30`\n• `5pm`"
        }
    
    await update_user(user_id, reminder_time=parsed_time)
    
    return {
        "text": f"✅ Reminder time updated to *{format_time_12h(parsed_time)}*\n\nYou'll get reminders at this time on Fridays (in your timezone)."
    }
