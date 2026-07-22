const messagesEl = document.getElementById("messages");
const emptyStateEl = document.getElementById("empty-state");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const newChatBtn = document.getElementById("new-chat-btn");

marked.setOptions({ breaks: true });

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideEmptyState() {
  const el = document.getElementById("empty-state");
  if (el) el.style.display = "none";
}

function renderMarkdown(text) {
  return marked.parse(text || "");
}

function addMessageRow(role, initialHtml = "") {
  hideEmptyState();
  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = initialHtml;

  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollToBottom();
  return bubble;
}

function addTypingIndicator() {
  const bubble = addMessageRow(
    "assistant",
    '<div class="typing-dots"><span></span><span></span><span></span></div>'
  );
  return bubble;
}

function addErrorBubble(message) {
  const row = document.createElement("div");
  row.className = "message-row assistant";
  const bubble = document.createElement("div");
  bubble.className = "bubble error";
  bubble.textContent = message;
  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollToBottom();
}

// --- Load existing history on page load ---

async function loadHistory() {
  try {
    const res = await fetch("/api/history");
    const data = await res.json();
    if (data.history && data.history.length > 0) {
      hideEmptyState();
      for (const msg of data.history) {
        addMessageRow(msg.role, renderMarkdown(msg.content));
      }
    }
  } catch (err) {
    console.error("Failed to load history:", err);
  }
}

// --- Auto-resize textarea ---

inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + "px";
});

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    formEl.requestSubmit();
  }
});

// --- Send message + stream response ---

let isStreaming = false;

formEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = inputEl.value.trim();
  if (!message || isStreaming) return;

  addMessageRow("user", renderMarkdown(message));
  inputEl.value = "";
  inputEl.style.height = "auto";

  isStreaming = true;
  sendBtn.disabled = true;

  const typingBubble = addTypingIndicator();
  let started = false;
  let fullText = "";

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    if (!res.ok || !res.body) {
      throw new Error("Request failed");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop(); // keep any incomplete chunk

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        const jsonStr = line.slice(5).trim();
        if (!jsonStr) continue;

        let payload;
        try {
          payload = JSON.parse(jsonStr);
        } catch {
          continue;
        }

        if (payload.error) {
          typingBubble.parentElement.remove();
          addErrorBubble(payload.error);
          isStreaming = false;
          sendBtn.disabled = false;
          return;
        }

        if (payload.delta) {
          if (!started) {
            typingBubble.innerHTML = "";
            started = true;
          }
          fullText += payload.delta;
          typingBubble.innerHTML = renderMarkdown(fullText);
          scrollToBottom();
        }

        if (payload.done) {
          isStreaming = false;
          sendBtn.disabled = false;
        }
      }
    }
  } catch (err) {
    console.error(err);
    typingBubble.parentElement.remove();
    addErrorBubble("Couldn't reach the server. Check your connection and try again.");
  } finally {
    isStreaming = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }
});

// --- New chat ---

newChatBtn.addEventListener("click", async () => {
  try {
    await fetch("/api/new-chat", { method: "POST" });
  } catch (err) {
    console.error("Failed to start new chat:", err);
  }
  messagesEl.innerHTML =
    '<div class="empty-state" id="empty-state"><p>Say something to start the conversation.</p></div>';
  inputEl.value = "";
  inputEl.style.height = "auto";
  inputEl.focus();
});

// --- Init ---

loadHistory();
inputEl.focus();
