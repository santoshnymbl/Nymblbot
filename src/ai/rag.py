"""
Miss Minutes - RAG Pipeline
BM25 Retrieval + Cross-Encoder Reranking
"""
import os
import re
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """A chunk of text from a document"""
    content: str
    source: str
    section: str
    chunk_id: int


class RAGPipeline:
    """
    Production RAG Pipeline
    - BM25 for fast initial retrieval
    - Cross-encoder reranking for precision
    """
    
    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir or settings.data_dir)
        self.chunks: List[DocumentChunk] = []
        self.bm25: Optional[BM25Okapi] = None
        self.reranker: Optional[CrossEncoder] = None
        self.tokenized_chunks: List[List[str]] = []
        self._loaded = False
    
    def load(self) -> None:
        """Load documents and initialize search indices"""
        if self._loaded:
            return
        
        logger.info(f"Loading RAG pipeline from {self.data_dir}")
        
        # Load reranker model
        logger.info("Loading reranker model...")
        try:
            self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
            logger.info("Reranker loaded: cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception as e:
            logger.warning(f"Could not load reranker: {e}. Falling back to BM25 only.")
            self.reranker = None
        
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
        logger.info("RAG pipeline ready!")
    
    def _chunk_document(self, source: str, content: str) -> List[DocumentChunk]:
        """Split document into searchable chunks by section"""
        chunks = []
        
        # Split by headers (# ## ###)
        sections = re.split(r'\n(?=#{1,3}\s+)', content)
        
        chunk_id = 0
        for section in sections:
            section = section.strip()
            if not section:
                continue
            
            # Extract header
            header_match = re.match(r'^(#{1,3})\s+(.+?)(?:\n|$)', section)
            if header_match:
                header = header_match.group(2).strip()
                body = section[header_match.end():].strip()
            else:
                header = "General"
                body = section
            
            # Skip empty sections
            if not body:
                continue
            
            # If section is too long, split by paragraphs
            if len(body) > settings.chunk_size:
                paragraphs = body.split("\n\n")
                current_chunk = ""
                
                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue
                    
                    if len(current_chunk) + len(para) < settings.chunk_size:
                        current_chunk += para + "\n\n"
                    else:
                        if current_chunk.strip():
                            chunks.append(DocumentChunk(
                                content=current_chunk.strip(),
                                source=source,
                                section=header,
                                chunk_id=chunk_id
                            ))
                            chunk_id += 1
                        current_chunk = para + "\n\n"
                
                if current_chunk.strip():
                    chunks.append(DocumentChunk(
                        content=current_chunk.strip(),
                        source=source,
                        section=header,
                        chunk_id=chunk_id
                    ))
                    chunk_id += 1
            else:
                chunks.append(DocumentChunk(
                    content=body,
                    source=source,
                    section=header,
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
        """Simple tokenization"""
        # Lowercase and split on non-alphanumeric
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        return tokens
    
    def search(self, query: str, top_k: int = None) -> List[Tuple[DocumentChunk, float]]:
        """
        Two-stage retrieval:
        1. BM25 retrieval (fast, get candidates)
        2. Reranker (precise, select best)
        """
        if not self._loaded:
            self.load()
        
        if not self.chunks or self.bm25 is None:
            return []
        
        top_k = top_k or settings.rerank_top_k
        
        # Stage 1: BM25 retrieval
        query_tokens = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(query_tokens)
        
        # Get top candidates for reranking
        bm25_top_k = settings.bm25_top_k
        top_indices = bm25_scores.argsort()[-bm25_top_k:][::-1]
        
        candidates = [(self.chunks[i], bm25_scores[i]) for i in top_indices if bm25_scores[i] > 0]
        
        if not candidates:
            return []
        
        # Stage 2: Reranking (if available)
        if self.reranker and len(candidates) > 1:
            try:
                pairs = [(query, chunk.content) for chunk, _ in candidates]
                rerank_scores = self.reranker.predict(pairs)
                
                # Combine with rerank scores
                reranked = sorted(
                    zip([c for c, _ in candidates], rerank_scores),
                    key=lambda x: x[1],
                    reverse=True
                )
                
                return reranked[:top_k]
            except Exception as e:
                logger.warning(f"Reranking failed: {e}. Using BM25 scores only.")
        
        # Fallback to BM25 scores only
        return candidates[:top_k]
    
    def get_context(self, query: str, max_chars: int = 3000) -> str:
        """Get formatted context string for LLM prompt"""
        results = self.search(query)
        
        if not results:
            return "No relevant information found in the knowledge base."
        
        context_parts = []
        total_chars = 0
        
        for chunk, score in results:
            chunk_text = f"[Source: {chunk.source} | Section: {chunk.section}]\n{chunk.content}"
            
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


if __name__ == "__main__":
    # Test the RAG pipeline
    logging.basicConfig(level=logging.INFO)
    
    pipeline = RAGPipeline("data")
    pipeline.load()
    
    test_queries = [
        "What is WGLL?",
        "How do I submit PTO?",
        "Who is the CEO?",
        "What are Nymbl's tenets?",
        "How do I log time?"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print("="*60)
        
        results = pipeline.search(query, top_k=3)
        for chunk, score in results:
            print(f"\n[Score: {score:.3f}] {chunk.section}")
            print(chunk.content[:200] + "...")
