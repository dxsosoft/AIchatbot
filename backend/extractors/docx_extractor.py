"""
DOCX text, heading, and table extractor using python-docx.
Preserves section titles, paragraph groupings, and table structures.
"""

from pathlib import Path
from typing import Optional, List
import docx
from backend.extractors.base import BaseExtractor, ExtractedDocument, ExtractedSection
from backend.validators import ValidationError


class DocxExtractor(BaseExtractor):
    """Extracts paragraphs, headings, and tables from Word (.docx) documents."""

    def extract(self, file_path: Path, filename: Optional[str] = None) -> ExtractedDocument:
        fname = filename or file_path.name

        try:
            document = docx.Document(str(file_path))
        except Exception as e:
            raise ValidationError(f"Failed to open DOCX file '{fname}': {str(e)}")

        sections: List[ExtractedSection] = []
        current_heading = "General"
        current_paras: List[str] = []

        def flush_paragraphs():
            nonlocal current_paras
            if current_paras:
                combined_text = "\n\n".join(current_paras).strip()
                if combined_text:
                    sections.append(
                        ExtractedSection(
                            text=combined_text,
                            section_title=current_heading,
                        )
                    )
                current_paras = []

        # Process paragraphs
        for p in document.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            style_name = p.style.name.lower() if p.style else ""
            if "heading" in style_name or "title" in style_name:
                flush_paragraphs()
                current_heading = text
            else:
                current_paras.append(text)

        flush_paragraphs()

        # Process tables
        for tbl_idx, table in enumerate(document.tables, 1):
            table_rows = []
            for row in table.rows:
                cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                if any(cells):
                    table_rows.append(cells)

            if not table_rows:
                continue

            # Format table as Markdown
            headers = table_rows[0]
            col_count = len(headers)
            separator = ["---"] * col_count

            md_lines = [
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join(separator) + " |"
            ]

            for row in table_rows[1:]:
                # Normalize length
                padded = row + [""] * (col_count - len(row))
                md_lines.append("| " + " | ".join(padded[:col_count]) + " |")

            table_text = "\n".join(md_lines)
            table_title = f"{current_heading} (Table {tbl_idx})"

            sections.append(
                ExtractedSection(
                    text=table_text,
                    section_title=table_title,
                    metadata={"table_index": tbl_idx, "rows_count": len(table_rows)}
                )
            )

        if not sections:
            raise ValidationError(f"No extractable text or tables found in DOCX file '{fname}'.")

        doc = ExtractedDocument(
            filename=fname,
            file_type="docx",
            sections=sections
        )
        doc.compute_stats()
        return doc
