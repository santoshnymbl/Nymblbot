"""Tests for Slack Block Kit response formatting"""
from src.slack.formatting import format_ai_response


class TestFormatAIResponse:
    def test_includes_answer_section(self):
        """Response should have a section block with the answer"""
        blocks = format_ai_response(
            answer="You get 15 days PTO.",
            sources=[{"source": "nymbl_wiki.md", "section_path": "Policies > PTO"}],
            interaction_id=1
        )
        section_blocks = [b for b in blocks if b.get("type") == "section"]
        assert len(section_blocks) >= 1
        assert "15 days PTO" in section_blocks[0]["text"]["text"]

    def test_includes_source_citations(self):
        """Response should have a context block with source citations"""
        blocks = format_ai_response(
            answer="You get 15 days PTO.",
            sources=[
                {"source": "nymbl_wiki.md", "section_path": "Policies > PTO Policy"},
                {"source": "nymbl_handbook.md", "section_path": "Company Overview"}
            ],
            interaction_id=1
        )
        context_blocks = [b for b in blocks if b.get("type") == "context"]
        assert len(context_blocks) >= 1
        citation_text = context_blocks[0]["elements"][0]["text"]
        assert "PTO Policy" in citation_text
        assert "Company Overview" in citation_text

    def test_includes_feedback_buttons(self):
        """Response should have thumbs up/down action buttons"""
        blocks = format_ai_response(
            answer="You get 15 days PTO.",
            sources=[],
            interaction_id=42
        )
        action_blocks = [b for b in blocks if b.get("type") == "actions"]
        assert len(action_blocks) == 1
        buttons = action_blocks[0]["elements"]
        assert len(buttons) == 2
        action_ids = [b["action_id"] for b in buttons]
        assert "feedback_positive_42" in action_ids
        assert "feedback_negative_42" in action_ids

    def test_no_sources_skips_citation(self):
        """If no sources, should skip the citation context block"""
        blocks = format_ai_response(
            answer="I couldn't find that information.",
            sources=[],
            interaction_id=1
        )
        context_blocks = [b for b in blocks if b.get("type") == "context"]
        # Should have no citation context
        citation_contexts = [
            b for b in context_blocks
            if any("Sources:" in e.get("text", "") for e in b.get("elements", []))
        ]
        assert len(citation_contexts) == 0

    def test_deduplicates_sources(self):
        """Duplicate sources should be deduplicated in citations"""
        blocks = format_ai_response(
            answer="Answer text.",
            sources=[
                {"source": "nymbl_wiki.md", "section_path": "Policies > PTO"},
                {"source": "nymbl_wiki.md", "section_path": "Policies > PTO"},
            ],
            interaction_id=1
        )
        context_blocks = [b for b in blocks if b.get("type") == "context"]
        if context_blocks:
            text = context_blocks[0]["elements"][0]["text"]
            assert text.count("PTO") == 1  # should appear only once
