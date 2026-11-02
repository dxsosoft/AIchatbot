/**
 * AI Knowledge Assistant - Type 1 (File Upload)
 * Frontend Application Controller
 */

// -----------------------------------------------------------------------------
// State & Session Management
// -----------------------------------------------------------------------------
let currentSessionId = localStorage.getItem("ai_chatbot_session_id");
if (!currentSessionId) {
  currentSessionId = "usr_" + Math.random().toString(36).substring(2, 10);
  localStorage.setItem("ai_chatbot_session_id", currentSessionId);
}

const API_BASE = "";

// DOM Elements
const sessionLabel = document.getElementById("currentSessionLabel");
const switchSessionBtn = document.getElementById("switchSessionBtn");
const providerStatusText = document.getElementById("providerStatusText");
const systemStatusPill = document.getElementById("systemStatusPill");

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const uploadProgressCard = document.getElementById("uploadProgressCard");
const progressFileName = document.getElementById("progressFileName");
const progressPercent = document.getElementById("progressPercent");
const progressBarFill = document.getElementById("progressBarFill");

const documentsList = document.getElementById("documentsList");
const emptyDocsMsg = document.getElementById("emptyDocsMsg");
const docCountBadge = document.getElementById("docCountBadge");

const chatHistory = document.getElementById("chatHistory");
const welcomeHero = document.getElementById("welcomeHero");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const toastBanner = document.getElementById("toastBanner");
const toastMessage = document.getElementById("toastMessage");

// Initialize Session Display
sessionLabel.textContent = currentSessionId;

// -----------------------------------------------------------------------------
// Toast Notifications
// -----------------------------------------------------------------------------
function showToast(msg, type = "success") {
  toastMessage.textContent = msg;
  toastBanner.className = `toast-banner toast-${type}`;
  toastBanner.style.display = "flex";
  setTimeout(() => {
    toastBanner.style.display = "none";
  }, 4000);
}

// -----------------------------------------------------------------------------
// System Health & Provider Check
// -----------------------------------------------------------------------------
async function checkSystemHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    if (!res.ok) throw new Error("Health check failed");
    const data = await res.json();
    const cfg = data.configuration;

    if (cfg.gemini_configured) {
      providerStatusText.textContent = "AI Ready (Gemini)";
      systemStatusPill.style.color = "var(--accent-emerald)";
    } else if (cfg.openai_configured) {
      providerStatusText.textContent = "AI Ready (OpenAI)";
      systemStatusPill.style.color = "var(--accent-emerald)";
    } else if (cfg.configured_provider === "mock") {
      providerStatusText.textContent = "AI Ready (Mock/Test)";
      systemStatusPill.style.color = "var(--accent-cyan)";
    } else {
      providerStatusText.textContent = "No API Key in .env";
      systemStatusPill.style.color = "var(--accent-amber)";
    }
  } catch (err) {
    providerStatusText.textContent = "Offline / Error";
    systemStatusPill.style.color = "var(--accent-rose)";
  }
}

// -----------------------------------------------------------------------------
// Document Listing & Deletion
// -----------------------------------------------------------------------------
function formatBytes(bytes) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

async function loadDocuments() {
  try {
    const res = await fetch(`${API_BASE}/api/documents?session_id=${encodeURIComponent(currentSessionId)}`, {
      headers: { "X-Session-Id": currentSessionId }
    });
    if (!res.ok) throw new Error("Failed to load documents");
    const data = await res.json();
    const docs = data.documents || [];

    docCountBadge.textContent = `${docs.length} file${docs.length === 1 ? "" : "s"}`;

    if (docs.length === 0) {
      emptyDocsMsg.style.display = "block";
      // Clear cards except empty message
      const cards = documentsList.querySelectorAll(".doc-card");
      cards.forEach(c => c.remove());
      return;
    }

    emptyDocsMsg.style.display = "none";
    // Retain empty message element, remove existing cards
    const cards = documentsList.querySelectorAll(".doc-card");
    cards.forEach(c => c.remove());

    docs.forEach(doc => {
      const card = document.createElement("div");
      card.className = "doc-card";
      card.innerHTML = `
        <div class="doc-info">
          <div class="doc-type-icon type-${doc.file_type}">${doc.file_type}</div>
          <div class="doc-details">
            <span class="doc-name" title="${doc.filename}">${doc.filename}</span>
            <span class="doc-meta">
              <span>${formatBytes(doc.file_size_bytes)}</span>
              <span>•</span>
              <span class="doc-chunks-pill">${doc.chunk_count} chunk${doc.chunk_count === 1 ? "" : "s"}</span>
            </span>
          </div>
        </div>
        <button class="doc-delete-btn" title="Delete document from index" data-doc-id="${doc.doc_id}">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
        </button>
      `;

      card.querySelector(".doc-delete-btn").addEventListener("click", () => deleteDocument(doc.doc_id, doc.filename));
      documentsList.appendChild(card);
    });
  } catch (err) {
    console.error("Error loading documents:", err);
  }
}

async function deleteDocument(docId, filename) {
  if (!confirm(`Delete '${filename}' and remove its content from the search index?`)) return;

  try {
    const res = await fetch(`${API_BASE}/api/documents/${docId}?session_id=${encodeURIComponent(currentSessionId)}`, {
      method: "DELETE",
      headers: { "X-Session-Id": currentSessionId }
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Deletion failed");
    }

    showToast(`Removed '${filename}'`, "success");
    await loadDocuments();
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

// -----------------------------------------------------------------------------
// File Upload Handling
// -----------------------------------------------------------------------------
dropzone.addEventListener("click", () => fileInput.click());

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});

dropzone.addEventListener("dragleave", () => {
  dropzone.classList.remove("dragover");
});

dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files.length > 0) {
    handleFileUpload(e.dataTransfer.files);
  }
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) {
    handleFileUpload(fileInput.files);
  }
});

async function handleFileUpload(files) {
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    uploadProgressCard.style.display = "block";
    progressFileName.textContent = `Processing '${file.name}'...`;
    progressPercent.textContent = "30%";
    progressBarFill.style.width = "30%";

    const formData = new FormData();
    formData.append("file", file);
    formData.append("session_id", currentSessionId);

    try {
      progressBarFill.style.width = "65%";
      progressPercent.textContent = "65%";

      const res = await fetch(`${API_BASE}/api/upload`, {
        method: "POST",
        headers: { "X-Session-Id": currentSessionId },
        body: formData
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Upload rejected");
      }

      progressBarFill.style.width = "100%";
      progressPercent.textContent = "100%";

      showToast(`Indexed '${data.document.filename}' (${data.chunks_indexed} chunks)`, "success");
      await loadDocuments();
    } catch (err) {
      showToast(`Upload failed: ${err.message}`, "error");
    } finally {
      setTimeout(() => {
        uploadProgressCard.style.display = "none";
        progressBarFill.style.width = "0%";
      }, 1000);
    }
  }

  fileInput.value = "";
}

// -----------------------------------------------------------------------------
// Session Switcher
// -----------------------------------------------------------------------------
switchSessionBtn.addEventListener("click", () => {
  const newSession = prompt("Enter a session identifier for isolated storage & chat:", currentSessionId);
  if (newSession && newSession.trim() && newSession.trim() !== currentSessionId) {
    currentSessionId = newSession.trim();
    localStorage.setItem("ai_chatbot_session_id", currentSessionId);
    sessionLabel.textContent = currentSessionId;
    loadDocuments();
    clearChatHistory();
    showToast(`Switched to session: ${currentSessionId}`, "success");
  }
});

function clearChatHistory() {
  chatHistory.innerHTML = "";
  if (welcomeHero) {
    chatHistory.appendChild(welcomeHero);
  }
}

// -----------------------------------------------------------------------------
// Interactive Chat & Grounding
// -----------------------------------------------------------------------------
chatInput.addEventListener("input", () => {
  chatInput.style.height = "auto";
  chatInput.style.height = `${Math.min(chatInput.scrollHeight, 140)}px`;
});

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    chatForm.dispatchEvent(new Event("submit"));
  }
});

// Prompt Suggestions
document.querySelectorAll(".prompt-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const q = btn.getAttribute("data-query");
    chatInput.value = q;
    chatForm.dispatchEvent(new Event("submit"));
  });
});

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = chatInput.value.trim();
  if (!query) return;

  // Remove welcome banner on first prompt
  if (welcomeHero && welcomeHero.parentNode) {
    welcomeHero.remove();
  }

  // 1. Add user message
  appendUserMessage(query);
  chatInput.value = "";
  chatInput.style.height = "38px";
  sendBtn.disabled = true;

  // 2. Add thinking bubble
  const thinkingId = appendThinkingBubble();
  chatHistory.scrollTop = chatHistory.scrollHeight;

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-Id": currentSessionId
      },
      body: JSON.stringify({
        query: query,
        session_id: currentSessionId,
        top_k: 5
      })
    });

    const data = await res.json();
    removeBubble(thinkingId);

    if (!res.ok) {
      appendAssistantMessage(`Error: ${data.detail || "Failed to process query"}`, []);
      return;
    }

    appendAssistantMessage(data.answer, data.citations || [], data.error);
  } catch (err) {
    removeBubble(thinkingId);
    appendAssistantMessage(`Network error connecting to assistant: ${err.message}`, []);
  } finally {
    sendBtn.disabled = false;
    chatHistory.scrollTop = chatHistory.scrollHeight;
  }
});

function appendUserMessage(text) {
  const row = document.createElement("div");
  row.className = "message-row user-row";
  row.innerHTML = `
    <div class="message-bubble">${escapeHtml(text)}</div>
    <div class="message-avatar avatar-user">You</div>
  `;
  chatHistory.appendChild(row);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

function appendThinkingBubble() {
  const id = "thinking_" + Date.now();
  const row = document.createElement("div");
  row.id = id;
  row.className = "message-row";
  row.innerHTML = `
    <div class="message-avatar avatar-bot">AI</div>
    <div class="message-bubble">
      <div class="typing-dots">
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
      </div>
    </div>
  `;
  chatHistory.appendChild(row);
  return id;
}

function removeBubble(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function renderMarkdown(raw) {
  // Simple clean markdown parser for bullets, bold, and code blocks
  let html = escapeHtml(raw);

  // Bold
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

  // Code inline
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Bullet items
  html = html.replace(/^\s*-\s+(.*)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>");

  // Paragraphs
  const paras = html.split("\n\n").map(p => {
    p = p.trim();
    if (p.startsWith("<ul>") || p.startsWith("<li>") || p.startsWith("<h")) return p;
    return `<p>${p.replace(/\n/g, "<br>")}</p>`;
  });

  return paras.join("");
}

function appendAssistantMessage(answerText, citations = [], errorDetail = null) {
  const row = document.createElement("div");
  row.className = "message-row";

  let citationsHtml = "";
  if (citations && citations.length > 0) {
    const citationCards = citations.map(c => {
      const badgeParts = [];
      if (c.page_number) badgeParts.push(`Page ${c.page_number}`);
      if (c.sheet_name) badgeParts.push(`Sheet: ${c.sheet_name}`);
      if (c.section_title) badgeParts.push(c.section_title);
      const badgeLabel = badgeParts.join(" • ") || "Section";
      const scorePct = Math.round(c.relevance_score * 100);

      return `
        <div class="citation-card">
          <div class="citation-header">
            <span class="citation-source" title="${c.document_name}">📄 ${escapeHtml(c.document_name)}</span>
            <span class="citation-badge">${escapeHtml(badgeLabel)} (${scorePct}%)</span>
          </div>
          <div class="citation-snippet" title="${escapeHtml(c.snippet)}">"${escapeHtml(c.snippet)}"</div>
        </div>
      `;
    }).join("");

    citationsHtml = `
      <div class="citations-box">
        <div class="citations-label">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="16" x2="12" y2="12"/>
            <line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
          Grounding Sources (${citations.length})
        </div>
        <div class="citations-grid">
          ${citationCards}
        </div>
      </div>
    `;
  }

  row.innerHTML = `
    <div class="message-avatar avatar-bot">AI</div>
    <div class="message-bubble">
      ${renderMarkdown(answerText)}
      ${citationsHtml}
    </div>
  `;

  chatHistory.appendChild(row);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// -----------------------------------------------------------------------------
// Page Bootstrap
// -----------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  checkSystemHealth();
  loadDocuments();
});
