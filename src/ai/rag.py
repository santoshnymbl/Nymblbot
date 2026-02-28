"""
Miss Minutes - RAG Pipeline
BM25 Retrieval (Lightweight - no heavy ML models)
"""
import os
import re
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """A chunk of text from a document"""
    content: str
    source: str          # filename (e.g., "nymbl_wiki.md")
    section: str         # immediate section header
    section_path: str    # full breadcrumb (e.g., "Policies > PTO Policy")
    chunk_id: int


class RAGPipeline:
    """
    Lightweight RAG Pipeline using BM25
    - Fast and efficient
    - No heavy ML models (works on Railway free tier)
    - Still provides good retrieval quality
    """
    
    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir or settings.data_dir)
        self.chunks: List[DocumentChunk] = []
        self.bm25: Optional[BM25Okapi] = None
        self.tokenized_chunks: List[List[str]] = []
        self._loaded = False
    
    def load(self) -> None:
        """Load documents and initialize search indices"""
        if self._loaded:
            return
        
        logger.info(f"Loading RAG pipeline from {self.data_dir}")
        
        # Load documents
        documents = []
        for ext in ["*.md", "*.txt"]:
            for file_path in self.data_dir.glob(ext):
                content = file_path.read_text(encoding="utf-8")
                documents.append((file_path.name, content))
                logger.info(f"Loaded {file_path.name} ({len(content)} chars)")
        
        if not documents:
            logger.warning(f"No documents found in {self.data_dir}")
            self._loaded = True
            return
        
        # Chunk documents
        for source, content in documents:
            chunks = self._chunk_document(source, content)
            self.chunks.extend(chunks)
        
        logger.info(f"Created {len(self.chunks)} chunks from {len(documents)} documents")
        
        # Build BM25 index
        self._build_bm25_index()
        self._loaded = True
        logger.info("RAG pipeline ready (BM25 mode)!")
    
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
    
    def _build_bm25_index(self) -> None:
        """Build BM25 search index"""
        if not self.chunks:
            return
        
        # Tokenize chunks (include section for better matching)
        self.tokenized_chunks = [
            self._tokenize(f"{chunk.section} {chunk.content}")
            for chunk in self.chunks
        ]
        
        self.bm25 = BM25Okapi(self.tokenized_chunks)
        logger.info(f"Built BM25 index with {len(self.chunks)} chunks")
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization with stopword removal"""
        # Common stopwords to remove from queries
        STOPWORDS = {
            'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
            'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
            'from', 'as', 'into', 'through', 'during', 'before', 'after',
            'above', 'below', 'between', 'under', 'again', 'further', 'then',
            'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all',
            'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
            'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
            'and', 'but', 'if', 'or', 'because', 'until', 'while', 'although',
            'though', 'after', 'before', 'when', 'whenever', 'where', 'wherever',
            'whether', 'which', 'while', 'who', 'whom', 'whose', 'what', 'this',
            'that', 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'been',
            'being', 'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves',
            'you', 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his',
            'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself',
            'they', 'them', 'their', 'theirs', 'themselves', 'about', 'tell',
            'please', 'help', 'know', 'get', 'find', 'show', 'give', 'let'
        }
        
        # Lowercase and split on non-alphanumeric
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        
        # Remove stopwords (but keep at least one token)
        filtered = [t for t in tokens if t not in STOPWORDS]
        
        # If all tokens were stopwords, return original tokens
        return filtered if filtered else tokens

    
    def search(self, query: str, top_k: int = None) -> List[Tuple[DocumentChunk, float]]:
        """
        BM25 retrieval - fast and effective
        """
        if not self._loaded:
            self.load()
        
        if not self.chunks or self.bm25 is None:
            return []
        
        top_k = top_k or settings.rerank_top_k
        
        # BM25 retrieval
        query_tokens = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(query_tokens)
        
        # Get top results
        top_indices = bm25_scores.argsort()[-top_k:][::-1]
        
        results = [
            (self.chunks[i], float(bm25_scores[i])) 
            for i in top_indices 
            if bm25_scores[i] > 0
        ]
        
        return results

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

    def get_context(self, query: str, max_chars: int = 3000) -> str:
        """Get formatted context string for LLM prompt"""
        results = self.search(query)
        
        if not results:
            return "No relevant information found in the knowledge base."
        
        context_parts = []
        total_chars = 0
        
        for chunk, score in results:
            # Format with clear section header
            chunk_text = f"""### {chunk.section}
(Source: {chunk.source})

{chunk.content}"""
            
            if total_chars + len(chunk_text) > max_chars:
                break
            
            context_parts.append(chunk_text)
            total_chars += len(chunk_text)
        
        return "\n\n---\n\n".join(context_parts)


# Global instance
rag_pipeline = RAGPipeline()


def initialize_rag():
    """Initialize RAG pipeline on startup"""
    try:
        rag_pipeline.load()
        logger.info("RAG pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RAG pipeline: {e}")
