"""
Base models and abstract interface for document extractors.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ExtractedSection(BaseModel):
    """Represents a coherent section of extracted text with provenance metadata."""
    text: str
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    section_title: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractedDocument(BaseModel):
    """Represents the complete extracted contents of an uploaded document."""
    filename: str
    file_type: str
    sections: List[ExtractedSection]
    total_sections: int = 0
    total_characters: int = 0
    total_words: int = 0

    def compute_stats(self):
        self.total_sections = len(self.sections)
        self.total_characters = sum(len(s.text) for s in self.sections)
        self.total_words = sum(len(s.text.split()) for s in self.sections)


class BaseExtractor(ABC):
    """Abstract base class for all file format extractors."""

    @abstractmethod
    def extract(self, file_path: Path, filename: Optional[str] = None) -> ExtractedDocument:
        """Extracts structured text and provenance metadata from the target file."""
        pass
