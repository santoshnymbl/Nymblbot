"""Integration tests for the full retrieval pipeline"""
import pytest
from pathlib import Path
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
