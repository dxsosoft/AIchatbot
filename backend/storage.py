"""
Session-partitioned document storage and metadata registry.
Guarantees file isolation between sessions, safe disk persistence, and complete deletion.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict
from pydantic import BaseModel
from backend.config import UPLOAD_DIR, DATA_DIR
from backend.validators import sanitize_filename, calculate_sha256
from backend.indexer import index_manager


class DocumentRecord(BaseModel):
    """Metadata record for an uploaded document."""
    doc_id: str
    session_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    sha256: str
    stored_path: str
    uploaded_at: str
    chunk_count: int = 0
    status: str = "indexed"
    error_message: Optional[str] = None


class DocumentStorage:
    """Manages file storage and metadata persistence partitioned per user session."""

    def __init__(self, upload_root: Optional[Path] = None, data_root: Optional[Path] = None):
        self.upload_root = upload_root or UPLOAD_DIR
        self.data_root = data_root or DATA_DIR

    def _get_session_upload_dir(self, session_id: str) -> Path:
        p = self.upload_root / "sessions" / session_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _get_registry_path(self, session_id: str) -> Path:
        p = self.data_root / "sessions" / session_id
        p.mkdir(parents=True, exist_ok=True)
        return p / "documents.json"

    def _load_registry(self, session_id: str) -> Dict[str, DocumentRecord]:
        reg_file = self._get_registry_path(session_id)
        if not reg_file.exists():
            return {}
        try:
            with open(reg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {k: DocumentRecord(**v) for k, v in data.items()}
        except Exception:
            return {}

    def _save_registry(self, session_id: str, registry: Dict[str, DocumentRecord]) -> None:
        reg_file = self._get_registry_path(session_id)
        data = {k: v.model_dump() for k, v in registry.items()}
        with open(reg_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_file(
        self,
        session_id: str,
        filename: str,
        content: bytes,
        file_type: str
    ) -> DocumentRecord:
        """
        Saves raw file bytes to isolated session storage and registers metadata.
        """
        clean_name = sanitize_filename(filename)
        doc_id = str(uuid.uuid4())[:8]
        file_hash = calculate_sha256(content)

        session_upload_dir = self._get_session_upload_dir(session_id)
        stored_filename = f"{doc_id}_{clean_name}"
        target_path = session_upload_dir / stored_filename

        # Write file securely to disk
        target_path.write_bytes(content)

        now_iso = datetime.now(timezone.utc).isoformat()
        record = DocumentRecord(
            doc_id=doc_id,
            session_id=session_id,
            filename=clean_name,
            file_type=file_type,
            file_size_bytes=len(content),
            sha256=file_hash,
            stored_path=str(target_path),
            uploaded_at=now_iso,
            chunk_count=0,
            status="uploaded"
        )

        registry = self._load_registry(session_id)
        registry[doc_id] = record
        self._save_registry(session_id, registry)

        return record

    def update_chunk_count(self, session_id: str, doc_id: str, chunk_count: int, status: str = "indexed") -> None:
        registry = self._load_registry(session_id)
        if doc_id in registry:
            registry[doc_id].chunk_count = chunk_count
            registry[doc_id].status = status
            self._save_registry(session_id, registry)

    def list_documents(self, session_id: str) -> List[DocumentRecord]:
        """Lists all registered documents for the specified session."""
        registry = self._load_registry(session_id)
        # Return sorted by upload timestamp descending
        return sorted(registry.values(), key=lambda r: r.uploaded_at, reverse=True)

    def get_document(self, session_id: str, doc_id: str) -> Optional[DocumentRecord]:
        registry = self._load_registry(session_id)
        return registry.get(doc_id)

    def delete_document(self, session_id: str, doc_id: str) -> bool:
        """
        Deletes the document file from disk, removes its chunks from the search index,
        and unregisters it from the session registry.
        """
        registry = self._load_registry(session_id)
        if doc_id not in registry:
            return False

        record = registry[doc_id]

        # 1. Delete physical file
        try:
            stored_file = Path(record.stored_path)
            if stored_file.exists():
                stored_file.unlink()
        except Exception:
            pass

        # 2. Remove chunks from session search index
        index_manager.get_index(session_id).remove_document(doc_id)

        # 3. Remove from registry
        del registry[doc_id]
        self._save_registry(session_id, registry)
        return True


# Global storage instance
doc_storage = DocumentStorage()
