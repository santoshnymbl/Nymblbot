"""Tests for LLM-powered query expansion"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.ai.query_expansion import expand_query, parse_expansion_response


class TestParseExpansionResponse:
    def test_parses_numbered_list(self):
        """Should extract queries from numbered list format"""
        response = "1. performance review process\n2. career growth feedback\n3. WGLL promotion criteria"
        result = parse_expansion_response(response)
        assert len(result) == 3
        assert "performance review process" in result

    def test_parses_bullet_list(self):
        """Should extract queries from bullet list format"""
        response = "- performance review process\n- career growth\n- promotion criteria"
        result = parse_expansion_response(response)
        assert len(result) == 3

    def test_parses_plain_lines(self):
        """Should extract queries from plain lines"""
        response = "performance review process\ncareer growth feedback\npromotion criteria"
        result = parse_expansion_response(response)
        assert len(result) == 3

    def test_returns_empty_on_empty_input(self):
        """Should return empty list on empty input"""
        result = parse_expansion_response("")
        assert result == []


class TestExpandQuery:
    @pytest.mark.asyncio
    async def test_returns_original_plus_expansions(self):
        """Should return original query plus expanded variants"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="1. performance review\n2. feedback process")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        result = await expand_query("How do I get promoted?", mock_client)
        assert "How do I get promoted?" in result
        assert len(result) >= 2

    @pytest.mark.asyncio
    async def test_returns_original_on_api_failure(self):
        """Should fall back to just the original query if API fails"""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")

        result = await expand_query("How do I get promoted?", mock_client)
        assert result == ["How do I get promoted?"]
