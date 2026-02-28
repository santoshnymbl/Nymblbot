"""Tests for AI generator with query expansion and conversation memory"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestGeneratorWithExpansion:
    @pytest.mark.asyncio
    async def test_generate_calls_expand_query(self):
        """Generator should call expand_query before RAG search"""
        with patch("src.ai.generator.expand_query", new_callable=AsyncMock) as mock_expand, \
             patch("src.ai.generator.rag_pipeline") as mock_rag, \
             patch("src.ai.generator.get_conversation_history", new_callable=AsyncMock) as mock_history, \
             patch("src.ai.generator.save_conversation_message", new_callable=AsyncMock):

            mock_expand.return_value = ["What is PTO?", "paid time off policy", "leave policy"]
            mock_rag.get_context_with_sources.return_value = ("PTO is 15 days.", [{"source": "wiki.md", "section_path": "Policies > PTO"}])
            mock_history.return_value = []

            from src.ai.generator import AIGenerator
            gen = AIGenerator()
            gen.client = MagicMock()
            gen._initialized = True

            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="You get 15 days PTO.")]
            gen.client.messages.create = AsyncMock(return_value=mock_response)

            response, latency, sources = await gen.generate("What is PTO?", "TestUser", "U123")

            mock_expand.assert_called_once()
            mock_rag.get_context_with_sources.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_returns_sources(self):
        """Generator should return source metadata along with response"""
        with patch("src.ai.generator.expand_query", new_callable=AsyncMock) as mock_expand, \
             patch("src.ai.generator.rag_pipeline") as mock_rag, \
             patch("src.ai.generator.get_conversation_history", new_callable=AsyncMock) as mock_history, \
             patch("src.ai.generator.save_conversation_message", new_callable=AsyncMock):

            mock_expand.return_value = ["What is PTO?"]
            mock_rag.get_context_with_sources.return_value = (
                "PTO is 15 days.",
                [{"source": "nymbl_wiki.md", "section_path": "Policies > PTO Policy"}]
            )
            mock_history.return_value = []

            from src.ai.generator import AIGenerator
            gen = AIGenerator()
            gen.client = MagicMock()
            gen._initialized = True

            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="You get 15 days PTO.")]
            gen.client.messages.create = AsyncMock(return_value=mock_response)

            response, latency, sources = await gen.generate("What is PTO?", "TestUser", "U123")

            assert len(sources) > 0
            assert sources[0]["section_path"] == "Policies > PTO Policy"
