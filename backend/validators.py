"""
File upload validation and security sanitization module.
Guards against path traversal, oversized files, invalid MIME/magic bytes,
empty payloads, and corrupt files.
"""

import re
import hashlib
from pathlib import Path
from typing import Tuple, Optional
from backend.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES


class ValidationError(Exception):
    """Raised when an uploaded file violates security or integrity rules."""
    pass


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes filename against path traversal and forbidden characters.
    Preserves valid basename and extension.
    """
    if not filename:
        raise ValidationError("Filename cannot be empty.")

    # Remove any directory path components
    basename = Path(filename).name

    # Replace suspicious characters with underscore
    clean = re.sub(r'[^a-zA-Z0-9_.\- ]', '_', basename).strip()
    clean = re.sub(r'\.{2,}', '.', clean)  # Prevent multiple dots like '..'

    if not clean or clean.startswith("."):
        clean = f"document_{clean.lstrip('.')}" if clean.lstrip(".") else "uploaded_document"

    return clean


def calculate_sha256(content: bytes) -> str:
    """Calculates SHA-256 hash of file bytes for integrity and deduplication."""
    return hashlib.sha256(content).hexdigest()


def validate_file_content(filename: str, content: bytes) -> Tuple[str, str]:
    """
    Validates extension, size, empty files, and basic magic bytes.
    Returns: (sanitized_filename, extension)
    Raises: ValidationError on invalid input.
    """
    if not content or len(content) == 0:
        raise ValidationError("File is empty (0 bytes).")

    if len(content) > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        raise ValidationError(f"File size exceeds maximum allowed limit of {max_mb} MB.")

    clean_name = sanitize_filename(filename)
    ext = Path(clean_name).suffix.lower().lstrip(".")

    if not ext or ext not in ALLOWED_EXTENSIONS:
        allowed_str = ", ".join(sorted(list(ALLOWED_EXTENSIONS)))
        raise ValidationError(f"Unsupported file format '.{ext}'. Allowed formats: {allowed_str}")

    # Magic byte verification
    if ext == "pdf":
        if not content.startswith(b"%PDF"):
            raise ValidationError("Invalid PDF file: Missing %PDF header.")
    elif ext in ("docx", "xlsx"):
        # DOCX and XLSX are OpenXML ZIP packages starting with 'PK\x03\x04'
        if not content.startswith(b"PK\x03\x04"):
            raise ValidationError(f"Invalid .{ext} file: Not a valid OpenXML package (corrupted or wrong format).")
    elif ext in ("txt", "csv"):
        # Check for binary null bytes to prevent uploading executables renamed as .txt/.csv
        if b"\x00" in content[:4096]:
            raise ValidationError(f"Binary content detected in .{ext} file.")

    return clean_name, ext
