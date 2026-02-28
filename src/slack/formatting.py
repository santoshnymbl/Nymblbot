"""
NymblBot - Slack Block Kit Response Formatting
Formats AI responses with source citations and feedback buttons.
"""
from typing import List


def format_ai_response(answer: str, sources: List[dict], interaction_id: int) -> list:
    """
    Format an AI response as Slack Block Kit blocks.
    Includes: answer section, source citations, feedback buttons.
    """
    blocks = []

    # Answer section
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": answer
        }
    })

    # Source citations (if any)
    if sources:
        # Deduplicate sources
        seen = set()
        unique_sources = []
        for s in sources:
            key = s["section_path"]
            if key not in seen:
                seen.add(key)
                unique_sources.append(s)

        # Format as "source_file > section_path"
        citation_parts = []
        for s in unique_sources:
            # Remove .md extension for cleaner display
            source_name = s["source"].replace(".md", "").replace("nymbl_", "").title()
            citation_parts.append(f"{source_name} > {s['section_path']}")

        citation_text = " | ".join(citation_parts)

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"Sources: {citation_text}"
            }]
        })

    # Feedback buttons
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Helpful", "emoji": True},
                "action_id": f"feedback_positive_{interaction_id}",
                "value": f"positive_{interaction_id}"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Not Helpful", "emoji": True},
                "action_id": f"feedback_negative_{interaction_id}",
                "value": f"negative_{interaction_id}"
            }
        ]
    })

    return blocks
