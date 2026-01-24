"""
Miss Minutes - Reminder Scheduler
Per-user personalized reminders with timezone support
"""
import logging
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from slack_sdk.web.async_client import AsyncWebClient

from src.config import settings, get_reminder_message
from src.models import (
    get_subscribed_users,
    log_reminder_sent,
    check_reminder_sent_today
)
from src.utils import is_time_match, is_day_match, get_current_time_in_timezone

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """
    Handles personalized reminders for all subscribed users.
    
    Strategy: Single cron job runs every 15 minutes on reminder days,
    checks each user's timezone and sends if time matches.
    """
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.slack_client: AsyncWebClient = None
        self._running = False
    
    def initialize(self, slack_client: AsyncWebClient):
        """Initialize scheduler with Slack client"""
        self.slack_client = slack_client
        
        # Run every 15 minutes, every day
        # We check the day inside the job based on user preferences
        self.scheduler.add_job(
            self.check_and_send_reminders,
            CronTrigger(minute="*/15"),  # Every 15 minutes
            id="reminder_check",
            name="Check and Send Reminders",
            replace_existing=True
        )
        
        logger.info("Reminder scheduler initialized (checks every 15 minutes)")
    
    def start(self):
        """Start the scheduler"""
        if not self._running:
            self.scheduler.start()
            self._running = True
            logger.info("Reminder scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        if self._running:
            self.scheduler.shutdown()
            self._running = False
            logger.info("Reminder scheduler stopped")
    
    async def check_and_send_reminders(self):
        """
        Check all subscribed users and send reminders if conditions match:
        1. It's the user's reminder day (in their timezone)
        2. Current time matches their reminder time (±7 min tolerance)
        3. Reminder hasn't been sent today
        """
        logger.debug("Running reminder check...")
        
        try:
            # Get all subscribed users
            users = await get_subscribed_users()
            
            if not users:
                logger.debug("No subscribed users")
                return
            
            sent_count = 0
            
            for user in users:
                try:
                    # Check if it's the right day
                    if not is_day_match(user.reminder_day, user.timezone):
                        continue
                    
                    # Check if it's the right time (±7 min)
                    if not is_time_match(user.reminder_time, user.timezone, tolerance_minutes=7):
                        continue
                    
                    # Check if already sent today
                    user_now = get_current_time_in_timezone(user.timezone)
                    if await check_reminder_sent_today(user.user_id, user_now.date()):
                        continue
                    
                    # Send reminder!
                    await self.send_reminder_to_user(user.user_id, user.user_name)
                    sent_count += 1
                    
                except Exception as e:
                    logger.error(f"Error checking user {user.user_id}: {e}")
            
            if sent_count > 0:
                logger.info(f"Sent {sent_count} reminders")
                
        except Exception as e:
            logger.error(f"Error in reminder check: {e}")
    
    async def send_reminder_to_user(self, user_id: str, user_name: str):
        """Send reminder DM to a specific user"""
        if not self.slack_client:
            logger.error("Slack client not initialized")
            return False
        
        try:
            # Open DM channel
            response = await self.slack_client.conversations_open(users=[user_id])
            channel_id = response["channel"]["id"]
            
            # Build message
            message = get_reminder_message(user_name, settings.mynos_url)
            
            # Send
            await self.slack_client.chat_postMessage(
                channel=channel_id,
                blocks=message["blocks"],
                text=f"⏰ Hey {user_name}! Time to log your hours on MyNos!"
            )
            
            # Log it
            await log_reminder_sent(user_id)
            
            logger.info(f"Sent reminder to {user_name} ({user_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send reminder to {user_id}: {e}")
            return False
    
    async def send_test_reminder(self, user_id: str, user_name: str):
        """Send a test reminder (bypasses time/day checks)"""
        return await self.send_reminder_to_user(user_id, user_name)
    
    def get_next_run(self) -> str:
        """Get next scheduled check time"""
        job = self.scheduler.get_job("reminder_check")
        if job and job.next_run_time:
            return job.next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        return "Not scheduled"


# Global instance
reminder_scheduler = ReminderScheduler()
