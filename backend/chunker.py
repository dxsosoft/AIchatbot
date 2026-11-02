"""
Document chunking engine.
Splits extracted document sections into overlapping, semantically coherent chunks
while preserving strict provenance metadata (filename, page, sheet, section, chunk index).
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from backend.extractors.base import ExtractedDocument, ExtractedSection
from backend.config import CHUNK_SIZE, CHUNK_OVERLAP


class DocumentChunk(BaseModel):
    """Searchable chunk of text with rich source attribution metadata."""
    chunk_id: str
    doc_id: str
    filename: str
    chunk_index: int
    text: str
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    section_title: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


def split_text_recursive(
    text: str,
    max_chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
) -> List[str]:
    """
    Recursively splits text into overlapping chunks using natural delimiters:
    paragraphs -> sentences -> words.
    """
    clean_text = text.strip()
    if not clean_text:
        return []

    if len(clean_text) <= max_chunk_size:
        return [clean_text]

    chunks: List[str] = []
    delimiters = ["\n\n", "\n", ". ", "; ", ", ", " "]

    def _split(s: str, delim_idx: int) -> List[str]:
        if delim_idx >= len(delimiters):
            # Hard character split fallback
            return [s[i:i + max_chunk_size] for i in range(0, len(s), max_chunk_size - overlap)]

        delim = delimiters[delim_idx]
        parts = s.split(delim)
        result = []
        current = ""

        for part in parts:
            candidate = f"{current}{delim}{part}" if current else part
            if len(candidate) <= max_chunk_size:
                current = candidate
            else:
                if current:
                    result.append(current.strip())
                if len(part) > max_chunk_size:
                    # Delimiter unit itself is too large, recurse with next finer delimiter
                    sub_splits = _split(part, delim_idx + 1)
                    result.extend(sub_splits)
                    current = ""
                else:
                    current = part

        if current and current.strip():
            result.append(current.strip())

        return result

    raw_splits = _split(clean_text, 0)

    # Apply sliding window overlap between splits
    if not raw_splits:
        return []

    processed_chunks: List[str] = []
    for idx, piece in enumerate(raw_splits):
        if idx > 0 and overlap > 0:
            prev_piece = raw_splits[idx - 1]
            overlap_prefix = prev_piece[-overlap:]
            combined = f"...{overlap_prefix} {piece}"
            processed_chunks.append(combined)
        else:
            processed_chunks.append(piece)

    return processed_chunks


def chunk_document(
    doc: ExtractedDocument,
    doc_id: str,
    max_chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
) -> List[DocumentChunk]:
    """
    Transforms an ExtractedDocument into an indexed list of DocumentChunks.
    Preserves exact page numbers, sheet names, and section titles.
    """
    chunks: List[DocumentChunk] = []
    chunk_counter = 0

    for section in doc.sections:
        split_texts = split_text_recursive(section.text, max_chunk_size=max_chunk_size, overlap=overlap)

        for text_part in split_texts:
            if not text_part.strip():
                continue

            chunk_id = f"{doc_id}_c{chunk_counter}"
            chunk = DocumentChunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                filename=doc.filename,
                chunk_index=chunk_counter,
                text=text_part,
                page_number=section.page_number,
                sheet_name=section.sheet_name,
                section_title=section.section_title,
                metadata={
                    **section.metadata,
                    "file_type": doc.file_type,
                    "char_count": len(text_part),
                    "word_count": len(text_part.split())
                }
            )
            chunks.append(chunk)
            chunk_counter += 1

    return chunks
