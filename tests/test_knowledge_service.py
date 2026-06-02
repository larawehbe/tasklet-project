"""Tests for the knowledge base service and tool dispatch.

Three groups:

  1. Chunking — does _chunk_article split markdown correctly?
  2. Search — does build_index + search return relevant results?
  3. Dispatch — does the tool dispatch route search_knowledge_base
     correctly, including error handling for bad input?

No live API calls. No internet. The embedding model runs locally.
ChromaDB uses a temporary directory that is cleaned up after each test.

These tests are slower than the ticket tests (~2-3 seconds) because
loading the sentence-transformers model takes about 1 second. That's
fine — they only run when you change the knowledge service.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.knowledge_service import (
    _chunk_article,
    build_index,
    search,
    COLLECTION_NAME,
)
from src.models import ToolUse
from src.tools import dispatch


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def tmp_knowledge_dir(tmp_path):
    """Create a temporary directory with two small test articles.

    We use tiny articles (not the full 18) so tests are fast and
    we control exactly what content exists. If a test needs specific
    content, it knows exactly what's here.
    """
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()

    # Article 1: has an intro and two ## sections
    (knowledge_dir / "jira-setup.md").write_text(
        "# Jira Integration Setup\n\n"
        "Connect Jira to Tasklet for bidirectional sync.\n\n"
        "## How to connect\n\n"
        "Go to Settings, click Connect Jira, sign in with Atlassian.\n\n"
        "## Troubleshooting\n\n"
        "If sync stops, re-authenticate your Jira connection.\n"
    )

    # Article 2: different topic so we can test search relevance
    (knowledge_dir / "billing-faq.md").write_text(
        "# Billing and Plans\n\n"
        "Tasklet offers Free, Team, and Enterprise plans.\n\n"
        "## Adding seats\n\n"
        "Go to Settings, Billing, Seats, click Add seat.\n\n"
        "## Refunds\n\n"
        "Tasklet does not offer partial refunds for unused seats.\n"
    )

    return knowledge_dir


@pytest.fixture
def indexed_knowledge(tmp_path, tmp_knowledge_dir):
    """Build a ChromaDB index from the test articles in a temp directory.

    Patches the module-level paths so build_index() and search() use
    our temporary directories instead of the real data/ folder. Also
    resets the module-level _collection so each test gets a fresh index.
    """
    chroma_dir = tmp_path / "chroma"

    with patch("src.knowledge_service.KNOWLEDGE_DIR", tmp_knowledge_dir), \
         patch("src.knowledge_service.CHROMA_DIR", chroma_dir), \
         patch("src.knowledge_service._collection", None):
        count = build_index()
        # After build_index, _collection is set. We need search() to
        # use the same patched CHROMA_DIR, so we yield inside the patch.
        yield count


# --------------------------------------------------------------------------
# 1. Chunking tests
# --------------------------------------------------------------------------

class TestChunking:
    """Verify that _chunk_article splits markdown correctly."""

    def test_splits_on_h2_headers(self, tmp_knowledge_dir):
        """Each ## section becomes its own chunk, plus the intro."""
        filepath = tmp_knowledge_dir / "jira-setup.md"
        chunks = _chunk_article(filepath)

        # Intro + "How to connect" + "Troubleshooting" = 3 chunks
        assert len(chunks) == 3

    def test_intro_chunk_has_title(self, tmp_knowledge_dir):
        """The intro chunk should contain the article title."""
        filepath = tmp_knowledge_dir / "jira-setup.md"
        chunks = _chunk_article(filepath)

        intro = chunks[0]
        assert "Jira Integration Setup" in intro["text"]
        assert "bidirectional sync" in intro["text"]

    def test_section_chunk_has_title_prepended(self, tmp_knowledge_dir):
        """Every section chunk should have the article title prepended
        for embedding context."""
        filepath = tmp_knowledge_dir / "jira-setup.md"
        chunks = _chunk_article(filepath)

        # The "How to connect" section (index 1) should start with the title
        how_to = chunks[1]
        assert "Jira Integration Setup" in how_to["text"]
        assert "Settings" in how_to["text"]

    def test_chunk_ids_are_unique(self, tmp_knowledge_dir):
        """Every chunk must have a unique id."""
        filepath = tmp_knowledge_dir / "jira-setup.md"
        chunks = _chunk_article(filepath)

        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_chunk_source_is_filename(self, tmp_knowledge_dir):
        """The source metadata should be the filename, not the full path."""
        filepath = tmp_knowledge_dir / "jira-setup.md"
        chunks = _chunk_article(filepath)

        for chunk in chunks:
            assert chunk["source"] == "jira-setup.md"


# --------------------------------------------------------------------------
# 2. Search tests (build + query round-trip)
# --------------------------------------------------------------------------

class TestSearch:
    """Verify that build_index + search returns relevant results."""

    def test_build_index_returns_chunk_count(self, tmp_path, tmp_knowledge_dir):
        """build_index should return the total number of chunks indexed."""
        chroma_dir = tmp_path / "chroma"

        with patch("src.knowledge_service.KNOWLEDGE_DIR", tmp_knowledge_dir), \
             patch("src.knowledge_service.CHROMA_DIR", chroma_dir), \
             patch("src.knowledge_service._collection", None):
            count = build_index()

        # 2 articles x 3 chunks each = 6
        assert count == 6

    def test_search_returns_relevant_results(self, tmp_path, tmp_knowledge_dir):
        """Searching for "Jira" should return Jira chunks, not billing."""
        chroma_dir = tmp_path / "chroma"

        with patch("src.knowledge_service.KNOWLEDGE_DIR", tmp_knowledge_dir), \
             patch("src.knowledge_service.CHROMA_DIR", chroma_dir), \
             patch("src.knowledge_service._collection", None):
            build_index()
            results = search("how do I connect Jira?", n_results=2)

        # Should get results back
        assert len(results) == 2

        # The top result should be from the Jira article, not billing
        assert results[0]["source"] == "jira-setup.md"

    def test_search_result_shape(self, tmp_path, tmp_knowledge_dir):
        """Each result should have text, source, and score keys."""
        chroma_dir = tmp_path / "chroma"

        with patch("src.knowledge_service.KNOWLEDGE_DIR", tmp_knowledge_dir), \
             patch("src.knowledge_service.CHROMA_DIR", chroma_dir), \
             patch("src.knowledge_service._collection", None):
            build_index()
            results = search("billing", n_results=1)

        result = results[0]
        assert "text" in result
        assert "source" in result
        assert "score" in result
        assert isinstance(result["score"], float)


# --------------------------------------------------------------------------
# 3. Dispatch tests
# --------------------------------------------------------------------------

class TestDispatch:
    """Verify that dispatch() routes search_knowledge_base correctly."""

    def test_dispatch_returns_results(self, conn, tmp_path, tmp_knowledge_dir):
        """dispatch should return search results for a valid query."""
        chroma_dir = tmp_path / "chroma"

        with patch("src.knowledge_service.KNOWLEDGE_DIR", tmp_knowledge_dir), \
             patch("src.knowledge_service.CHROMA_DIR", chroma_dir), \
             patch("src.knowledge_service._collection", None):
            build_index()

            tool_use = ToolUse(
                id="test-123",
                name="search_knowledge_base",
                input={"query": "Jira setup"},
            )
            result = dispatch(conn, user_id=1, tool_use=tool_use)

        assert not result.is_error
        assert "results" in result.content

    def test_dispatch_rejects_empty_query(self, conn):
        """dispatch should return an error for an empty query string."""
        tool_use = ToolUse(
            id="test-456",
            name="search_knowledge_base",
            input={"query": ""},
        )
        result = dispatch(conn, user_id=1, tool_use=tool_use)

        assert result.is_error
        assert "non-empty" in result.content

    def test_dispatch_rejects_missing_query(self, conn):
        """dispatch should return an error when query is missing entirely."""
        tool_use = ToolUse(
            id="test-789",
            name="search_knowledge_base",
            input={},
        )
        result = dispatch(conn, user_id=1, tool_use=tool_use)

        assert result.is_error