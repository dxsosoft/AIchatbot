# AI Knowledge Assistant & Database Inspection Chatbot

A production-ready AI Assistant platform featuring document-grounded question answering (RAG) with source citations, multi-format file extraction, multi-LLM provider support (Google Gemini, OpenAI, Mock), and database inspection capabilities.

---

## 🌟 Key Features

- **Document Grounded Chat (Type 1 - File Upload)**:
  - Upload documents (`.pdf`, `.docx`, `.xlsx`, `.csv`, `.txt`) up to 25 MB.
  - Multi-extractor pipeline with metadata tracking (page numbers, sheet names, row counts, sections).
  - Adaptive sliding-window text chunker preserving context boundaries.
  - TF-IDF + BM25-style lexical keyword retrieval engine per session.
  - Strict grounding: only answers based on provided documents with explicit source citations.
  - Multiple LLM providers supported: **Google Gemini**, **OpenAI**, and an offline **Mock** mode for testing.

- **Interactive Modern Frontend**:
  - Dark-mode glassmorphism design with responsive UI.
  - Drag-and-drop document upload with real-time status and file management.
  - Markdown-rendered answers with interactive citation badges and provenance cards.
  - Session switching and management.

- **PostgreSQL Database Inspection Module**:
  - Safe, read-only database schema inspection (`db_connection.py`, `inspect_db.py`, `schema_inspector.py`).
  - Catalogues tables, foreign keys, constraints, and data distribution safely.

---

## 🏗️ Project Structure

```text
├── backend/
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── prompt.py          # Grounded system instructions & prompt templates
│   │   ├── provider.py        # Gemini, OpenAI, and Mock provider implementations
│   │   └── qa_service.py      # Q&A orchestration with citations and fallback
│   ├── extractors/
│   │   ├── base.py            # Extractor abstract base class
│   │   ├── docx_extractor.py  # DOCX parser with paragraph/table mapping
│   │   ├── excel_extractor.py # Excel (.xlsx) / CSV tabular data parser
│   │   ├── pdf_extractor.py   # PDF text extraction with page numbers
│   │   ├── text_extractor.py  # Plain text and markdown parser
│   │   └── factory.py         # Extractor factory routing
│   ├── chunker.py             # Context-aware text chunking
│   ├── config.py              # Environment configuration & validation
│   ├── indexer.py             # TF-IDF / BM25 inverted index for semantic retrieval
│   ├── main.py                # FastAPI REST API & static file server
│   ├── storage.py             # Session-isolated document persistence
│   └── validators.py          # File size, MIME-type, and magic number validators
├── frontend/
│   ├── css/
│   │   └── style.css          # Modern glassmorphism CSS
│   ├── js/
│   │   └── app.js             # Single-page application logic
│   └── index.html             # Application markup
├── .env.example               # Template for environment variables
├── .gitignore                 # Preconfigured ignore rules (secrets, caches, data)
├── db_connection.py           # PostgreSQL connection helper
├── inspect_db.py              # Database schema inspector
├── requirements.txt           # Python dependencies
├── schema_inspector.py        # Detailed DB schema analysis tool
├── test_step1.py              # Step 1 test suite
└── test_type1.py              # Type 1 full system test suite
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- (Optional) PostgreSQL database if using database inspection features.

### 2. Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/dxsosoft/AIchatbot.git
   cd AIchatbot
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### 3. Configuration

Copy the example environment file and configure your API keys:
```bash
cp .env.example .env
```

Edit `.env` with your settings:
```ini
# AI Provider: 'gemini', 'openai', or 'mock'
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here

# Or for OpenAI:
# AI_PROVIDER=openai
# OPENAI_API_KEY=your_openai_api_key_here
```

### 4. Running the Application

Start the FastAPI application:
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser at:
- **Web App**: [http://localhost:8000](http://localhost:8000)
- **Interactive API Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## 🧪 Testing

Run the automated test suites:
```bash
# Test Type 1 File Upload, Extraction, Indexing, and QA:
python test_type1.py

# Test Database Connection & Inspection:
python test_step1.py
```

---

## 📄 License

This project is licensed under the MIT License.
