const chatState = {
  messages: [],
};

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "request failed");
  }
  return data;
}

function renderStats(stats) {
  const statsNode = document.getElementById("stats");
  statsNode.innerHTML = `
    <div class="stat-item"><strong>${stats.document_count}</strong><span>Documents</span></div>
    <div class="stat-item"><strong>${stats.chunk_count}</strong><span>Chunks</span></div>
    <div class="stat-item"><strong>${stats.vector_count}</strong><span>Vectors</span></div>
  `;
}

function renderFiles(files) {
  const select = document.getElementById("pdf-select");
  select.innerHTML = "";
  if (!files.length) {
    const option = document.createElement("option");
    option.value = "";
    option.dataset.documentId = "";
    option.textContent = "No PDF found. Upload one or put it into the pdfs folder.";
    select.appendChild(option);
    return;
  }
  files.forEach((file) => {
    const option = document.createElement("option");
    option.value = file.document_id || file.path;
    option.dataset.documentId = file.document_id || "";
    option.dataset.path = file.path || "";
    option.textContent = file.name;
    select.appendChild(option);
  });
}

function sourceMarkup(sources) {
  if (!sources || !sources.length) {
    return `<div class="source-empty">No source snippets returned for this turn.</div>`;
  }
  return sources
    .map(
      (source) => `
        <details class="source-item">
          <summary>${source.document_name || "Unknown document"} | score ${source.score}</summary>
          <div class="source-text">${escapeHtml(source.text)}</div>
        </details>
      `,
    )
    .join("");
}

function renderChat() {
  const history = document.getElementById("chat-history");
  const emptyState = document.getElementById("empty-chat");

  if (!chatState.messages.length) {
    history.innerHTML = "";
    history.appendChild(emptyState);
    return;
  }

  history.innerHTML = chatState.messages
    .map((message) => {
      if (message.role === "user") {
        return `
          <article class="message-row user">
            <div class="message-bubble user-bubble">
              <div class="message-role">User</div>
              <div class="message-content">${escapeHtml(message.content)}</div>
            </div>
          </article>
        `;
      }
      return `
        <article class="message-row assistant">
          <div class="message-bubble assistant-bubble">
            <div class="message-role">Assistant</div>
            <div class="message-content">${escapeHtml(message.content)}</div>
            <div class="message-meta">
              <span>Time ${message.durationMs ?? "-"} ms</span>
              <span>Sources ${message.sourceCount ?? 0}</span>
            </div>
            <div class="message-sources">
              ${sourceMarkup(message.sources)}
            </div>
          </div>
        </article>
      `;
    })
    .join("");

  history.scrollTop = history.scrollHeight;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
    .replaceAll("\n", "<br>");
}

function appendUserMessage(question) {
  chatState.messages.push({ role: "user", content: question });
  renderChat();
}

function setPendingAssistant() {
  chatState.messages.push({
    role: "assistant",
    content: "Generating answer...",
    sources: [],
    sourceCount: 0,
    durationMs: "-",
    pending: true,
  });
  renderChat();
}

function replacePendingAssistant(replacement) {
  const index = chatState.messages.findIndex((item) => item.pending);
  if (index >= 0) {
    chatState.messages.splice(index, 1, replacement);
  } else {
    chatState.messages.push(replacement);
  }
  renderChat();
}

function toBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      const base64 = String(result).split(",")[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function refreshDashboard() {
  const [filesResult, statsResult] = await Promise.all([
    request("/api/files"),
    request("/api/stats"),
  ]);
  renderFiles(filesResult.files);
  renderStats(statsResult);
}

async function ingestSelectedPath() {
  const select = document.getElementById("pdf-select");
  const selectedOption = select.options[select.selectedIndex];
  const resultBox = document.getElementById("ingest-result");
  try {
    resultBox.textContent = "Importing PDF...";
    const result = await request("/api/ingest-path", {
      method: "POST",
      body: JSON.stringify({ pdf_path: selectedOption?.dataset.path || select.value }),
    });
    resultBox.textContent = JSON.stringify(result, null, 2);
    await refreshDashboard();
  } catch (error) {
    resultBox.textContent = error.message;
  }
}

async function uploadAndIngest() {
  const input = document.getElementById("pdf-upload");
  const resultBox = document.getElementById("ingest-result");
  const file = input.files[0];
  if (!file) {
    resultBox.textContent = "Please choose a PDF file first.";
    return;
  }
  try {
    resultBox.textContent = "Uploading and importing PDF...";
    const contentBase64 = await toBase64(file);
    const result = await request("/api/ingest-file", {
      method: "POST",
      body: JSON.stringify({
        filename: file.name,
        content_base64: contentBase64,
      }),
    });
    resultBox.textContent = JSON.stringify(result, null, 2);
    input.value = "";
    await refreshDashboard();
  } catch (error) {
    resultBox.textContent = error.message;
  }
}

async function askQuestion() {
  const input = document.getElementById("question-input");
  const select = document.getElementById("pdf-select");
  const selectedOption = select.options[select.selectedIndex];
  const question = input.value.trim();
  if (!question) {
    chatState.messages.push({
      role: "assistant",
      content: "Please enter a question.",
      sources: [],
      sourceCount: 0,
      durationMs: "-",
    });
    renderChat();
    return;
  }

  appendUserMessage(question);
  input.value = "";
  setPendingAssistant();

  try {
    const result = await request("/api/ask", {
      method: "POST",
      body: JSON.stringify({
        question,
        document_id: selectedOption?.dataset.documentId || "",
      }),
    });
    replacePendingAssistant({
      role: "assistant",
      content: result.answer || "No answer returned.",
      sources: result.sources || [],
      sourceCount: result.source_count || 0,
      durationMs: result.duration_ms ?? "-",
    });
  } catch (error) {
    replacePendingAssistant({
      role: "assistant",
      content: `Request failed: ${error.message}`,
      sources: [],
      sourceCount: 0,
      durationMs: "-",
    });
  }
}

function clearChat() {
  chatState.messages = [];
  renderChat();
}

document.getElementById("ingest-path-btn").addEventListener("click", ingestSelectedPath);
document.getElementById("upload-btn").addEventListener("click", uploadAndIngest);
document.getElementById("ask-btn").addEventListener("click", askQuestion);
document.getElementById("clear-chat-btn").addEventListener("click", clearChat);
document.getElementById("question-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    askQuestion();
  }
});

refreshDashboard().catch((error) => {
  document.getElementById("ingest-result").textContent = error.message;
});

renderChat();
