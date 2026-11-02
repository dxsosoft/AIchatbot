"""
PDF text and metadata extractor using pypdf.
Extracts content page-by-page to guarantee exact page-number citation attribution.
"""

from pathlib import Path
from typing import Optional
import pypdf
from backend.extractors.base import BaseExtractor, ExtractedDocument, ExtractedSection
from backend.validators import ValidationError


class PDFExtractor(BaseExtractor):
    """Extracts text page by page from PDF files."""

    def extract(self, file_path: Path, filename: Optional[str] = None) -> ExtractedDocument:
        fname = filename or file_path.name

        try:
            reader = pypdf.PdfReader(str(file_path))
        except Exception as e:
            raise ValidationError(f"Failed to open PDF file: {str(e)}")

        if reader.is_encrypted:
            raise ValidationError(f"PDF '{fname}' is password-protected and cannot be parsed.")

        sections = []
        total_pages = len(reader.pages)

        if total_pages == 0:
            raise ValidationError(f"PDF '{fname}' contains no pages.")

        for idx, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""

            clean_text = page_text.strip()
            if clean_text:
                sections.append(
                    ExtractedSection(
                        text=clean_text,
                        page_number=idx + 1,
                        metadata={"total_pages": total_pages}
                    )
                )

        if not sections:
            raise ValidationError(
                f"No extractable text found in '{fname}'. "
                "The PDF may consist solely of scanned images without OCR text."
            )

        doc = ExtractedDocument(
            filename=fname,
            file_type="pdf",
            sections=sections
        )
        doc.compute_stats()
        return doc
