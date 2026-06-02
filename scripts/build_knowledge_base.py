"""Build the knowledge base index.

Run once after generating the articles (or whenever you add/edit articles):

    uv run python scripts/build_knowledge_base.py

What it does:
  1. Reads every .md file in data/knowledge/
  2. Splits each file into chunks (one per ## section)
  3. Embeds each chunk using sentence-transformers (locally, free)
  4. Stores chunks + embeddings in ChromaDB at data/chroma/

The first run downloads the embedding model (~80MB). After that it loads
from cache in about 1 second.

This script is destructive — it wipes the existing ChromaDB collection
and rebuilds from scratch. Safe to run repeatedly.
"""

from src.knowledge_service import build_index

if __name__ == "__main__":
    print("Building knowledge base index...")
    count = build_index()
    print(f"Done — indexed {count} chunks into data/chroma/")