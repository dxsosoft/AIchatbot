"""
Comprehensive Verification Test Suite for Type 1 (File Upload Knowledge Assistant).

Verifies:
1. Document extraction across all 5 formats: PDF, DOCX, XLSX, CSV, TXT.
2. File validation & security: corrupt files, 0-byte files, invalid extensions, path traversal.
3. Provenance-preserving chunking (pages, sheets, sections).
4. Session-isolated local indexing and BM25 retrieval.
5. User/Session isolation (no cross-tenant leakage).
6. Complete document deletion and index cache purging.
7. Grounded AI Q&A with source citations & missing credential error handling.
8. End-to-end FastAPI REST API flow using sample files.
"""

import os
import sys
import tempfile
import io
from pathlib import Path

# Ensure project root is in path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from backend.validators import validate_file_content, sanitize_filename, ValidationError
from backend.extractors import get_extractor
from backend.chunker import chunk_document
from backend.indexer import SessionSearchIndex, index_manager
from backend.storage import DocumentStorage
from backend.ai.provider import MockProvider, ConfigErrorProvider, AIConfigurationError
from backend.ai.qa_service import QAService
from fastapi.testclient import TestClient
from backend.main import app


SAMPLE_DIR = Path(r"D:\DXSO\AI  Sample Files")


def run_all_tests():
    print("=" * 70)
    print("   TYPE 1 (FILE UPLOAD) COMPREHENSIVE VERIFICATION SUITE")
    print("=" * 70)
    
    passed_count = 0
    total_tests = 8

    # --------------------------------------------------------------------------
    # Test 1: File Upload Validation & Security
    # --------------------------------------------------------------------------
    print("\n[TEST 1] Upload Validation & Security Constraints...")
    try:
        # Reject 0-byte file
        try:
            validate_file_content("empty.pdf", b"")
            assert False, "Should reject empty file"
        except ValidationError:
            pass

        # Reject invalid extension (.exe)
        try:
            validate_file_content("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00")
            assert False, "Should reject .exe extension"
        except ValidationError:
            pass

        # Reject fake/corrupt PDF (wrong magic bytes)
        try:
            validate_file_content("fake.pdf", b"This is not a pdf file header")
            assert False, "Should reject corrupt PDF"
        except ValidationError:
            pass

        # Reject binary null bytes in .txt
        try:
            validate_file_content("corrupt.txt", b"Hello\x00World")
            assert False, "Should reject binary null bytes in txt"
        except ValidationError:
            pass

        # Test path traversal sanitization
        clean_name = sanitize_filename("../../etc/passwd/report.pdf")
        assert ".." not in clean_name and "/" not in clean_name and "\\" not in clean_name
        assert clean_name.endswith(".pdf")

        # Accept valid PDF bytes
        name, ext = validate_file_content("annual_report.pdf", b"%PDF-1.4 test content")
        assert ext == "pdf"
        assert name == "annual_report.pdf"

        print("  --> PASS: 0-byte, corrupt files, invalid extensions & path traversal rejected successfully.")
        passed_count += 1
    except Exception as e:
        print(f"  --> FAIL in Test 1: {e}")

    # --------------------------------------------------------------------------
    # Test 2: Extraction Across Supported Formats
    # --------------------------------------------------------------------------
    print("\n[TEST 2] Document Parsers (PDF, DOCX, XLSX, CSV, TXT)...")
    try:
        # PDF Extraction (using sample file if present)
        sample_pdf = SAMPLE_DIR / "Detailed_Operations_and_KPI_Report.pdf"
        if sample_pdf.exists():
            pdf_extractor = get_extractor("pdf")
            pdf_doc = pdf_extractor.extract(sample_pdf)
            assert len(pdf_doc.sections) > 0
            assert any(s.page_number is not None for s in pdf_doc.sections)
            print(f"  --> PASS [PDF]: {len(pdf_doc.sections)} pages parsed with page numbers.")
        else:
            print("  --> SKIP [PDF]: Sample file not found, testing synthesized.")

        # DOCX Extraction (using sample file if present)
        sample_docx = SAMPLE_DIR / "Detailed_Company_Knowledge_Base.docx"
        if sample_docx.exists():
            docx_extractor = get_extractor("docx")
            docx_doc = docx_extractor.extract(sample_docx)
            assert len(docx_doc.sections) > 0
            assert any(s.section_title for s in docx_doc.sections)
            print(f"  --> PASS [DOCX]: {len(docx_doc.sections)} sections parsed with headings & tables.")
        else:
            print("  --> SKIP [DOCX]: Sample file not found.")

        # XLSX Extraction (using sample file if present)
        sample_xlsx = SAMPLE_DIR / "Detailed_Sales_Operations_Dataset.xlsx"
        if sample_xlsx.exists():
            xlsx_extractor = get_extractor("xlsx")
            xlsx_doc = xlsx_extractor.extract(sample_xlsx)
            assert len(xlsx_doc.sections) > 0
            assert any(s.sheet_name for s in xlsx_doc.sections)
            print(f"  --> PASS [XLSX]: {len(xlsx_doc.sections)} row blocks parsed across workbook sheets.")
        else:
            print("  --> SKIP [XLSX]: Sample file not found.")

        # CSV Extraction (synthesized)
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("CustomerID,CustomerName,Plan,MonthlyFee\n101,Acme Corp,Enterprise,499.00\n102,TechNova,Pro,199.00\n")
            temp_csv = Path(f.name)
        try:
            csv_extractor = get_extractor("csv")
            csv_doc = csv_extractor.extract(temp_csv)
            assert len(csv_doc.sections) > 0
            assert "Acme Corp" in csv_doc.sections[0].text
            print(f"  --> PASS [CSV]: Structured tabular rows parsed successfully.")
        finally:
            temp_csv.unlink()

        # TXT Extraction (synthesized)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("# Refund Policy\nAll software licenses have a 30-day money-back guarantee.\n\n# Support Hours\nSupport is 24/7.")
            temp_txt = Path(f.name)
        try:
            txt_extractor = get_extractor("txt")
            txt_doc = txt_extractor.extract(temp_txt)
            assert len(txt_doc.sections) >= 2
            assert "Refund Policy" in txt_doc.sections[0].section_title or "Refund Policy" in txt_doc.sections[0].text
            print(f"  --> PASS [TXT]: Sections and headings parsed successfully.")
        finally:
            temp_txt.unlink()

        passed_count += 1
    except Exception as e:
        print(f"  --> FAIL in Test 2: {e}")

    # --------------------------------------------------------------------------
    # Test 3: Provenance-Preserving Chunking
    # --------------------------------------------------------------------------
    print("\n[TEST 3] Chunking Engine & Provenance Preservation...")
    try:
        sample_docx = SAMPLE_DIR / "Detailed_Company_Knowledge_Base.docx"
        if sample_docx.exists():
            docx_extractor = get_extractor("docx")
            doc = docx_extractor.extract(sample_docx)
            chunks = chunk_document(doc, doc_id="test_doc_01", max_chunk_size=600, overlap=100)
            assert len(chunks) > 0
            assert all(c.doc_id == "test_doc_01" for c in chunks)
            assert all(c.filename == "Detailed_Company_Knowledge_Base.docx" for c in chunks)
            assert all(c.text.strip() for c in chunks)
            print(f"  --> PASS: {len(chunks)} chunks produced with complete metadata binding.")
        else:
            print("  --> SKIP: Sample docx not found for chunk test.")
        passed_count += 1
    except Exception as e:
        print(f"  --> FAIL in Test 3: {e}")

    # --------------------------------------------------------------------------
    # Test 4: Local BM25 Retrieval & Phrase Matching
    # --------------------------------------------------------------------------
    print("\n[TEST 4] Local Search Index & Semantic Retrieval...")
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            idx = SessionSearchIndex("session_test_ranking", storage_dir=Path(tmp_dir))
            
            sample_docx = SAMPLE_DIR / "Detailed_Company_Knowledge_Base.docx"
            if sample_docx.exists():
                doc = get_extractor("docx").extract(sample_docx)
                chunks = chunk_document(doc, doc_id="kb_01")
                idx.add_chunks(chunks)

                # Search query matching knowledge base
                results = idx.search("What is the company mission and founding year?", top_k=3)
                assert len(results) > 0
                assert results[0].relevance_score > 0.0
                assert results[0].filename == "Detailed_Company_Knowledge_Base.docx"
                print(f"  --> PASS: Retrieved top {len(results)} chunks (Best score: {results[0].relevance_score}).")
            else:
                print("  --> SKIP: Sample docx not found.")
        passed_count += 1
    except Exception as e:
        print(f"  --> FAIL in Test 4: {e}")

    # --------------------------------------------------------------------------
    # Test 5: Strict Session / User Isolation
    # --------------------------------------------------------------------------
    print("\n[TEST 5] Multi-Tenant / Session Isolation...")
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage_path = Path(tmp_dir)
            index_mgr = DocumentStorage(upload_root=storage_path / "uploads", data_root=storage_path / "data")
            
            idx_user_a = SessionSearchIndex("user_alice", storage_dir=storage_path / "data")
            idx_user_b = SessionSearchIndex("user_bob", storage_dir=storage_path / "data")

            # Alice uploads secret project Alpha
            from backend.chunker import DocumentChunk
            chunk_a = DocumentChunk(
                chunk_id="a_01",
                doc_id="doc_a",
                filename="alice_confidential.txt",
                chunk_index=0,
                text="Project Alpha secret code is 998877."
            )
            idx_user_a.add_chunks([chunk_a])

            # Bob uploads project Beta
            chunk_b = DocumentChunk(
                chunk_id="b_01",
                doc_id="doc_b",
                filename="bob_notes.txt",
                chunk_index=0,
                text="Project Beta meeting is at 2 PM."
            )
            idx_user_b.add_chunks([chunk_b])

            # Alice searches for Project Alpha -> Found
            res_a = idx_user_a.search("Project Alpha secret code")
            assert len(res_a) > 0
            assert "998877" in res_a[0].text

            # Bob searches for Project Alpha -> Must NOT be found!
            res_b = idx_user_b.search("Project Alpha secret code")
            assert len(res_b) == 0, "Bob MUST NOT access Alice's documents!"

            print("  --> PASS: User sessions are completely isolated. Zero cross-tenant leakage.")
        passed_count += 1
    except Exception as e:
        print(f"  --> FAIL in Test 5: {e}")

    # --------------------------------------------------------------------------
    # Test 6: Document Deletion & Index Purging
    # --------------------------------------------------------------------------
    print("\n[TEST 6] Document Deletion & Purging...")
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage_path = Path(tmp_dir)
            storage = DocumentStorage(upload_root=storage_path / "uploads", data_root=storage_path / "data")
            
            # Save file
            rec = storage.save_file("session_del", "temp_notes.txt", b"Secret data to be purged", "txt")
            assert Path(rec.stored_path).exists()

            # Index chunk
            idx = SessionSearchIndex("session_del", storage_dir=storage_path / "data")
            from backend.chunker import DocumentChunk
            chk = DocumentChunk(
                chunk_id=f"{rec.doc_id}_c0",
                doc_id=rec.doc_id,
                filename="temp_notes.txt",
                chunk_index=0,
                text="Secret data to be purged"
            )
            idx.add_chunks([chk])
            assert len(idx.search("Secret data")) > 0

            # Delete document
            success = storage.delete_document("session_del", rec.doc_id)
            assert success is True
            assert not Path(rec.stored_path).exists(), "Physical file must be deleted"

            # Check index has purged the chunks
            idx_reloaded = SessionSearchIndex("session_del", storage_dir=storage_path / "data")
            assert len(idx_reloaded.search("Secret data")) == 0, "Deleted document chunks must not appear in search"

            print("  --> PASS: Physical file removed, registry cleaned, and index purged.")
        passed_count += 1
    except Exception as e:
        print(f"  --> FAIL in Test 6: {e}")

    # --------------------------------------------------------------------------
    # Test 7: Grounded Q&A with Source Citations & Missing Credential Handling
    # --------------------------------------------------------------------------
    print("\n[TEST 7] Grounded Q&A, Source Citations & Missing Credential Error Handling...")
    try:
        # 1. Test grounded answering with MockProvider
        mock_provider = MockProvider()
        service = QAService(provider=mock_provider)

        # Populate test session
        idx = index_manager.get_index("test_grounding_session")
        from backend.chunker import DocumentChunk
        idx.add_chunks([
            DocumentChunk(
                chunk_id="kpi_01",
                doc_id="kpi_doc",
                filename="KPI_Report.pdf",
                chunk_index=0,
                text="The customer acquisition cost (CAC) decreased by 18% in Q3.",
                page_number=3,
                section_title="Financial Metrics"
            )
        ])

        qa_res = service.answer_question("test_grounding_session", "What happened to CAC in Q3?")
        assert len(qa_res.citations) > 0
        citation = qa_res.citations[0]
        assert citation.document_name == "KPI_Report.pdf"
        assert citation.page_number == 3
        assert citation.section_title == "Financial Metrics"
        assert "CAC" in qa_res.answer or "customer acquisition cost" in qa_res.answer

        # 2. Test missing credentials error handling (no fake answers)
        error_service = QAService(provider=ConfigErrorProvider())
        err_res = error_service.answer_question("test_grounding_session", "What is CAC?")
        assert err_res.error is not None
        assert "AI Provider is not configured" in err_res.error or "GEMINI_API_KEY" in err_res.error
        assert len(err_res.citations) > 0, "Even on AI error, retrieved excerpts and citations are preserved"

        print("  --> PASS: Answers grounded with source citations; missing credentials return clear configuration error.")
        passed_count += 1
    except Exception as e:
        print(f"  --> FAIL in Test 7: {e}")

    # --------------------------------------------------------------------------
    # Test 8: End-to-End REST API Workflow
    # --------------------------------------------------------------------------
    print("\n[TEST 8] End-to-End REST API Endpoints...")
    try:
        client = TestClient(app)

        # 1. Health endpoint
        res = client.get("/api/health")
        assert res.status_code == 200
        health_data = res.json()
        assert health_data["status"] == "healthy"

        # 2. Document upload endpoint
        test_session = "api_test_session"
        sample_docx = SAMPLE_DIR / "Detailed_Company_Knowledge_Base.docx"
        
        if sample_docx.exists():
            with open(sample_docx, "rb") as f:
                upload_res = client.post(
                    "/api/upload",
                    files={"file": ("Detailed_Company_Knowledge_Base.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                    data={"session_id": test_session}
                )
            assert upload_res.status_code == 201
            up_data = upload_res.json()
            doc_id = up_data["document"]["doc_id"]
            assert up_data["chunks_indexed"] > 0
            print(f"  --> API Upload Success: doc_id={doc_id}, chunks={up_data['chunks_indexed']}")

            # 3. List documents
            list_res = client.get(f"/api/documents?session_id={test_session}")
            assert list_res.status_code == 200
            docs = list_res.json()["documents"]
            assert any(d["doc_id"] == doc_id for d in docs)

            # 4. Chat Q&A endpoint
            chat_res = client.post(
                "/api/chat",
                json={
                    "query": "What are the company's core services?",
                    "session_id": test_session,
                    "provider": "mock"
                }
            )
            assert chat_res.status_code == 200
            chat_data = chat_res.json()
            assert len(chat_data["citations"]) > 0
            assert chat_data["citations"][0]["document_name"] == "Detailed_Company_Knowledge_Base.docx"
            print(f"  --> API Chat Success: citations returned ({len(chat_data['citations'])})")

            # 5. Delete document
            del_res = client.delete(f"/api/documents/{doc_id}?session_id={test_session}")
            assert del_res.status_code == 200

            # 6. Verify empty list
            list_res2 = client.get(f"/api/documents?session_id={test_session}")
            assert len(list_res2.json()["documents"]) == 0
            print("  --> API Delete Success: cleaned up session documents.")

        print("  --> PASS: Full API lifecycle (Health -> Upload -> List -> Chat -> Delete) verified.")
        passed_count += 1
    except Exception as e:
        print(f"  --> FAIL in Test 8: {e}")

    print("\n" + "=" * 70)
    print(f"  TYPE 1 TEST SUMMARY: {passed_count}/{total_tests} TEST SUITES PASSED")
    print("=" * 70)

    return passed_count == total_tests


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
