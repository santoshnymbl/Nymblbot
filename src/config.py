"""
NymblBot - Configuration
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional

# Get the project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent


class Settings(BaseSettings):
    # Slack Configuration
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    
    # Anthropic Claude API
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    
    # MyNos Configuration
    mynos_url: str = "https://mynos.example.com"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 3000
    debug: bool = False
    
    # Database - use absolute path
    database_url: str = f"sqlite+aiosqlite:///{PROJECT_ROOT}/db/miss_minutes.db"
    
    # RAG Configuration - use absolute path
    data_dir: str = str(PROJECT_ROOT / "data")
    chunk_size: int = 500
    chunk_overlap: int = 50
    bm25_top_k: int = 20
    rerank_top_k: int = 5
    
    # Default reminder settings
    default_timezone: str = "America/New_York"
    default_reminder_time: str = "16:30"
    default_reminder_day: str = "friday"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


# =============================================================================
# Nymbling PERSONALITY
# =============================================================================

SYSTEM_PROMPT = """You are a Nymbling, Nymbl's friendly AI assistant! 🕐

## Your Personality
- Warm, helpful, and encouraging (embody Nymbl's "Be Empowering" tenet)
- Use Nymbl terminology naturally (WGLL, tenets, Solution Architects, etc.)
- Keep responses concise but thorough
- Add a touch of friendliness without being over-the-top
- When you don't know something, admit it honestly and suggest who might help

## Your Knowledge
- Nymbl's history, values, and tenets
- Leadership team and their roles  
- Company processes (time logging, PTO, feedback)
- Nymbl terminology and acronyms
- How Nymbl works (tools, meetings, events)

## Response Guidelines
- Start with a brief, direct answer
- Add helpful context if relevant
- Use bullet points sparingly, only when listing multiple items
- Keep responses under 300 words unless the question requires more detail
- End with a follow-up offer if appropriate ("Need more details?")

## Important
- You're a helpful colleague, not a formal corporate bot
- Be natural and conversational
- If asked about something not in your knowledge base, say so honestly
"""


# =============================================================================
# SLACK MESSAGE TEMPLATES
# =============================================================================

def get_welcome_message(user_name: str) -> dict:
    """First-time user welcome message with onboarding"""
    return {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"👋 *Hey {user_name}!* I'm Nymbling, Nymbl's AI assistant.\n\nI can help you with:"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "• 📚 *Answer questions* about Nymbl (policies, processes, people)\n• ⏰ *Remind you* to log time on Fridays"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Want me to send you Friday reminders to log your time?*"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Yes, subscribe", "emoji": True},
                        "style": "primary",
                        "action_id": "subscribe_reminder",
                        "value": "subscribe"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ No thanks", "emoji": True},
                        "action_id": "decline_reminder",
                        "value": "decline"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "⚙️ Customize", "emoji": True},
                        "action_id": "customize_reminder",
                        "value": "customize"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "💡 You can always change this later by saying `subscribe` or `unsubscribe`"
                    }
                ]
            }
        ]
    }


def get_reminder_message(user_name: str, mynos_url: str) -> dict:
    """Friday time logging reminder"""
    return {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"⏰ *Hey {user_name}!* Nymbling here.\n\nIt's Friday – time to log your hours! Being Reliable means keeping our time tracking accurate. 💪"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "📝 Log Time on MyNos", "emoji": True},
                        "style": "primary",
                        "url": mynos_url,
                        "action_id": "open_mynos"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "💡 Say `done` to dismiss • `snooze 1 hour` to delay • `unsubscribe` to stop reminders"
                    }
                ]
            }
        ]
    }


def get_status_message(user_name: str, subscribed: bool, timezone: str, reminder_time: str) -> dict:
    """User status/preferences message"""
    status = "✅ Subscribed" if subscribed else "❌ Not subscribed"
    return {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🕐 Your Nymbling Settings*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Reminders:*\n{status}"},
                    {"type": "mrkdwn", "text": f"*Time:*\nFridays at {reminder_time}"},
                    {"type": "mrkdwn", "text": f"*Timezone:*\n{timezone}"},
                    {"type": "mrkdwn", "text": f"*Name:*\n{user_name}"}
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "💡 Commands: `subscribe` • `unsubscribe` • `set timezone US/Pacific` • `set reminder 5pm`"
                    }
                ]
            }
        ]
    }


def get_help_message() -> dict:
    """Help message with all commands"""
    return {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🕐 Nymbling Help*\n\nHere's what I can do:"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*📚 Ask Questions*\nJust type any question about Nymbl!\n_Example: \"What is WGLL?\" or \"How do I submit PTO?\"_"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*⏰ Reminder Commands*\n• `subscribe` - Get Friday reminders\n• `unsubscribe` - Stop reminders\n• `snooze 1 hour` - Delay current reminder\n• `done` - Dismiss reminder"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*⚙️ Settings*\n• `status` - View your settings\n• `set timezone US/Pacific` - Change timezone\n• `set reminder 5pm` - Change reminder time"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Nymbling | Nymbl's AI Assistant"
                    }
                ]
            }
        ]
    }
