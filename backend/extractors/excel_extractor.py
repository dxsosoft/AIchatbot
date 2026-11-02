"""
Excel (.xlsx) and CSV (.csv) structured data extractor.
Converts sheets and rows into readable tabular text chunks,
preserving sheet names and row identifiers for provenance.
"""

import csv
from pathlib import Path
from typing import Optional, List
import openpyxl
from backend.extractors.base import BaseExtractor, ExtractedDocument, ExtractedSection
from backend.validators import ValidationError


class ExcelExtractor(BaseExtractor):
    """Extracts structured rows and sheets from XLSX and CSV files."""

    def extract(self, file_path: Path, filename: Optional[str] = None) -> ExtractedDocument:
        fname = filename or file_path.name
        ext = file_path.suffix.lower().lstrip(".")

        if ext == "csv":
            return self._extract_csv(file_path, fname)
        elif ext == "xlsx":
            return self._extract_xlsx(file_path, fname)
        else:
            raise ValidationError(f"Unsupported spreadsheet format '.{ext}'")

    def _extract_csv(self, file_path: Path, fname: str) -> ExtractedDocument:
        sections: List[ExtractedSection] = []

        # Try utf-8 first, fallback to latin-1
        encoding = "utf-8"
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                f.read(1024)
        except UnicodeDecodeError:
            encoding = "latin-1"

        try:
            with open(file_path, "r", encoding=encoding, newline="") as f:
                reader = csv.reader(f)
                rows = [row for row in reader if any(cell.strip() for cell in row)]
        except Exception as e:
            raise ValidationError(f"Failed to read CSV file '{fname}': {str(e)}")

        if not rows:
            raise ValidationError(f"CSV file '{fname}' is empty or contains no valid rows.")

        headers = [h.strip() for h in rows[0]]
        data_rows = rows[1:]

        # Group rows into batches (e.g., 25 rows per section) for clean retrieval
        batch_size = 25
        for i in range(0, len(data_rows), batch_size):
            chunk_rows = data_rows[i:i + batch_size]
            row_start = i + 2
            row_end = i + 1 + len(chunk_rows)

            formatted_records = []
            for r_idx, row in enumerate(chunk_rows, start=row_start):
                record_fields = []
                for h, val in zip(headers, row):
                    clean_val = val.strip()
                    if clean_val:
                        record_fields.append(f"{h}: {clean_val}")
                if record_fields:
                    formatted_records.append(f"[Row {r_idx}] " + " | ".join(record_fields))

            if formatted_records:
                section_text = (
                    f"Columns: {', '.join(headers)}\n\n" +
                    "\n".join(formatted_records)
                )
                sections.append(
                    ExtractedSection(
                        text=section_text,
                        sheet_name="Main",
                        section_title=f"Rows {row_start}-{row_end}",
                        metadata={"start_row": row_start, "end_row": row_end}
                    )
                )

        if not sections:
            raise ValidationError(f"No extractable data rows found in CSV '{fname}'.")

        doc = ExtractedDocument(
            filename=fname,
            file_type="csv",
            sections=sections
        )
        doc.compute_stats()
        return doc

    def _extract_xlsx(self, file_path: Path, fname: str) -> ExtractedDocument:
        sections: List[ExtractedSection] = []

        try:
            wb = openpyxl.load_workbook(str(file_path), data_only=True, read_only=True)
        except Exception as e:
            raise ValidationError(f"Failed to open Excel workbook '{fname}': {str(e)}")

        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            raw_rows = []

            for row in sheet.iter_rows(values_only=True):
                # Filter out completely empty rows
                str_cells = [str(c).strip() if c is not None else "" for c in row]
                if any(str_cells):
                    raw_rows.append(str_cells)

            if not raw_rows:
                continue

            headers = raw_rows[0]
            # Replace empty headers with column indices
            headers = [h if h else f"Col_{idx+1}" for idx, h in enumerate(headers)]
            data_rows = raw_rows[1:]

            # Batch rows for granular search retrieval
            batch_size = 25
            for i in range(0, len(data_rows), batch_size):
                chunk_rows = data_rows[i:i + batch_size]
                row_start = i + 2
                row_end = i + 1 + len(chunk_rows)

                formatted_records = []
                for r_idx, row in enumerate(chunk_rows, start=row_start):
                    record_fields = []
                    for h, val in zip(headers, row):
                        if val:
                            record_fields.append(f"{h}: {val}")
                    if record_fields:
                        formatted_records.append(f"[Row {r_idx}] " + " | ".join(record_fields))

                if formatted_records:
                    section_text = (
                        f"Sheet: {sheet_name} | Columns: {', '.join(headers)}\n\n" +
                        "\n".join(formatted_records)
                    )
                    sections.append(
                        ExtractedSection(
                            text=section_text,
                            sheet_name=sheet_name,
                            section_title=f"Sheet '{sheet_name}' (Rows {row_start}-{row_end})",
                            metadata={"sheet": sheet_name, "start_row": row_start, "end_row": row_end}
                        )
                    )

        wb.close()

        if not sections:
            raise ValidationError(f"No extractable sheets or rows found in Excel workbook '{fname}'.")

        doc = ExtractedDocument(
            filename=fname,
            file_type="xlsx",
            sections=sections
        )
        doc.compute_stats()
        return doc
