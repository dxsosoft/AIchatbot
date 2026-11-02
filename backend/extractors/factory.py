"""
Factory for creating the appropriate document extractor based on file extension.
"""

from pathlib import Path
from typing import Union
from backend.extractors.base import BaseExtractor
from backend.extractors.pdf_extractor import PDFExtractor
from backend.extractors.docx_extractor import DocxExtractor
from backend.extractors.excel_extractor import ExcelExtractor
from backend.extractors.text_extractor import TextExtractor
from backend.validators import ValidationError


def get_extractor(file_target: Union[str, Path]) -> BaseExtractor:
    """Returns extractor instance corresponding to target filename or Path."""
    path = Path(file_target)
    ext = path.suffix.lower().lstrip(".")

    if ext == "pdf":
        return PDFExtractor()
    elif ext == "docx":
        return DocxExtractor()
    elif ext in ("xlsx", "csv"):
        return ExcelExtractor()
    elif ext in ("txt", "md"):
        return TextExtractor()
    else:
        raise ValidationError(f"No extractor available for file format '.{ext}'")
