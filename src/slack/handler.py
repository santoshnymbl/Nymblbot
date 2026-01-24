"""
Miss Minutes - Slack Event Handler
Process DMs, mentions, and interactions
"""
import re
import logging
import time
from typing import Optional

from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from src.config import settings, get_welcome_message, get_help_message
from src.models import get_or_create_user, log_interaction, get_stats
from src.ai import ai_generator, get_quick_response
from src.slack.commands import handle_command

logger = logging.getLogger(__name__)


def create_slack_app() -> AsyncApp:
    """Create and configure the Slack Bolt application"""
    
    app = AsyncApp(
        token=settings.slack_bot_token,
        signing_secret=settings.slack_signing_secret
    )
    
    # Cache bot user ID
    bot_user_id = None
    
    # =========================================================================
    # EVENT: App Mention (@Miss Minutes in channels)
    # =========================================================================
    @app.event("app_mention")
    async def handle_mention(event: dict, say, client: AsyncWebClient):
        """Handle @Miss Minutes mentions in channels"""
        nonlocal bot_user_id
        
        if not bot_user_id:
            auth = await client.auth_test()
            bot_user_id = auth["user_id"]
        
        user_id = event.get("user")
        text = event.get("text", "")
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        
        # Remove mention from text
        text = re.sub(f"<@{bot_user_id}>", "", text).strip()
        
        # Get user info
        user_name = await get_user_display_name(client, user_id)
        
        # Ensure user exists in DB
        user, is_new = await get_or_create_user(user_id, user_name)
        
        if not text:
            await say(text="Hey! What can I help you with? 🕐", thread_ts=thread_ts)
            return
        
        # Process the message
        await process_message(text, user_id, user_name, say, client, channel, thread_ts, event.get("ts"))
    
    # =========================================================================
    # EVENT: Direct Message
    # =========================================================================
    @app.event("message")
    async def handle_dm(event: dict, say, client: AsyncWebClient):
        """Handle direct messages to Miss Minutes"""
        
        # Ignore bot messages, edits, etc.
        if event.get("bot_id") or event.get("subtype"):
            return
        
        # Only respond to DMs
        if event.get("channel_type") != "im":
            return
        
        user_id = event.get("user")
        text = event.get("text", "").strip()
        thread_ts = event.get("thread_ts") or event.get("ts")
        channel = event.get("channel")
        
        if not text:
            return
        
        # Get user info
        user_name = await get_user_display_name(client, user_id)
        
        # Check if new user (for onboarding)
        user, is_new = await get_or_create_user(user_id, user_name)
        
        if is_new:
            # Send welcome message for first-time users
            welcome = get_welcome_message(user_name)
            await say(blocks=welcome["blocks"], text=f"Welcome {user_name}!")
            return
        
        # Process the message
        await process_message(text, user_id, user_name, say, client, channel, thread_ts, event.get("ts"))
    
    # =========================================================================
    # EVENT: App Home Opened
    # =========================================================================
    @app.event("app_home_opened")
    async def handle_app_home(event: dict, client: AsyncWebClient):
        """Update App Home tab"""
        user_id = event.get("user")
        
        # Get stats
        stats = await get_stats()
        
        await client.views_publish(
            user_id=user_id,
            view={
                "type": "home",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Welcome Nymbling!*\n\nI'm Nymbl's AI assistant. Here's what I can help with:"
                        }
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "📚 *Ask Questions*\nAsk about Nymbl policies, processes, people, and terminology."
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "⏰ *Time Reminders*\nGet personalized Friday reminders to log your time."
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*How to use:*\n• DM me directly with any question\n• Mention `@NymblBot` in any channel\n• Say `help` for all commands"
                        }
                    },
                    {"type": "divider"},
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"📊 Stats: {stats['total_users']} users | {stats['subscribed_users']} subscribed | {stats['total_interactions']} questions answered"
                            }
                        ]
                    }
                ]
            }
        )
    
    # =========================================================================
    # ACTIONS: Button Clicks
    # =========================================================================
    @app.action("subscribe_reminder")
    async def handle_subscribe_button(ack, body, say):
        """Handle subscribe button click"""
        await ack()
        user_id = body["user"]["id"]
        
        from src.models import update_user
        await update_user(user_id, subscribed=True)
        
        await say(text="✅ *Subscribed!* You'll get Friday reminders to log your time.\n\n💡 Say `status` to see your settings.")
    
    @app.action("decline_reminder")
    async def handle_decline_button(ack, body, say):
        """Handle decline button click"""
        await ack()
        await say(text="No problem! You can always say `subscribe` later if you change your mind.\n\nFeel free to ask me anything about Nymbl! 🕐")
    
    @app.action("customize_reminder")
    async def handle_customize_button(ack, body, say):
        """Handle customize button click"""
        await ack()
        await say(text="*Customize your reminders:*\n\n• `set timezone US/Pacific` - Change your timezone\n• `set reminder 5pm` - Change reminder time\n• `subscribe` - Turn on reminders\n\nWhat would you like to change?")
    
    @app.action("open_mynos")
    async def handle_mynos_button(ack):
        """Handle MyNos button click (just acknowledge, URL opens in browser)"""
        await ack()
    
    return app


async def process_message(
    text: str,
    user_id: str,
    user_name: str,
    say,
    client: AsyncWebClient,
    channel: str,
    thread_ts: str,
    message_ts: str
):
    """Process a user message (from DM or mention)"""
    
    # Check for commands first
    command_response = await handle_command(text, user_id, user_name)
    if command_response:
        if "blocks" in command_response:
            await say(blocks=command_response["blocks"], thread_ts=thread_ts)
        else:
            await say(text=command_response.get("text", ""), thread_ts=thread_ts)
        return
    
    # Check for quick responses
    quick = get_quick_response(text)
    if quick:
        await say(text=quick, thread_ts=thread_ts)
        return
    
    # Add thinking reaction
    try:
        await client.reactions_add(channel=channel, timestamp=message_ts, name="hourglass_flowing_sand")
    except:
        pass
    
    # Generate AI response
    response, latency_ms = await ai_generator.generate(text, user_name)
    
    # Remove thinking reaction
    try:
        await client.reactions_remove(channel=channel, timestamp=message_ts, name="hourglass_flowing_sand")
    except:
        pass
    
    # Send response
    await say(text=response, thread_ts=thread_ts)
    
    # Log interaction
    await log_interaction(user_id, text, response, latency_ms)


async def get_user_display_name(client: AsyncWebClient, user_id: str) -> str:
    """Get user's display name from Slack"""
    try:
        response = await client.users_info(user=user_id)
        user = response.get("user", {})
        return (
            user.get("profile", {}).get("display_name") or
            user.get("profile", {}).get("real_name") or
            user.get("name") or
            "there"
        )
    except Exception as e:
        logger.warning(f"Could not get user info: {e}")
        return "there"
