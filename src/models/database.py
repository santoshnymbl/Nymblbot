"""
Miss Minutes - Database Models and Queries
SQLite with async support
"""
import aiosqlite
import os
from pathlib import Path
from datetime import datetime, date
from typing import Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Database path - relative to project root (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "db" / "miss_minutes.db"


@dataclass
class UserPreference:
    """User preferences model"""
    user_id: str
    user_name: str
    subscribed: bool = True
    timezone: str = "America/New_York"
    reminder_time: str = "16:30"
    reminder_day: str = "friday"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Interaction:
    """Interaction log model"""
    id: Optional[int]
    user_id: str
    query: str
    response: str
    latency_ms: int
    feedback: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass 
class ReminderLog:
    """Reminder sent log"""
    id: Optional[int]
    user_id: str
    sent_at: datetime
    acknowledged: bool = False
    snoozed_until: Optional[datetime] = None


async def init_database():
    """Initialize database with tables"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        # User preferences table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                user_name TEXT,
                subscribed BOOLEAN DEFAULT 1,
                timezone TEXT DEFAULT 'America/New_York',
                reminder_time TEXT DEFAULT '16:30',
                reminder_day TEXT DEFAULT 'friday',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Interactions log table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                query TEXT,
                response TEXT,
                latency_ms INTEGER,
                feedback TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Reminder log table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminder_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                sent_at TIMESTAMP,
                acknowledged BOOLEAN DEFAULT 0,
                snoozed_until TIMESTAMP
            )
        """)
        
        # Create indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_interactions_user ON interactions(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_reminder_log_user ON reminder_log(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_reminder_log_sent ON reminder_log(sent_at)")
        
        await db.commit()
        logger.info("Database initialized successfully")


# =============================================================================
# USER PREFERENCES QUERIES
# =============================================================================

async def get_user(user_id: str) -> Optional[UserPreference]:
    """Get user preferences by ID"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_preferences WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return UserPreference(
                    user_id=row["user_id"],
                    user_name=row["user_name"],
                    subscribed=bool(row["subscribed"]),
                    timezone=row["timezone"],
                    reminder_time=row["reminder_time"],
                    reminder_day=row["reminder_day"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"]
                )
            return None


async def create_user(user: UserPreference) -> UserPreference:
    """Create new user preferences"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("""
            INSERT INTO user_preferences (user_id, user_name, subscribed, timezone, reminder_time, reminder_day)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user.user_id, user.user_name, user.subscribed, user.timezone, user.reminder_time, user.reminder_day))
        await db.commit()
        logger.info(f"Created user: {user.user_id}")
        return user


async def update_user(user_id: str, **kwargs) -> Optional[UserPreference]:
    """Update user preferences"""
    if not kwargs:
        return await get_user(user_id)
    
    set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [user_id]
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(f"""
            UPDATE user_preferences 
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, values)
        await db.commit()
        logger.info(f"Updated user {user_id}: {kwargs}")
        
    return await get_user(user_id)


async def get_or_create_user(user_id: str, user_name: str) -> tuple[UserPreference, bool]:
    """Get existing user or create new one. Returns (user, is_new)"""
    user = await get_user(user_id)
    if user:
        # Update name if changed
        if user.user_name != user_name:
            await update_user(user_id, user_name=user_name)
            user.user_name = user_name
        return user, False
    
    # Create new user
    new_user = UserPreference(
        user_id=user_id,
        user_name=user_name,
        subscribed=False  # Default to not subscribed, let them opt-in
    )
    await create_user(new_user)
    return new_user, True


async def get_subscribed_users() -> List[UserPreference]:
    """Get all users subscribed to reminders"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_preferences WHERE subscribed = 1"
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                UserPreference(
                    user_id=row["user_id"],
                    user_name=row["user_name"],
                    subscribed=bool(row["subscribed"]),
                    timezone=row["timezone"],
                    reminder_time=row["reminder_time"],
                    reminder_day=row["reminder_day"]
                )
                for row in rows
            ]


# =============================================================================
# INTERACTION LOG QUERIES  
# =============================================================================

async def log_interaction(user_id: str, query: str, response: str, latency_ms: int):
    """Log an interaction"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("""
            INSERT INTO interactions (user_id, query, response, latency_ms)
            VALUES (?, ?, ?, ?)
        """, (user_id, query, response, latency_ms))
        await db.commit()


async def update_feedback(interaction_id: int, feedback: str):
    """Update feedback for an interaction"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            "UPDATE interactions SET feedback = ? WHERE id = ?",
            (feedback, interaction_id)
        )
        await db.commit()


# =============================================================================
# REMINDER LOG QUERIES
# =============================================================================

async def log_reminder_sent(user_id: str) -> int:
    """Log that a reminder was sent"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute("""
            INSERT INTO reminder_log (user_id, sent_at)
            VALUES (?, CURRENT_TIMESTAMP)
        """, (user_id,))
        await db.commit()
        return cursor.lastrowid


async def check_reminder_sent_today(user_id: str, user_date: date) -> bool:
    """Check if reminder was already sent to user today (in their timezone)"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        async with db.execute("""
            SELECT COUNT(*) FROM reminder_log 
            WHERE user_id = ? AND DATE(sent_at) = ?
        """, (user_id, user_date.isoformat())) as cursor:
            row = await cursor.fetchone()
            return row[0] > 0


async def acknowledge_reminder(user_id: str):
    """Mark most recent reminder as acknowledged"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("""
            UPDATE reminder_log 
            SET acknowledged = 1 
            WHERE user_id = ? 
            ORDER BY sent_at DESC 
            LIMIT 1
        """, (user_id,))
        await db.commit()


async def snooze_reminder(user_id: str, snooze_until: datetime):
    """Snooze the most recent reminder"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("""
            UPDATE reminder_log 
            SET snoozed_until = ? 
            WHERE user_id = ? 
            ORDER BY sent_at DESC 
            LIMIT 1
        """, (snooze_until, user_id))
        await db.commit()


# =============================================================================
# STATS QUERIES
# =============================================================================

async def get_stats() -> dict:
    """Get bot statistics"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        # Total users
        async with db.execute("SELECT COUNT(*) FROM user_preferences") as cursor:
            total_users = (await cursor.fetchone())[0]
        
        # Subscribed users
        async with db.execute("SELECT COUNT(*) FROM user_preferences WHERE subscribed = 1") as cursor:
            subscribed_users = (await cursor.fetchone())[0]
        
        # Total interactions
        async with db.execute("SELECT COUNT(*) FROM interactions") as cursor:
            total_interactions = (await cursor.fetchone())[0]
        
        # Interactions today
        async with db.execute(
            "SELECT COUNT(*) FROM interactions WHERE DATE(created_at) = DATE('now')"
        ) as cursor:
            interactions_today = (await cursor.fetchone())[0]
        
        return {
            "total_users": total_users,
            "subscribed_users": subscribed_users,
            "total_interactions": total_interactions,
            "interactions_today": interactions_today
        }
