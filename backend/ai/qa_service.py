"""
Question Answering Orchestration Service.
Connects session retrieval, grounded prompt construction, LLM generation, and citation formatting.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.indexer import index_manager, SearchResult
from backend.ai.prompt import SYSTEM_GROUNDING_INSTRUCTION, build_grounded_prompt
from backend.ai.provider import get_ai_provider, BaseAIProvider, AIConfigurationError, AIProviderError
from backend.config import TOP_K_RETRIEVAL


class SourceCitation(BaseModel):
    """Clean citation attribution for grounded response verification."""
    document_name: str
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    section_title: Optional[str] = None
    relevance_score: float
    snippet: str


class QAResponse(BaseModel):
    """Complete structured response including grounded answer and source citations."""
    query: str
    answer: str
    citations: List[SourceCitation]
    total_chunks_retrieved: int
    provider: str
    error: Optional[str] = None


class QAService:
    """Coordinates search retrieval, AI generation, and source citation extraction."""

    def __init__(self, provider: Optional[BaseAIProvider] = None):
        self._custom_provider = provider

    def answer_question(
        self,
        session_id: str,
        query: str,
        top_k: int = TOP_K_RETRIEVAL,
        provider_override: Optional[str] = None
    ) -> QAResponse:
        clean_query = query.strip()
        if not clean_query:
            return QAResponse(
                query=query,
                answer="Please enter a valid question.",
                citations=[],
                total_chunks_retrieved=0,
                provider="none"
            )

        # 1. Retrieve relevant chunks for this isolated session
        search_index = index_manager.get_index(session_id)
        results = search_index.search(clean_query, top_k=top_k)

        # 2. Get active AI provider
        provider = self._custom_provider or get_ai_provider(provider_override)

        # If no documents uploaded or no matches found
        if not results:
            return QAResponse(
                query=clean_query,
                answer=(
                    "The provided documents do not contain information to answer this question. "
                    "(No matching content was found in the files uploaded for this session)."
                ),
                citations=[],
                total_chunks_retrieved=0,
                provider=provider.name
            )

        # 3. Format citations from retrieved chunks
        citations = [
            SourceCitation(
                document_name=r.filename,
                page_number=r.page_number,
                sheet_name=r.sheet_name,
                section_title=r.section_title,
                relevance_score=r.relevance_score,
                snippet=r.text[:280] + ("..." if len(r.text) > 280 else "")
            )
            for r in results
        ]

        # 4. Construct prompt and generate answer
        prompt = build_grounded_prompt(clean_query, results)

        try:
            raw_answer = provider.generate(prompt, SYSTEM_GROUNDING_INSTRUCTION)
            return QAResponse(
                query=clean_query,
                answer=raw_answer,
                citations=citations,
                total_chunks_retrieved=len(results),
                provider=provider.name
            )
        except AIConfigurationError as ce:
            return QAResponse(
                query=clean_query,
                answer=(
                    f"⚠️ Configuration Error: {str(ce)}\n\n"
                    "The file was successfully uploaded, parsed, and relevant excerpts were retrieved below. "
                    "To generate AI synthesis, please add your API key to `.env`."
                ),
                citations=citations,
                total_chunks_retrieved=len(results),
                provider=provider.name,
                error=str(ce)
            )
        except AIProviderError as pe:
            return QAResponse(
                query=clean_query,
                answer=f"AI Provider Error: {str(pe)}",
                citations=citations,
                total_chunks_retrieved=len(results),
                provider=provider.name,
                error=str(pe)
            )


# Global service instance
qa_service = QAService()
