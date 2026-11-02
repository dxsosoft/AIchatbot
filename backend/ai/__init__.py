"""
AI Integration and Question Answering package.
"""

from backend.ai.provider import (
    BaseAIProvider,
    GeminiProvider,
    OpenAIProvider,
    MockProvider,
    ConfigErrorProvider,
    get_ai_provider,
    AIConfigurationError,
    AIProviderError
)
from backend.ai.qa_service import QAService, qa_service, QAResponse, SourceCitation

__all__ = [
    "BaseAIProvider",
    "GeminiProvider",
    "OpenAIProvider",
    "MockProvider",
    "ConfigErrorProvider",
    "get_ai_provider",
    "AIConfigurationError",
    "AIProviderError",
    "QAService",
    "qa_service",
    "QAResponse",
    "SourceCitation"
]
