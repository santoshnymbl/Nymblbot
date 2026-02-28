"""Tests for RAG search with query expansion integration"""
import pytest
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
        """get_context_with_sources should return both context text and source metadata"""
        pipeline = RAGPipeline(data_dir=temp_data_dir)
        pipeline.load()

        context, sources = pipeline.get_context_with_sources("PTO policy")
        assert len(context) > 0
        assert len(sources) > 0
        assert all("source" in s and "section_path" in s for s in sources)
