# NymblBot Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade NymblBot with enhanced BM25 retrieval (query expansion), conversation memory, source citations, Block Kit formatting, and feedback loop.

**Architecture:** Keep BM25 as primary retrieval but add LLM-powered query expansion before search. Add conversation history to SQLite. Format all AI responses with Block Kit including source citations and feedback buttons. Add hot-reload for the knowledge base.

**Tech Stack:** Python 3.11+, FastAPI, Slack Bolt, Anthropic Claude API, rank-bm25, aiosqlite, pytest + pytest-asyncio

---

### Task 1: Add test infrastructure

**Files:**
- Modify: `requirements.txt`
- Create: `tests/conftest.py`
- Create: `pytest.ini`

**Step 1: Add test dependencies to requirements.txt**

Add these lines to the end of `requirements.txt`:

```
# Testing
pytest==8.0.0
pytest-asyncio==0.23.3
```

**Step 2: Create pytest.ini**

Create `pytest.ini` at project root:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
pythonpath = .
```

**Step 3: Create tests/conftest.py**

```python
"""Shared test fixtures for NymblBot tests"""
import os
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def sample_wiki_content():
    """Sample markdown content for testing chunking and retrieval"""
    return """# Company Overview

Nymbl is a technology company founded in 2022.

## Leadership Team

### CEO / Co-Founder

John Smith is the CEO of Nymbl. He leads company strategy.

### CTO

Jane Doe is the CTO. She oversees all technology decisions.

## Policies

### PTO Policy

Employees get 15 days of PTO per year. Submit PTO requests through the HR portal.

For absences of 5 or more days, manager approval is required in advance.

### India Holiday Calendar

India office observes Republic Day (Jan 26), Independence Day (Aug 15), and Gandhi Jayanti (Oct 2).

## Glossary

- WGLL: What Good Looks Like
- WBLL: What Bad Looks Like
- SA: Solution Architect
- BDR: Business Development Representative
"""


@pytest.fixture
def sample_handbook_content():
    """Sample handbook content for testing multi-file retrieval"""
    return """# Hello, Nymblings

# Company Overview

At Nymbl, we are reimagining the way applications are designed and developed.

## Nymbl Tenets

Be Client Focused: Deliver client value
Be Productive: Focus on optimizing internal processes
Be Improving: Constant improvement on yourself and the team
Be Transparent: Full transparency to employees, clients and investors
Be Balanced: Spend time on personal life and your foundation
Be Reliable: No shallow commitments; full ownership of responsibilities
Be Empowering: Constant enablement of clients and employees
"""


@pytest.fixture
def temp_data_dir(sample_wiki_content, sample_handbook_content):
    """Create a temporary data directory with sample documents"""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir) / "nymbl_wiki.md"
        wiki_path.write_text(sample_wiki_content, encoding="utf-8")

        handbook_path = Path(tmpdir) / "nymbl_handbook.md"
        handbook_path.write_text(sample_handbook_content, encoding="utf-8")

        yield tmpdir
```

**Step 4: Run tests to verify setup**

Run: `cd src && python -m pytest ../tests/ -v --co`
Expected: "no tests ran" (collected 0 items) — confirms pytest finds the test directory.

**Step 5: Commit**

```bash
git add requirements.txt pytest.ini tests/conftest.py
git commit -m "feat: add pytest test infrastructure"
```

---

### Task 2: Improve chunking with overlap and metadata

**Files:**
- Modify: `src/ai/rag.py:19-25` (DocumentChunk dataclass)
- Modify: `src/ai/rag.py:75-149` (_chunk_document method)
- Create: `tests/test_chunking.py`

**Step 1: Write the failing tests**

Create `tests/test_chunking.py`:

```python
"""Tests for improved chunking with overlap and metadata"""
from src.ai.rag import RAGPipeline, DocumentChunk


class TestChunking:
    def test_chunk_has_section_path_metadata(self, temp_data_dir):
        """Chunks should carry full header breadcrumb as section_path"""
        pipeline = RAGPipeline(data_dir=temp_data_dir)
        pipeline.load()

        # Find a chunk from nested section
        ceo_chunks = [c for c in pipeline.chunks if "CEO" in c.section_path]
        assert len(ceo_chunks) > 0
        assert ceo_chunks[0].section_path == "Leadership Team > CEO / Co-Founder"

    def test_chunk_has_source_file_metadata(self, temp_data_dir):
        """Chunks should know which file they came from"""
        pipeline = RAGPipeline(data_dir=temp_data_dir)
        pipeline.load()

        wiki_chunks = [c for c in pipeline.chunks if c.source == "nymbl_wiki.md"]
        handbook_chunks = [c for c in pipeline.chunks if c.source == "nymbl_handbook.md"]
        assert len(wiki_chunks) > 0
        assert len(handbook_chunks) > 0

    def test_chunks_have_overlap(self, temp_data_dir):
        """Adjacent chunks from the same section should share overlapping text"""
        # Create a pipeline with a very small chunk size to force splitting
        pipeline = RAGPipeline(data_dir=temp_data_dir)
        pipeline.load()

        # Get chunks from the same section
        pto_chunks = [c for c in pipeline.chunks if "PTO" in c.section_path]
        if len(pto_chunks) >= 2:
            # Last part of chunk N should appear in start of chunk N+1
            end_of_first = pto_chunks[0].content[-100:]
            assert any(
                end_of_first[:50] in c.content for c in pto_chunks[1:]
            ), "Adjacent chunks should share overlapping text"

    def test_chunk_id_is_sequential(self, temp_data_dir):
        """Chunk IDs should be sequential within a source file"""
        pipeline = RAGPipeline(data_dir=temp_data_dir)
        pipeline.load()

        wiki_chunks = [c for c in pipeline.chunks if c.source == "nymbl_wiki.md"]
        ids = [c.chunk_id for c in wiki_chunks]
        assert ids == list(range(len(ids))), "Chunk IDs should be sequential"
```

**Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest ../tests/test_chunking.py -v`
Expected: FAIL — `DocumentChunk` has no `section_path` attribute.

**Step 3: Update DocumentChunk dataclass**

In `src/ai/rag.py`, replace the `DocumentChunk` dataclass (lines 19-25):

```python
@dataclass
class DocumentChunk:
    """A chunk of text from a document"""
    content: str
    source: str          # filename (e.g., "nymbl_wiki.md")
    section: str         # immediate section header
    section_path: str    # full breadcrumb (e.g., "Policies > PTO Policy")
    chunk_id: int
```

**Step 4: Rewrite _chunk_document with overlap and section path tracking**

Replace `_chunk_document` method (lines 75-149) in `src/ai/rag.py`:

```python
    def _chunk_document(self, source: str, content: str) -> List[DocumentChunk]:
        """Split document into searchable chunks with overlap and metadata"""
        chunks = []
        chunk_id = 0
        overlap_size = 200  # characters of overlap between chunks

        # Track header hierarchy for breadcrumb paths
        header_stack = []  # list of (level, text) tuples

        # Split by headers (# ## ###)
        sections = re.split(r'\n(?=#{1,3}\s+)', content)

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # Extract header and update hierarchy
            header_match = re.match(r'^(#{1,3})\s+(.+?)(?:\n|$)', section)
            if header_match:
                level = len(header_match.group(1))
                header = header_match.group(2).strip()
                body = section[header_match.end():].strip()

                # Pop headers at same or deeper level
                header_stack = [(l, t) for l, t in header_stack if l < level]
                header_stack.append((level, header))
            else:
                header = "General"
                body = section

            # Build section path breadcrumb
            section_path = " > ".join(t for _, t in header_stack)
            if not section_path:
                section_path = header

            # Skip empty sections
            if not body:
                continue

            max_chunk_size = 1500

            if len(body) > max_chunk_size:
                # Split by paragraphs with overlap
                paragraphs = body.split("\n\n")
                current_chunk = ""
                prev_chunk_tail = ""

                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue

                    if len(current_chunk) + len(para) < max_chunk_size:
                        current_chunk += para + "\n\n"
                    else:
                        if current_chunk.strip():
                            # Prepend overlap from previous chunk
                            chunk_text = prev_chunk_tail + current_chunk.strip() if prev_chunk_tail else current_chunk.strip()
                            chunk_content = f"{header}\n\n{chunk_text}"
                            chunks.append(DocumentChunk(
                                content=chunk_content,
                                source=source,
                                section=header,
                                section_path=section_path,
                                chunk_id=chunk_id
                            ))
                            chunk_id += 1
                            # Save tail for overlap
                            prev_chunk_tail = current_chunk.strip()[-overlap_size:] + "\n\n"
                        current_chunk = para + "\n\n"

                if current_chunk.strip():
                    chunk_text = prev_chunk_tail + current_chunk.strip() if prev_chunk_tail else current_chunk.strip()
                    chunk_content = f"{header}\n\n{chunk_text}"
                    chunks.append(DocumentChunk(
                        content=chunk_content,
                        source=source,
                        section=header,
                        section_path=section_path,
                        chunk_id=chunk_id
                    ))
                    chunk_id += 1
            else:
                chunk_content = f"{header}\n\n{body}"
                chunks.append(DocumentChunk(
                    content=chunk_content,
                    source=source,
                    section=header,
                    section_path=section_path,
                    chunk_id=chunk_id
                ))
                chunk_id += 1

        return chunks
```

**Step 5: Run tests to verify they pass**

Run: `cd src && python -m pytest ../tests/test_chunking.py -v`
Expected: PASS (all 4 tests)

**Step 6: Commit**

```bash
git add src/ai/rag.py tests/test_chunking.py
git commit -m "feat: improve chunking with overlap and section_path metadata"
```

---

### Task 3: Add query expansion module

**Files:**
- Create: `src/ai/query_expansion.py`
- Modify: `src/ai/__init__.py`
- Create: `tests/test_query_expansion.py`

**Step 1: Write the failing tests**

Create `tests/test_query_expansion.py`:

```python
"""Tests for LLM-powered query expansion"""
import pytest
from unittest.mock import MagicMock, patch
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
        mock_client.messages.create.return_value = mock_response

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
```

**Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest ../tests/test_query_expansion.py -v`
Expected: FAIL — module `src.ai.query_expansion` does not exist.

**Step 3: Create query expansion module**

Create `src/ai/query_expansion.py`:

```python
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


async def expand_query(query: str, client: anthropic.Anthropic) -> List[str]:
    """
    Expand a user query into multiple search variants using Claude.
    Always returns the original query as the first element.
    Falls back to just the original query on any error.
    """
    expanded = [query]

    try:
        response = client.messages.create(
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
```

**Step 4: Update `src/ai/__init__.py`**

Add the new export:

```python
from .rag import rag_pipeline, initialize_rag, RAGPipeline
from .generator import ai_generator, AIGenerator, get_quick_response
from .query_expansion import expand_query

__all__ = [
    "rag_pipeline",
    "initialize_rag",
    "RAGPipeline",
    "ai_generator",
    "AIGenerator",
    "get_quick_response",
    "expand_query"
]
```

**Step 5: Run tests to verify they pass**

Run: `cd src && python -m pytest ../tests/test_query_expansion.py -v`
Expected: PASS (all 6 tests)

**Step 6: Commit**

```bash
git add src/ai/query_expansion.py src/ai/__init__.py tests/test_query_expansion.py
git commit -m "feat: add LLM-powered query expansion module"
```

---

### Task 4: Integrate query expansion into RAG search

**Files:**
- Modify: `src/ai/rag.py:200-250` (search and get_context methods)
- Create: `tests/test_rag_search.py`

**Step 1: Write the failing tests**

Create `tests/test_rag_search.py`:

```python
"""Tests for RAG search with query expansion integration"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.ai.rag import RAGPipeline


class TestSearchWithExpansion:
    def test_search_returns_results_with_section_path(self, temp_data_dir):
        """Search results should include section_path metadata"""
        pipeline = RAGPipeline(data_dir=temp_data_dir)
        pipeline.load()

        results = pipeline.search("PTO policy")
        assert len(results) > 0
        chunk, score = results[0]
        assert hasattr(chunk, "section_path")
        assert chunk.section_path  # not empty

    def test_multi_query_search_merges_results(self, temp_data_dir):
        """Searching with multiple queries should merge and deduplicate"""
        pipeline = RAGPipeline(data_dir=temp_data_dir)
        pipeline.load()

        results = pipeline.search_multi(
            queries=["PTO policy", "time off vacation days", "leave policy"],
            top_k=5
        )
        assert len(results) > 0
        # No duplicate chunk_ids from same source
        seen = set()
        for chunk, score in results:
            key = (chunk.source, chunk.chunk_id)
            assert key not in seen, f"Duplicate chunk: {key}"
            seen.add(key)

    def test_get_context_returns_sources(self, temp_data_dir):
        """get_context should return both context text and source metadata"""
        pipeline = RAGPipeline(data_dir=temp_data_dir)
        pipeline.load()

        context, sources = pipeline.get_context_with_sources("PTO policy")
        assert len(context) > 0
        assert len(sources) > 0
        assert all("source" in s and "section_path" in s for s in sources)
```

**Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest ../tests/test_rag_search.py -v`
Expected: FAIL — `search_multi` and `get_context_with_sources` don't exist.

**Step 3: Add search_multi and get_context_with_sources to RAGPipeline**

In `src/ai/rag.py`, add these methods after the existing `search` method (after line 225):

```python
    def search_multi(self, queries: List[str], top_k: int = None) -> List[Tuple[DocumentChunk, float]]:
        """
        Search with multiple query variants and merge results.
        Deduplicates by (source, chunk_id), keeping highest score.
        """
        if not self._loaded:
            self.load()

        if not self.chunks or self.bm25 is None:
            return []

        top_k = top_k or settings.rerank_top_k
        best_scores = {}  # (source, chunk_id) -> (chunk, score)

        for query in queries:
            query_tokens = self._tokenize(query)
            bm25_scores = self.bm25.get_scores(query_tokens)

            top_indices = bm25_scores.argsort()[-settings.bm25_top_k:][::-1]

            for i in top_indices:
                if bm25_scores[i] <= 0:
                    continue
                chunk = self.chunks[i]
                key = (chunk.source, chunk.chunk_id)
                score = float(bm25_scores[i])

                if key not in best_scores or score > best_scores[key][1]:
                    best_scores[key] = (chunk, score)

        # Sort by score descending, take top_k
        merged = sorted(best_scores.values(), key=lambda x: x[1], reverse=True)
        return merged[:top_k]

    def get_context_with_sources(self, query: str, queries: List[str] = None, max_chars: int = 3000) -> Tuple[str, List[dict]]:
        """
        Get formatted context string and source metadata for citations.
        If queries (expanded) are provided, uses search_multi.
        Returns: (context_text, sources_list)
        """
        if queries and len(queries) > 1:
            results = self.search_multi(queries)
        else:
            results = self.search(query)

        if not results:
            return "No relevant information found in the knowledge base.", []

        context_parts = []
        sources = []
        total_chars = 0

        for chunk, score in results:
            chunk_text = f"### {chunk.section}\n(Source: {chunk.source})\n\n{chunk.content}"

            if total_chars + len(chunk_text) > max_chars:
                break

            context_parts.append(chunk_text)
            total_chars += len(chunk_text)

            # Collect unique sources for citation
            source_entry = {
                "source": chunk.source,
                "section_path": chunk.section_path
            }
            if source_entry not in sources:
                sources.append(source_entry)

        context = "\n\n---\n\n".join(context_parts)
        return context, sources
```

**Step 4: Run tests to verify they pass**

Run: `cd src && python -m pytest ../tests/test_rag_search.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add src/ai/rag.py tests/test_rag_search.py
git commit -m "feat: add multi-query search and source metadata to RAG"
```

---

### Task 5: Add conversation_history table to database

**Files:**
- Modify: `src/models/database.py:55-104` (init_database, add table)
- Modify: `src/models/database.py` (add CRUD functions)
- Modify: `src/models/__init__.py`
- Create: `tests/test_conversation_history.py`

**Step 1: Write the failing tests**

Create `tests/test_conversation_history.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest ../tests/test_conversation_history.py -v`
Expected: FAIL — `save_conversation_message` and `get_conversation_history` don't exist.

**Step 3: Add conversation_history table to init_database**

In `src/models/database.py`, add after the reminder_log CREATE TABLE (after line 96):

```python
        # Conversation history table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
```

Add a new index after line 101:

```python
        await db.execute("CREATE INDEX IF NOT EXISTS idx_conversation_user ON conversation_history(user_id)")
```

**Step 4: Add CRUD functions for conversation history**

Add before the STATS QUERIES section (before the `# STATS QUERIES` comment, around line 283):

```python
# =============================================================================
# CONVERSATION HISTORY QUERIES
# =============================================================================

async def save_conversation_message(user_id: str, role: str, content: str):
    """Save a single conversation message"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("""
            INSERT INTO conversation_history (user_id, role, content)
            VALUES (?, ?, ?)
        """, (user_id, role, content))
        await db.commit()


async def get_conversation_history(
    user_id: str,
    max_exchanges: int = 5,
    max_age_hours: int = 24
) -> List[dict]:
    """
    Get recent conversation history for a user.
    Returns list of {"role": str, "content": str} dicts, oldest first.
    Limited to max_exchanges (pairs of user+assistant messages).
    Excludes messages older than max_age_hours.
    """
    max_messages = max_exchanges * 2

    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT role, content FROM conversation_history
            WHERE user_id = ?
            AND created_at > datetime('now', ?)
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, f'-{max_age_hours} hours', max_messages)) as cursor:
            rows = await cursor.fetchall()

    # Reverse to get oldest first
    rows = list(reversed(rows))
    return [{"role": row["role"], "content": row["content"]} for row in rows]


async def cleanup_old_conversations(max_age_hours: int = 48):
    """Delete conversation messages older than max_age_hours"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("""
            DELETE FROM conversation_history
            WHERE created_at < datetime('now', ?)
        """, (f'-{max_age_hours} hours',))
        await db.commit()
```

**Step 5: Update `src/models/__init__.py`**

Add the new exports:

```python
from .database import (
    init_database,
    UserPreference,
    Interaction,
    ReminderLog,
    get_user,
    create_user,
    update_user,
    get_or_create_user,
    get_subscribed_users,
    log_interaction,
    update_feedback,
    log_reminder_sent,
    check_reminder_sent_today,
    acknowledge_reminder,
    snooze_reminder,
    get_stats,
    save_conversation_message,
    get_conversation_history,
    cleanup_old_conversations
)

__all__ = [
    "init_database",
    "UserPreference",
    "Interaction",
    "ReminderLog",
    "get_user",
    "create_user",
    "update_user",
    "get_or_create_user",
    "get_subscribed_users",
    "log_interaction",
    "update_feedback",
    "log_reminder_sent",
    "check_reminder_sent_today",
    "acknowledge_reminder",
    "snooze_reminder",
    "get_stats",
    "save_conversation_message",
    "get_conversation_history",
    "cleanup_old_conversations"
]
```

**Step 6: Run tests to verify they pass**

Run: `cd src && python -m pytest ../tests/test_conversation_history.py -v`
Expected: PASS (all 4 tests)

**Step 7: Commit**

```bash
git add src/models/database.py src/models/__init__.py tests/test_conversation_history.py
git commit -m "feat: add conversation_history table and CRUD functions"
```

---

### Task 6: Wire query expansion and conversation memory into the generator

**Files:**
- Modify: `src/ai/generator.py:37-114` (generate method)
- Create: `tests/test_generator.py`

**Step 1: Write the failing tests**

Create `tests/test_generator.py`:

```python
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
            gen.client.messages.create.return_value = mock_response

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
            gen.client.messages.create.return_value = mock_response

            response, latency, sources = await gen.generate("What is PTO?", "TestUser", "U123")

            assert len(sources) > 0
            assert sources[0]["section_path"] == "Policies > PTO Policy"
```

**Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest ../tests/test_generator.py -v`
Expected: FAIL — `generate` doesn't return sources or call `expand_query`.

**Step 3: Rewrite the generator's generate method**

Replace the full `generate` method in `src/ai/generator.py` (lines 37-114) and update imports:

At the top of the file, update imports (lines 1-14):

```python
"""
Miss Minutes - AI Response Generator
Claude API integration with query expansion and conversation memory
"""
import logging
import time
from typing import Optional, List

import anthropic

from src.config import settings, SYSTEM_PROMPT
from src.ai.rag import rag_pipeline
from src.ai.query_expansion import expand_query
from src.models.database import get_conversation_history, save_conversation_message

logger = logging.getLogger(__name__)
```

Replace the `generate` method:

```python
    async def generate(
        self,
        query: str,
        user_name: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> tuple[str, int, List[dict]]:
        """
        Generate a response to user's query.

        Returns: (response_text, latency_ms, sources)
        """
        if not self._initialized:
            self.initialize()

        if not self.client:
            return "I'm having trouble connecting right now. Please try again!", 0, []

        start_time = time.time()

        try:
            # Step 1: Expand the query for better retrieval
            expanded_queries = await expand_query(query, self.client)
            logger.info(f"Expanded queries: {expanded_queries}")

            # Step 2: Get RAG context with source metadata
            context, sources = rag_pipeline.get_context_with_sources(
                query=query,
                queries=expanded_queries
            )

            logger.info(f"RAG Context for '{query}': {context[:500]}...")

            # Step 3: Build system prompt
            system = SYSTEM_PROMPT
            if user_name:
                system += f"\n\nYou're talking to {user_name}."

            # Step 4: Build messages with conversation history
            messages = []

            if user_id:
                history = await get_conversation_history(user_id)
                for msg in history:
                    messages.append({"role": msg["role"], "content": msg["content"]})

            # Add current user message with RAG context
            user_message = f"""Here's relevant information from Nymbl's knowledge base:

{context}

---

User's question: {query}

IMPORTANT: The section headers (like "CEO / Co-Founder", "Leave Policy", etc.) indicate what/who the content is about. Use both the headers AND content to answer.

Please answer based on the information above. Be direct and specific - if the answer is in the context, state it clearly."""

            messages.append({"role": "user", "content": user_message})

            # Step 5: Call Claude
            response = self.client.messages.create(
                model=settings.claude_model,
                max_tokens=1024,
                system=system,
                messages=messages
            )

            answer = response.content[0].text
            latency_ms = int((time.time() - start_time) * 1000)

            # Step 6: Save to conversation history
            if user_id:
                await save_conversation_message(user_id, "user", query)
                await save_conversation_message(user_id, "assistant", answer)

            logger.info(f"Generated response in {latency_ms}ms for: {query[:50]}...")
            return answer, latency_ms, sources

        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            latency_ms = int((time.time() - start_time) * 1000)
            return "I ran into a hiccup with my AI brain! Try asking again in a moment.", latency_ms, []

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            latency_ms = int((time.time() - start_time) * 1000)
            return "Something went wrong on my end. Let me know if this keeps happening!", latency_ms, []
```

**Step 4: Run tests to verify they pass**

Run: `cd src && python -m pytest ../tests/test_generator.py -v`
Expected: PASS (all 2 tests)

**Step 5: Commit**

```bash
git add src/ai/generator.py tests/test_generator.py
git commit -m "feat: wire query expansion and conversation memory into generator"
```

---

### Task 7: Add Block Kit response formatting with source citations

**Files:**
- Create: `src/slack/formatting.py`
- Create: `tests/test_formatting.py`

**Step 1: Write the failing tests**

Create `tests/test_formatting.py`:

```python
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
        # Should have no citation context (may still have feedback)
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
```

**Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest ../tests/test_formatting.py -v`
Expected: FAIL — `src.slack.formatting` does not exist.

**Step 3: Create the formatting module**

Create `src/slack/formatting.py`:

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `cd src && python -m pytest ../tests/test_formatting.py -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add src/slack/formatting.py tests/test_formatting.py
git commit -m "feat: add Block Kit response formatting with citations and feedback buttons"
```

---

### Task 8: Update Slack handler to use new generator and formatting

**Files:**
- Modify: `src/slack/handler.py:196-242` (process_message)
- Modify: `src/slack/handler.py:162-192` (add feedback action handlers)
- Modify: `src/models/database.py:211-218` (update log_interaction to return ID)
- Modify: `src/slack/__init__.py`

**Step 1: Update log_interaction to return the interaction ID**

In `src/models/database.py`, replace `log_interaction` (lines 211-218):

```python
async def log_interaction(user_id: str, query: str, response: str, latency_ms: int) -> int:
    """Log an interaction and return the interaction ID"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute("""
            INSERT INTO interactions (user_id, query, response, latency_ms)
            VALUES (?, ?, ?, ?)
        """, (user_id, query, response, latency_ms))
        await db.commit()
        return cursor.lastrowid
```

**Step 2: Update handler imports and process_message**

In `src/slack/handler.py`, update the imports (lines 1-17):

```python
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
from src.models import get_or_create_user, log_interaction, update_feedback, get_stats
from src.ai import ai_generator, get_quick_response
from src.slack.commands import handle_command
from src.slack.formatting import format_ai_response

logger = logging.getLogger(__name__)
```

Replace `process_message` (lines 196-242):

```python
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

    # Generate AI response (now returns sources too)
    response, latency_ms, sources = await ai_generator.generate(text, user_name, user_id)

    # Remove thinking reaction
    try:
        await client.reactions_remove(channel=channel, timestamp=message_ts, name="hourglass_flowing_sand")
    except:
        pass

    # Log interaction and get ID for feedback buttons
    interaction_id = await log_interaction(user_id, text, response, latency_ms)

    # Format with Block Kit (citations + feedback buttons)
    blocks = format_ai_response(response, sources, interaction_id)
    await say(blocks=blocks, text=response, thread_ts=thread_ts)
```

**Step 3: Add feedback action handlers**

In `src/slack/handler.py`, add these handlers inside `create_slack_app()`, after the existing action handlers (after line 191, before `return app`):

```python
    # =========================================================================
    # ACTIONS: Feedback Buttons
    # =========================================================================
    @app.action(re.compile(r"^feedback_positive_\d+$"))
    async def handle_positive_feedback(ack, body, say):
        """Handle positive feedback button click"""
        await ack()
        action_id = body["actions"][0]["action_id"]
        interaction_id = int(action_id.split("_")[-1])
        await update_feedback(interaction_id, "positive")
        # Update message to show feedback was recorded
        await say(text="Thanks for the feedback! Glad I could help.")

    @app.action(re.compile(r"^feedback_negative_\d+$"))
    async def handle_negative_feedback(ack, body, say):
        """Handle negative feedback button click"""
        await ack()
        action_id = body["actions"][0]["action_id"]
        interaction_id = int(action_id.split("_")[-1])
        await update_feedback(interaction_id, "negative")
        await say(text="Thanks for the feedback. I'll try to do better!")
```

**Step 4: Update `src/slack/__init__.py`**

```python
from .handler import create_slack_app, get_user_display_name
from .commands import handle_command
from .formatting import format_ai_response

__all__ = [
    "create_slack_app",
    "get_user_display_name",
    "handle_command",
    "format_ai_response"
]
```

**Step 5: Commit**

```bash
git add src/slack/handler.py src/slack/formatting.py src/slack/__init__.py src/models/database.py
git commit -m "feat: wire Block Kit formatting, feedback buttons, and updated generator into Slack handler"
```

---

### Task 9: Add hot reload command

**Files:**
- Modify: `src/slack/commands.py:32-85` (add reload command)
- Modify: `src/ai/rag.py` (add reload method)

**Step 1: Add reload method to RAGPipeline**

In `src/ai/rag.py`, add this method to the RAGPipeline class (after the `load` method, around line 73):

```python
    def reload(self) -> None:
        """Force reload of all documents and rebuild index"""
        logger.info("Reloading RAG pipeline...")
        self.chunks = []
        self.bm25 = None
        self.tokenized_chunks = []
        self._loaded = False
        self.load()
        logger.info(f"RAG pipeline reloaded with {len(self.chunks)} chunks")
```

**Step 2: Add reload command to command handler**

In `src/slack/commands.py`, add an import at the top (after line 27):

```python
from src.ai.rag import rag_pipeline
```

In the `handle_command` function, add before the `# Not a command` line (before line 85):

```python
    # Reload knowledge base
    if text_lower in ["reload", "refresh", "reindex"]:
        return handle_reload()
```

Add the handler function (at the end of the file):

```python
def handle_reload() -> dict:
    """Handle reload command - reindex knowledge base"""
    try:
        rag_pipeline.reload()
        chunk_count = len(rag_pipeline.chunks)
        return {
            "text": f"Knowledge base reloaded. Indexed {chunk_count} chunks from {len(set(c.source for c in rag_pipeline.chunks))} documents."
        }
    except Exception as e:
        return {
            "text": f"Failed to reload knowledge base: {str(e)}"
        }
```

**Step 3: Commit**

```bash
git add src/ai/rag.py src/slack/commands.py
git commit -m "feat: add hot reload command for knowledge base"
```

---

### Task 10: Add startup cleanup for conversation history

**Files:**
- Modify: `src/app.py:38-74` (lifespan function)

**Step 1: Add cleanup to startup**

In `src/app.py`, add import at the top (with other model imports):

```python
from src.models import init_database, get_stats, cleanup_old_conversations
```

In the `lifespan` function, add after database initialization (after line 49):

```python
        # Cleanup old conversation history
        await cleanup_old_conversations(max_age_hours=48)
        logger.info("Cleaned up old conversation history")
```

**Step 2: Commit**

```bash
git add src/app.py
git commit -m "feat: add conversation history cleanup on startup"
```

---

### Task 11: Integration test - end-to-end retrieval

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

Create `tests/test_integration.py`:

```python
"""Integration tests for the full retrieval pipeline"""
import pytest
from unittest.mock import MagicMock
from src.ai.rag import RAGPipeline


class TestEndToEndRetrieval:
    def test_query_expansion_improves_pto_india_search(self, temp_data_dir):
        """Multi-query search should find PTO + India info from separate sections"""
        pipeline = RAGPipeline(data_dir=temp_data_dir)
        pipeline.load()

        # Simulate expanded queries for "What's the PTO policy for India?"
        expanded = [
            "What's the PTO policy for India?",
            "paid time off India employees",
            "India holiday calendar leave policy"
        ]

        results = pipeline.search_multi(queries=expanded, top_k=5)

        # Should find chunks from both PTO and India sections
        section_paths = [chunk.section_path for chunk, score in results]
        has_pto = any("PTO" in sp for sp in section_paths)
        has_india = any("India" in sp for sp in section_paths)
        assert has_pto, f"Should find PTO section, got: {section_paths}"
        assert has_india, f"Should find India section, got: {section_paths}"

    def test_context_with_sources_has_metadata(self, temp_data_dir):
        """get_context_with_sources should return usable citation data"""
        pipeline = RAGPipeline(data_dir=temp_data_dir)
        pipeline.load()

        context, sources = pipeline.get_context_with_sources("Who is the CEO?")
        assert "CEO" in context or "John Smith" in context
        assert len(sources) > 0
        assert all("source" in s for s in sources)
        assert all("section_path" in s for s in sources)

    def test_reload_picks_up_changes(self, temp_data_dir):
        """After reload, new content should be searchable"""
        from pathlib import Path

        pipeline = RAGPipeline(data_dir=temp_data_dir)
        pipeline.load()

        initial_count = len(pipeline.chunks)

        # Add a new file
        new_file = Path(temp_data_dir) / "new_doc.md"
        new_file.write_text("# New Feature\n\nThis is a brand new feature called Zebra Dashboard.", encoding="utf-8")

        # Reload
        pipeline.reload()

        assert len(pipeline.chunks) > initial_count

        # Search for new content
        results = pipeline.search("Zebra Dashboard")
        assert len(results) > 0
        assert any("Zebra" in chunk.content for chunk, score in results)

    def test_multi_file_search_returns_both_sources(self, temp_data_dir):
        """Search across wiki and handbook should return results from both"""
        pipeline = RAGPipeline(data_dir=temp_data_dir)
        pipeline.load()

        results = pipeline.search_multi(
            queries=["Nymbl company overview", "company founded technology"],
            top_k=10
        )
        sources = set(chunk.source for chunk, score in results)
        assert "nymbl_wiki.md" in sources or "nymbl_handbook.md" in sources
```

**Step 2: Run all tests**

Run: `cd src && python -m pytest ../tests/ -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for end-to-end retrieval pipeline"
```

---

### Task 12: Delete old database and final verification

**Step 1: Delete old database so new schema is created fresh**

The old `miss_minutes.db` won't have the `conversation_history` table. Delete it so it's recreated on next startup:

```bash
rm -f db/miss_minutes.db
```

**Step 2: Run full test suite**

Run: `cd src && python -m pytest ../tests/ -v --tb=short`
Expected: ALL PASS

**Step 3: Final commit**

```bash
git add -A
git commit -m "chore: remove old database for fresh schema creation"
```

---

## Summary of All Changes

| File | Change |
|------|--------|
| `requirements.txt` | Add pytest, pytest-asyncio |
| `pytest.ini` | New — test config |
| `tests/conftest.py` | New — shared fixtures |
| `tests/test_chunking.py` | New — chunking tests |
| `tests/test_query_expansion.py` | New — expansion tests |
| `tests/test_rag_search.py` | New — search tests |
| `tests/test_conversation_history.py` | New — DB tests |
| `tests/test_generator.py` | New — generator tests |
| `tests/test_formatting.py` | New — Block Kit tests |
| `tests/test_integration.py` | New — end-to-end tests |
| `src/ai/rag.py` | Chunk overlap, section_path, search_multi, get_context_with_sources, reload |
| `src/ai/generator.py` | Query expansion, conversation memory, return sources |
| `src/ai/query_expansion.py` | New — LLM query expansion |
| `src/ai/__init__.py` | Export expand_query |
| `src/models/database.py` | conversation_history table, CRUD, log_interaction returns ID |
| `src/models/__init__.py` | Export new functions |
| `src/slack/handler.py` | Block Kit responses, feedback handlers, pass user_id |
| `src/slack/formatting.py` | New — Block Kit formatting |
| `src/slack/commands.py` | Add reload command |
| `src/slack/__init__.py` | Export formatting |
| `src/app.py` | Conversation cleanup on startup |
