"""
Plain text (.txt) and Markdown document extractor.
Preserves paragraphs and section divisions.
"""

from pathlib import Path
from typing import Optional, List
from backend.extractors.base import BaseExtractor, ExtractedDocument, ExtractedSection
from backend.validators import ValidationError


class TextExtractor(BaseExtractor):
    """Extracts text from plain text (.txt) and markdown documents."""

    def extract(self, file_path: Path, filename: Optional[str] = None) -> ExtractedDocument:
        fname = filename or file_path.name

        raw_bytes = file_path.read_bytes()
        if not raw_bytes.strip():
            raise ValidationError(f"Text file '{fname}' is empty.")

        # Decode with fallback
        content = None
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                content = raw_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            raise ValidationError(f"Could not decode text file '{fname}' with supported encodings.")

        # Split into coherent paragraphs / sections
        blocks = [b.strip() for b in content.split("\n\n") if b.strip()]
        if not blocks:
            raise ValidationError(f"No readable content found in '{fname}'.")

        sections: List[ExtractedSection] = []
        current_title = "Document"
        current_chunk: List[str] = []

        for block in blocks:
            # Check if block looks like a header (e.g., '# Heading', '===', or short uppercase)
            if block.startswith("#") or (len(block) < 60 and block.isupper()):
                if current_chunk:
                    sections.append(
                        ExtractedSection(
                            text="\n\n".join(current_chunk),
                            section_title=current_title
                        )
                    )
                    current_chunk = []
                current_title = block.lstrip("# ").strip()
            else:
                current_chunk.append(block)

        if current_chunk:
            sections.append(
                ExtractedSection(
                    text="\n\n".join(current_chunk),
                    section_title=current_title
                )
            )

        doc = ExtractedDocument(
            filename=fname,
            file_type="txt",
            sections=sections
        )
        doc.compute_stats()
        return doc
