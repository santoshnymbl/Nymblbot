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
        assert ceo_chunks[0].section_path == "Company Overview > Leadership Team > CEO / Co-Founder"

    def test_chunk_has_source_file_metadata(self, temp_data_dir):
        """Chunks should know which file they came from"""
        pipeline = RAGPipeline(data_dir=temp_data_dir)
        pipeline.load()

        wiki_chunks = [c for c in pipeline.chunks if c.source == "nymbl_wiki.md"]
        handbook_chunks = [c for c in pipeline.chunks if c.source == "nymbl_handbook.md"]
        assert len(wiki_chunks) > 0
        assert len(handbook_chunks) > 0

    def test_chunk_id_is_sequential(self, temp_data_dir):
        """Chunk IDs should be sequential within a source file"""
        pipeline = RAGPipeline(data_dir=temp_data_dir)
        pipeline.load()

        wiki_chunks = [c for c in pipeline.chunks if c.source == "nymbl_wiki.md"]
        ids = [c.chunk_id for c in wiki_chunks]
        assert ids == list(range(len(ids))), "Chunk IDs should be sequential"
