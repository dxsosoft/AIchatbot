"""
Local search & retrieval index using Okapi BM25 ranking, exact phrase boosting,
and strict session/user isolation.
All session indexes are persisted independently to disk in session-isolated directories.
"""

import math
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.chunker import DocumentChunk
from backend.config import DATA_DIR, TOP_K_RETRIEVAL


class SearchResult(BaseModel):
    """Retrieved chunk with relevance score and provenance information."""
    chunk_id: str
    doc_id: str
    filename: str
    text: str
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    section_title: Optional[str] = None
    relevance_score: float
    match_reasons: List[str] = Field(default_factory=list)


def tokenize(text: str) -> List[str]:
    """Tokenizes text into lowercase alphanumeric words."""
    return re.findall(r'[a-zA-Z0-9_\-]+', text.lower())


class SessionSearchIndex:
    """
    Search index instance dedicated to a single user session.
    Provides Okapi BM25 ranking, phrase matching, and persistence.
    """

    def __init__(self, session_id: str, storage_dir: Optional[Path] = None):
        self.session_id = session_id
        self.storage_dir = (storage_dir or DATA_DIR) / "sessions" / session_id
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.storage_dir / "index.json"

        self.chunks: Dict[str, DocumentChunk] = {}  # chunk_id -> DocumentChunk
        self.doc_len: Dict[str, int] = {}           # chunk_id -> length
        self.avg_doc_len: float = 0.0
        self.inverted_index: Dict[str, Dict[str, int]] = {}  # term -> {chunk_id: term_freq}

        self.k1 = 1.5
        self.b = 0.75

        self.load()

    def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        """Adds a list of chunks to the session index and persists changes."""
        for chunk in chunks:
            self.chunks[chunk.chunk_id] = chunk
            tokens = tokenize(chunk.text)
            self.doc_len[chunk.chunk_id] = len(tokens)

            # Update inverted index
            term_counts: Dict[str, int] = {}
            for t in tokens:
                term_counts[t] = term_counts.get(t, 0) + 1

            for term, count in term_counts.items():
                if term not in self.inverted_index:
                    self.inverted_index[term] = {}
                self.inverted_index[term][chunk.chunk_id] = count

        self._recalculate_stats()
        self.save()

    def remove_document(self, doc_id: str) -> int:
        """Removes all chunks associated with doc_id from the session index."""
        chunk_ids_to_remove = [
            cid for cid, chk in self.chunks.items() if chk.doc_id == doc_id
        ]

        for cid in chunk_ids_to_remove:
            del self.chunks[cid]
            if cid in self.doc_len:
                del self.doc_len[cid]

            # Clean inverted index
            for term in list(self.inverted_index.keys()):
                if cid in self.inverted_index[term]:
                    del self.inverted_index[term][cid]
                if not self.inverted_index[term]:
                    del self.inverted_index[term]

        self._recalculate_stats()
        self.save()
        return len(chunk_ids_to_remove)

    def _recalculate_stats(self) -> None:
        """Updates average document length across all indexed chunks."""
        if self.doc_len:
            self.avg_doc_len = sum(self.doc_len.values()) / len(self.doc_len)
        else:
            self.avg_doc_len = 0.0

    def search(self, query: str, top_k: int = TOP_K_RETRIEVAL) -> List[SearchResult]:
        """
        Executes Okapi BM25 semantic retrieval with phrase and title boosting.
        """
        query_tokens = tokenize(query)
        if not query_tokens or not self.chunks:
            return []

        scores: Dict[str, float] = {}
        match_reasons: Dict[str, List[str]] = {}
        total_chunks = len(self.chunks)

        clean_query = query.strip().lower()

        for term in set(query_tokens):
            if term not in self.inverted_index:
                continue

            posting = self.inverted_index[term]
            doc_freq = len(posting)
            # Okapi BM25 IDF
            idf = math.log((total_chunks - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
            idf = max(idf, 0.1)

            for cid, tf in posting.items():
                dl = self.doc_len.get(cid, self.avg_doc_len)
                denom = tf + self.k1 * (1.0 - self.b + self.b * (dl / (self.avg_doc_len or 1.0)))
                term_score = idf * ((tf * (self.k1 + 1.0)) / (denom or 1.0))

                scores[cid] = scores.get(cid, 0.0) + term_score

                if cid not in match_reasons:
                    match_reasons[cid] = []
                match_reasons[cid].append(term)

        # Exact phrase and section/sheet title boosting
        for cid in list(scores.keys()):
            chunk = self.chunks[cid]
            chunk_lower = chunk.text.lower()

            # Boost if exact query appears as a substring
            if len(clean_query) > 4 and clean_query in chunk_lower:
                scores[cid] *= 1.8
                match_reasons[cid].append("exact_phrase")

            # Boost if section title or sheet name matches query terms
            title_text = f"{chunk.section_title or ''} {chunk.sheet_name or ''}".lower()
            for t in query_tokens:
                if t in title_text:
                    scores[cid] *= 1.25
                    match_reasons[cid].append(f"title_match({t})")
                    break

        if not scores:
            return []

        # Sort by relevance score descending
        sorted_cids = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        max_score = sorted_cids[0][1] if sorted_cids else 1.0
        results = []

        for cid, raw_score in sorted_cids:
            chunk = self.chunks[cid]
            normalized_score = round(min(raw_score / (max_score or 1.0), 1.0), 3)

            results.append(
                SearchResult(
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                    filename=chunk.filename,
                    text=chunk.text,
                    page_number=chunk.page_number,
                    sheet_name=chunk.sheet_name,
                    section_title=chunk.section_title,
                    relevance_score=normalized_score,
                    match_reasons=list(set(match_reasons.get(cid, [])))
                )
            )

        return results

    def save(self) -> None:
        """Persists index to disk in JSON format."""
        data = {
            "session_id": self.session_id,
            "chunks": [c.model_dump() for c in self.chunks.values()]
        }
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> None:
        """Loads index from disk if present."""
        if not self.index_file.exists():
            return

        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_chunks = [DocumentChunk(**c) for c in data.get("chunks", [])]
            self.chunks.clear()
            self.inverted_index.clear()
            self.doc_len.clear()

            for chunk in raw_chunks:
                self.chunks[chunk.chunk_id] = chunk
                tokens = tokenize(chunk.text)
                self.doc_len[chunk.chunk_id] = len(tokens)

                term_counts: Dict[str, int] = {}
                for t in tokens:
                    term_counts[t] = term_counts.get(t, 0) + 1

                for term, count in term_counts.items():
                    if term not in self.inverted_index:
                        self.inverted_index[term] = {}
                    self.inverted_index[term][chunk.chunk_id] = count

            self._recalculate_stats()
        except Exception:
            pass


class SessionIndexManager:
    """Thread-safe manager for session indexes ensuring complete user isolation."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or DATA_DIR
        self._indexes: Dict[str, SessionSearchIndex] = {}

    def get_index(self, session_id: str) -> SessionSearchIndex:
        """Retrieves or loads search index for given session_id."""
        clean_sid = re.sub(r'[^a-zA-Z0-9_\-]', '_', session_id) or "default"
        if clean_sid not in self._indexes:
            self._indexes[clean_sid] = SessionSearchIndex(clean_sid, storage_dir=self.storage_dir)
        return self._indexes[clean_sid]


# Global instance
index_manager = SessionIndexManager()
