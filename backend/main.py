"""
FastAPI application for AI Knowledge Assistant (Type 1 - File Upload).
Exposes REST endpoints for upload, document listing, deletion, chat Q&A, and health checks.
Serves the modern frontend single-page application.
"""

from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from backend.config import PROJECT_ROOT, get_config_summary, TOP_K_RETRIEVAL
from backend.validators import validate_file_content, ValidationError
from backend.extractors import get_extractor
from backend.chunker import chunk_document
from backend.indexer import index_manager
from backend.storage import doc_storage, DocumentRecord
from backend.ai import qa_service, QAResponse

app = FastAPI(
    title="AI Knowledge Assistant (Type 1 - File Upload)",
    description="Knowledge Assistant grounded in uploaded user documents with source citations",
    version="1.0.0"
)

# Enable CORS for local paired development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = PROJECT_ROOT / "frontend"


# ------------------------------------------------------------------------------
# Pydantic Request Models
# ------------------------------------------------------------------------------
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Question to answer using uploaded documents")
    session_id: Optional[str] = Field("default_session", description="Unique session/user identifier")
    top_k: Optional[int] = Field(TOP_K_RETRIEVAL, ge=1, le=15, description="Number of context excerpts to retrieve")
    provider: Optional[str] = Field(None, description="Optional AI provider override (gemini, openai, mock)")


# ------------------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------------------
@app.get("/api/health")
def health_check():
    """Health check endpoint providing system status and safe config information."""
    config_info = get_config_summary()
    return {
        "status": "healthy",
        "service": "AI Knowledge Assistant (Type 1 - File Upload)",
        "version": "1.0.0",
        "configuration": config_info
    }


@app.post("/api/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form("default_session"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id")
):
    """
    Validates, extracts, chunks, and indexes an uploaded document within an isolated session.
    Supported formats: PDF, DOCX, XLSX, CSV, TXT.
    """
    active_session = x_session_id or session_id or "default_session"

    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file payload: {str(e)}")

    # 1. Validate file extension, size, magic bytes, and sanitize filename
    try:
        clean_name, ext = validate_file_content(file.filename or "uploaded_file", content)
    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    # 2. Save raw file securely to session storage
    record = doc_storage.save_file(
        session_id=active_session,
        filename=clean_name,
        content=content,
        file_type=ext
    )

    # 3. Extract text and structural metadata
    try:
        extractor = get_extractor(ext)
        extracted_doc = extractor.extract(Path(record.stored_path), filename=clean_name)
    except ValidationError as ve:
        doc_storage.delete_document(active_session, record.doc_id)
        raise HTTPException(status_code=422, detail=f"Document parsing error: {str(ve)}")
    except Exception as e:
        doc_storage.delete_document(active_session, record.doc_id)
        raise HTTPException(status_code=500, detail=f"Extraction failure: {str(e)}")

    # 4. Chunk extracted text with preserved provenance
    chunks = chunk_document(extracted_doc, doc_id=record.doc_id)

    # 5. Index chunks in session-isolated search index
    search_index = index_manager.get_index(active_session)
    search_index.add_chunks(chunks)

    # 6. Update document registry
    doc_storage.update_chunk_count(active_session, record.doc_id, len(chunks), status="indexed")
    record.chunk_count = len(chunks)
    record.status = "indexed"

    return {
        "message": f"Successfully processed and indexed '{clean_name}'",
        "document": record.model_dump(),
        "chunks_indexed": len(chunks),
        "total_characters": extracted_doc.total_characters,
        "total_words": extracted_doc.total_words
    }


@app.get("/api/documents")
def list_documents(
    session_id: Optional[str] = "default_session",
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id")
):
    """Lists all uploaded documents for the specified user session."""
    active_session = x_session_id or session_id or "default_session"
    docs = doc_storage.list_documents(active_session)
    return {
        "session_id": active_session,
        "total_documents": len(docs),
        "documents": [d.model_dump() for d in docs]
    }


@app.delete("/api/documents/{doc_id}")
def delete_document(
    doc_id: str,
    session_id: Optional[str] = "default_session",
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id")
):
    """Deletes a document and purges its chunks from the search index."""
    active_session = x_session_id or session_id or "default_session"
    success = doc_storage.delete_document(active_session, doc_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found in session '{active_session}'.")

    return {
        "message": f"Document '{doc_id}' deleted successfully.",
        "doc_id": doc_id,
        "session_id": active_session
    }


@app.post("/api/chat", response_model=QAResponse)
def chat_query(
    request: ChatRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id")
):
    """
    Answers user queries grounded strictly in the session's uploaded documents.
    Returns the answer accompanied by source citation cards.
    """
    active_session = x_session_id or request.session_id or "default_session"
    return qa_service.answer_question(
        session_id=active_session,
        query=request.query,
        top_k=request.top_k or TOP_K_RETRIEVAL,
        provider_override=request.provider
    )


# ------------------------------------------------------------------------------
# Serve Single-Page Frontend Application
# ------------------------------------------------------------------------------
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def serve_index():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse({"message": "Frontend UI available. Open frontend/index.html."})
