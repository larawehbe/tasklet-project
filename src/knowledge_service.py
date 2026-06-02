"""Knowledge base service — RAG retrieval for Tasklet help articles.

Two entry points:

  build_index() — reads markdown articles from data/knowledge/, chunks them
    by section, embeds each chunk with sentence-transformers, and stores
    everything in a ChromaDB collection on disk. Run this once (or whenever
    you add/edit articles). No API calls, no cost.

  search(query, n_results) — embeds the query string, searches ChromaDB
    for the closest chunks, and returns them as a list of dicts. Called at
    runtime by the agent's tool dispatch when Claude decides to search the
    knowledge base.

The embedding model (all-MiniLM-L6-v2) runs locally. ChromaDB persists to
data/chroma/. Neither costs tokens or money.
"""

from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Paths — same pattern as db.py, relative to the project root.
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge"
CHROMA_DIR = PROJECT_ROOT / "data" / "chroma"
COLLECTION_NAME = "knowledge_base"

# ---------------------------------------------------------------------------
# Models — loaded once per process, reused across calls.
#
# _model and _collection start as None. The first call to search() or
# build_index() initializes them. This avoids loading the 80MB model at
# import time (which would slow down every CLI command, even `init-db`).
# ---------------------------------------------------------------------------

_model: SentenceTransformer | None = None
_collection: chromadb.Collection | None = None


def _get_model() -> SentenceTransformer:
    """Load the embedding model (once per process).

    all-MiniLM-L6-v2 is a small, fast model that produces 384-dimensional
    vectors. It's good enough for semantic search over short documents.
    The first call downloads ~80MB if the model isn't cached locally.
    After that it loads from disk in ~1 second.
    """
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_collection() -> chromadb.Collection:
    """Open (or create) the ChromaDB collection (once per process).

    PersistentClient stores data in data/chroma/ on disk, so the index
    survives restarts. get_or_create_collection returns the existing
    collection if it exists, or creates an empty one.
    """
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_or_create_collection(COLLECTION_NAME)
    return _collection


# ---------------------------------------------------------------------------
# Chunking — split a markdown article into sections.
# ---------------------------------------------------------------------------

def _chunk_article(filepath: Path) -> list[dict]:
    """Split one markdown file into chunks, one per ## section.

    Returns a list of dicts, each with:
      - "id": a unique string like "api-rate-limits__current-limits"
      - "text": the chunk content with the article title prepended
      - "source": the filename (e.g., "api-rate-limits.md")

    Why prepend the title? Without it a chunk like "Free plan: 60 requests
    per minute" loses context — the embedding model wouldn't know this is
    about rate limits. Prepending "API Rate Limits" to every chunk keeps
    the meaning intact.

    How the split works:
      1. Read the file.
      2. Find the # title (first line starting with "# ").
      3. Split the rest on "## " headers.
      4. Each split becomes a chunk. If there's text before the first ##,
         that's the intro chunk.
    """
    text = filepath.read_text().strip()
    lines = text.split("\n")

    # --- Extract the article title (the # line) ---
    title = ""
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line.lstrip("# ").strip()
            body_start = i + 1
            break

    # --- Rejoin everything after the title ---
    body = "\n".join(lines[body_start:]).strip()

    # --- Split on ## headers ---
    # We split on "\n## " so we get sections. The first element is any
    # text before the first ## (the intro paragraph).
    raw_sections = body.split("\n## ")

    chunks = []
    source = filepath.name  # e.g., "api-rate-limits.md"
    stem = filepath.stem     # e.g., "api-rate-limits"

    for i, section in enumerate(raw_sections):
        section = section.strip()
        if not section:
            continue

        # The first section is the intro (no ## header).
        # All others start with the header text (because we split on "\n## ").
        if i == 0:
            chunk_id = f"{stem}__intro"
            # Prepend the article title for context.
            chunk_text = f"{title}\n\n{section}"
        else:
            # The section starts with the header text, e.g., "Current limits\n..."
            # Extract it for the chunk ID.
            first_line = section.split("\n")[0].strip()
            slug = first_line.lower().replace(" ", "-")[:40]
            chunk_id = f"{stem}__{slug}"
            # Prepend the article title AND keep the section header.
            chunk_text = f"{title}\n\n{first_line}\n\n{section[len(first_line):].strip()}"

        chunks.append({
            "id": chunk_id,
            "text": chunk_text,
            "source": source,
        })

    return chunks


# ---------------------------------------------------------------------------
# Build — the offline indexing step. Run once.
# ---------------------------------------------------------------------------

def build_index() -> int:
    """Read all articles, chunk them, embed them, store in ChromaDB.

    Returns the total number of chunks indexed.

    This function is destructive: it deletes the existing collection and
    rebuilds from scratch. This is the simplest approach and fine for a
    small corpus. For a large production corpus you would do incremental
    updates instead.

    Steps:
      1. Find all .md files in data/knowledge/.
      2. Chunk each file into sections.
      3. Embed every chunk using sentence-transformers (locally, free).
      4. Store chunks + embeddings in ChromaDB.
    """
    global _collection

    model = _get_model()

    # --- Delete and recreate the collection for a clean rebuild ---
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # Collection didn't exist yet — that's fine.
    _collection = client.create_collection(COLLECTION_NAME)

    # --- Gather all chunks from all articles ---
    all_chunks = []
    for filepath in sorted(KNOWLEDGE_DIR.glob("*.md")):
        chunks = _chunk_article(filepath)
        all_chunks.extend(chunks)

    if not all_chunks:
        return 0

    # --- Embed all chunks in one batch (faster than one at a time) ---
    texts = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts).tolist()
    # model.encode returns a numpy array of shape (n_chunks, 384).
    # .tolist() converts it to a plain Python list of lists, which
    # is what ChromaDB expects.

    # --- Store in ChromaDB ---
    _collection.add(
        ids=[c["id"] for c in all_chunks],
        documents=texts,
        embeddings=embeddings,
        metadatas=[{"source": c["source"]} for c in all_chunks],
    )

    return len(all_chunks)


# ---------------------------------------------------------------------------
# Search — called at runtime by the agent tool.
# ---------------------------------------------------------------------------

def search(query: str, n_results: int = 3) -> list[dict]:
    """Embed the query and return the closest chunks from ChromaDB.

    Returns a list of dicts, each with:
      - "text": the chunk content
      - "source": which article it came from
      - "score": the distance (lower = more similar)

    Steps:
      1. Embed the query string using the same model that indexed the chunks.
         This is critical — query and documents MUST use the same model,
         otherwise the vectors live in different spaces and comparison is
         meaningless.
      2. Ask ChromaDB for the n closest chunks by cosine distance.
      3. Package the results into a clean list of dicts.
    """
    model = _get_model()
    collection = _get_collection()

    # --- Embed the query ---
    query_embedding = model.encode(query).tolist()
    # .tolist() converts the numpy array to a plain Python list.

    # --- Search ChromaDB ---
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
    )
    # results is a dict with parallel lists:
    #   results["documents"][0] = ["chunk text 1", "chunk text 2", ...]
    #   results["metadatas"][0] = [{"source": "file1.md"}, {"source": "file2.md"}, ...]
    #   results["distances"][0] = [0.42, 0.55, ...]
    # The [0] is because we passed one query. If we passed multiple queries
    # we'd get results[0], results[1], etc.

    # --- Package into a clean list ---
    output = []
    for text, metadata, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        output.append({
            "text": text,
            "source": metadata["source"],
            "score": round(distance, 4),
        })

    return output