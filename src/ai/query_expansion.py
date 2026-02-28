"""
NymblBot - LLM-Powered Query Expansion
Uses a fast Claude call to rephrase user queries with synonyms and related terms.
"""
import re
import logging
from typing import List, Optional

import anthropic

logger = logging.getLogger(__name__)

EXPANSION_PROMPT = """You are a search query expander for a company knowledge base.
Given a user's question, generate 2-3 alternative search queries that use different
keywords and synonyms to find the same information. Focus on company terminology.

Output ONLY the alternative queries, one per line, numbered. No explanations.

User question: {query}"""


def parse_expansion_response(response_text: str) -> List[str]:
    """Parse the expansion response into a list of query strings"""
    if not response_text.strip():
        return []

    queries = []
    for line in response_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Remove numbering (1. 2. 3.) or bullets (- *)
        cleaned = re.sub(r'^[\d]+[.)]\s*', '', line)
        cleaned = re.sub(r'^[-*]\s*', '', cleaned)
        cleaned = cleaned.strip()
        if cleaned:
            queries.append(cleaned)

    return queries


async def expand_query(query: str, client: anthropic.AsyncAnthropic) -> List[str]:
    """
    Expand a user query into multiple search variants using Claude.
    Always returns the original query as the first element.
    Falls back to just the original query on any error.
    """
    expanded = [query]

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": EXPANSION_PROMPT.format(query=query)
            }]
        )

        variants = parse_expansion_response(response.content[0].text)
        expanded.extend(variants)
        logger.info(f"Expanded '{query}' into {len(expanded)} variants")

    except Exception as e:
        logger.warning(f"Query expansion failed, using original query: {e}")

    return expanded
