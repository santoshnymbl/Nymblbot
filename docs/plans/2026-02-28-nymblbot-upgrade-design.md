# NymblBot Upgrade Design: Retrieval, Knowledge Base & UX

**Date:** 2026-02-28
**Approach:** Enhanced BM25 + Query Expansion (Approach B)
**Constraints:** Free tier, pre-launch, designed for upgradeability

---

## 1. Improved Retrieval with Query Expansion

**Current:** User question -> BM25 search -> top 5 chunks -> Claude generates answer.

**Proposed:** User question -> Claude rewrites query with synonyms/related terms -> BM25 search on expanded query -> top 5 chunks -> Claude generates answer.

- A lightweight Claude call (Haiku for speed/cost) takes the user's question and produces 2-3 rephrased variants with related keywords.
- Example: "How do I get promoted?" expands to include "performance review", "career growth", "feedback process", "WGLL".
- All variants are searched via BM25, results are merged and deduplicated, then top-K is selected.
- The expansion prompt is a short system prompt (~100 tokens) so the extra API call is cheap and fast (~200-400ms).

**Chunking improvements:**
- Switch from pure header-based splitting to recursive splitting with overlap (200-char overlap between chunks).
- Preserve full header path as metadata on each chunk (e.g., `Policies > PTO > India Holiday Calendar`).
- Chunk metadata powers source citations in the UX layer.

---

## 2. Knowledge Base Improvements

**Knowledge sources (2 files):**

| File | Lines | Content |
|------|-------|---------|
| `nymbl_wiki.md` | ~3,057 | Wiki: leadership, OKRs, tools, processes, glossary |
| `nymbl_handbook.md` | 983 | Handbook: company overview, tenets, culture, employment policies |

**Changes:**
- Recursive character splitting: 1,500 char chunks, 200 char overlap.
- Each chunk carries metadata: `source_file`, `section_path` (full header breadcrumb), `chunk_index`.
- Multi-file support: drop `.md`/`.txt` files in `data/`, picked up on restart.
- Hot reload: Slack slash command `/nymbl-reload` re-indexes without restart.
- Chunk deduplication: near-identical chunks from expanded query are deduplicated before passing to Claude.

**No changes to:** file format support (`.md`/`.txt`), storage location (`data/`), ingestion approach (file-based).

---

## 3. UX Improvements

### 3.1 Conversation Memory
- Store last 5 message exchanges (user question + bot response) per user in SQLite.
- Pass recent history as context to Claude so follow-ups work naturally.
- Messages older than 24 hours excluded to avoid stale context.
- New `conversation_history` table: `user_id`, `role` (user/assistant), `message`, `created_at`.

### 3.2 Source Citations
- Every response includes a footer showing which sources were used.
- Format: `Sources: Handbook > Nymbl Culture | Wiki > PTO Policy`
- Powered by `source_file` + `section_path` metadata from chunking.

### 3.3 Rich Slack Formatting (Block Kit)
- Replace plain text responses with Slack Block Kit messages.
- `section` blocks for the answer body, `divider` before citations, `context` blocks for source references.
- Clean and readable, not flashy.

### 3.4 Feedback Loop
- Thumbs up/down buttons appended to every response.
- On click, log feedback to the existing `interactions` table (`feedback` column).
- One click, no modals.

---

## 4. Error Handling & Edge Cases

- **Query expansion failure:** Fall back to original user query with standard BM25 search. No user-facing error.
- **No results found:** Respond honestly ("I couldn't find information about that in the Nymbl knowledge base."). Don't hallucinate.
- **Conversation memory overflow:** Hard cap at 5 exchanges per user. Oldest pruned on insert, plus 24-hour TTL. Cleanup query runs on startup.
- **Hot reload during query:** In-flight query uses old index. New index takes effect on next query. No locking needed (atomic swap).
- **Feedback button expiry:** Handle gracefully if bot was restarted and user clicks old button.

---

## 5. Testing Strategy

**Unit tests:**
- Query expansion: verify expanded queries contain relevant terms, verify fallback on API failure.
- Chunking: verify overlap, verify metadata attached correctly.
- Conversation memory: verify 5-exchange cap, verify 24-hour TTL pruning.
- Deduplication: verify near-duplicate chunks are merged.

**Integration tests:**
- End-to-end retrieval: question -> expansion -> BM25 -> deduplicated results with metadata.
- Conversation flow: multi-turn exchange where follow-up relies on prior context.
- Hot reload: verify `/nymbl-reload` rebuilds index from current `data/` contents.

**Manual/Slack testing:**
- Common question types against both wiki and handbook.
- Follow-up questions to confirm conversation memory.
- Block Kit rendering in Slack.
- Feedback buttons log to database.
