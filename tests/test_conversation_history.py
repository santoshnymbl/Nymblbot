"""Tests for conversation history storage"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

# Patch DB_PATH before importing database module
_temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_temp_db_path = Path(_temp_db.name)
_temp_db.close()


@pytest.fixture(autouse=True)
def patch_db_path():
    with patch("src.models.database.DB_PATH", _temp_db_path):
        yield
    # Clean up between tests
    if _temp_db_path.exists():
        _temp_db_path.unlink()


class TestConversationHistory:
    @pytest.mark.asyncio
    async def test_save_and_get_history(self, patch_db_path):
        from src.models.database import init_database, save_conversation_message, get_conversation_history

        await init_database()
        await save_conversation_message("U123", "user", "What is PTO?")
        await save_conversation_message("U123", "assistant", "PTO stands for Paid Time Off.")

        history = await get_conversation_history("U123")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_history_limited_to_5_exchanges(self, patch_db_path):
        from src.models.database import init_database, save_conversation_message, get_conversation_history

        await init_database()
        # Save 7 exchanges (14 messages)
        for i in range(7):
            await save_conversation_message("U123", "user", f"Question {i}")
            await save_conversation_message("U123", "assistant", f"Answer {i}")

        history = await get_conversation_history("U123", max_exchanges=5)
        assert len(history) == 10  # 5 exchanges = 10 messages
        # Should be the most recent 5 exchanges
        assert history[0]["content"] == "Question 2"

    @pytest.mark.asyncio
    async def test_history_excludes_old_messages(self, patch_db_path):
        from src.models.database import init_database, save_conversation_message, get_conversation_history

        await init_database()
        await save_conversation_message("U123", "user", "Old question")

        # History with 0-hour max age should return nothing
        history = await get_conversation_history("U123", max_age_hours=0)
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_history_per_user(self, patch_db_path):
        from src.models.database import init_database, save_conversation_message, get_conversation_history

        await init_database()
        await save_conversation_message("U123", "user", "User 1 question")
        await save_conversation_message("U456", "user", "User 2 question")

        history_1 = await get_conversation_history("U123")
        history_2 = await get_conversation_history("U456")
        assert len(history_1) == 1
        assert len(history_2) == 1
        assert history_1[0]["content"] == "User 1 question"
