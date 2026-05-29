"""
chunker.py — Split policy documents into overlapping chunks for embedding.

Target chunk size: ~200 tokens (~800 chars) with 50-char overlap.
"""

from __future__ import annotations

CHUNK_SIZE = 800    # characters
OVERLAP = 100       # characters


def chunk_text(text: str, title: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[dict]:
    """
    Split text into overlapping chunks.
    Returns list of dicts with: title, content, chunk_index
    """
    # Clean up whitespace
    text = " ".join(text.split())
    chunks = []
    start = 0
    index = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at a sentence boundary
        if end < len(text):
            for boundary in [". ", ".\n", "! ", "? "]:
                pos = text.rfind(boundary, start, end)
                if pos != -1:
                    end = pos + 2
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append({
                "title": f"{title} (chunk {index + 1})",
                "content": chunk,
                "chunk_index": index,
            })

        # Always advance — if end - overlap <= start, jump past end to avoid infinite loop
        new_start = end - overlap
        start = new_start if new_start > start else end
        index += 1

    return chunks


def chunk_markdown_file(filepath: str) -> list[dict]:
    """Read a markdown file and return chunks with metadata."""
    from pathlib import Path
    path = Path(filepath)
    text = path.read_text(encoding="utf-8")
    title = path.stem.replace("_", " ").title()

    # Extract category from filename
    name = path.stem
    if "aml" in name or "threshold" in name:
        category = "aml"
    elif "velocity" in name:
        category = "velocity"
    elif "geographic" in name:
        category = "geographic"
    elif "structuring" in name:
        category = "aml"
    elif "customer" in name or "communication" in name:
        category = "fraud"
    else:
        category = "fraud"

    chunks = chunk_text(text, title)
    for chunk in chunks:
        chunk["category"] = category
        chunk["source_file"] = path.name

    return chunks
