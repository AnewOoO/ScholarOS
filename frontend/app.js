const STORAGE_SESSION = "scholaros.session_id";
const STORAGE_CANDIDATES_PREFIX = "scholaros.candidates.";

const state = {
  sessionId: localStorage.getItem(STORAGE_SESSION) || "",
  profileTimer: null,
  libraryPapers: [],
  candidates: [],
  builderSuggestionBuckets: {},
  builderSuggestionSeq: 0,
};

const els = {
  libraryStatus: document.querySelector("#libraryStatus"),
  sessionList: document.querySelector("#sessionList"),
  newSessionButton: document.querySelector("#newSessionButton"),
  refreshSessionsButton: document.querySelector("#refreshSessionsButton"),
  profileInput: document.querySelector("#profileInput"),

  tabs: document.querySelectorAll(".agent-tab"),
  panels: {
    builder: document.querySelector("#builderPanel"),
    reader: document.querySelector("#readerPanel"),
    code: document.querySelector("#codePanel"),
    writer: document.querySelector("#writerPanel"),
  },

  builderForm: document.querySelector("#builderForm"),
  directionInput: document.querySelector("#directionInput"),
  limitInput: document.querySelector("#limitInput"),
  sortInput: document.querySelector("#sortInput"),
  skipPdfInput: document.querySelector("#skipPdfInput"),
  builderButton: document.querySelector("#builderButton"),
  builderStatus: document.querySelector("#builderStatus"),
  builderTrace: document.querySelector("#builderTrace"),
  keywordList: document.querySelector("#keywordList"),
  sourceStats: document.querySelector("#sourceStats"),
  candidateList: document.querySelector("#candidateList"),
  builderChatForm: document.querySelector("#builderChatForm"),
  builderChatInput: document.querySelector("#builderChatInput"),
  builderChatButton: document.querySelector("#builderChatButton"),
  builderChatMessages: document.querySelector("#builderChatMessages"),

  readerForm: document.querySelector("#readerForm"),
  readerPaperSelect: document.querySelector("#readerPaperSelect"),
  readerPromptInput: document.querySelector("#readerPromptInput"),
  includePdfInput: document.querySelector("#includePdfInput"),
  readerButton: document.querySelector("#readerButton"),
  readerStatus: document.querySelector("#readerStatus"),
  readerOutput: document.querySelector("#readerOutput"),

  codeForm: document.querySelector("#codeForm"),
  repoInput: document.querySelector("#repoInput"),
  codePaperSelect: document.querySelector("#codePaperSelect"),
  codeQuestionInput: document.querySelector("#codeQuestionInput"),
  codeButton: document.querySelector("#codeButton"),
  codeStatus: document.querySelector("#codeStatus"),
  codeOutput: document.querySelector("#codeOutput"),

  writerForm: document.querySelector("#writerForm"),
  writerModeSelect: document.querySelector("#writerModeSelect"),
  writerPromptInput: document.querySelector("#writerPromptInput"),
  experimentNotesInput: document.querySelector("#experimentNotesInput"),
  draftInput: document.querySelector("#draftInput"),
  writerButton: document.querySelector("#writerButton"),
  writerStatus: document.querySelector("#writerStatus"),
  writerOutput: document.querySelector("#writerOutput"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

function renderMarkdown(value) {
  if (window.ScholarOSMarkdown?.render) {
    return window.ScholarOSMarkdown.render(value);
  }
  return `<p>${escapeHtml(value)}</p>`;
}

function formatDate(value) {
  return value ? String(value).slice(0, 10) : "unknown";
}

function formatTime(seconds) {
  if (!seconds) return "";
  return new Date(seconds * 1000).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function paperKey(paper) {
  return String(paper?.arxiv_id || paper?.url || paper?.title || "");
}

function paperPool() {
  const seen = new Set();
  const papers = [];
  for (const item of [...state.libraryPapers, ...state.candidates]) {
    const key = paperKey(item);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    papers.push(item);
  }
  return papers;
}

function selectedPaper(selectEl) {
  const key = selectEl.value;
  if (!key) return null;
  return paperPool().find((paper) => paperKey(paper) === key) || null;
}

function candidateStorageKey() {
  return `${STORAGE_CANDIDATES_PREFIX}${state.sessionId}`;
}

function saveCandidates() {
  if (!state.sessionId) return;
  sessionStorage.setItem(candidateStorageKey(), JSON.stringify(state.candidates.slice(0, 40)));
}

function loadCandidates() {
  if (!state.sessionId) return [];
  try {
    const saved = JSON.parse(sessionStorage.getItem(candidateStorageKey()) || "[]");
    return Array.isArray(saved) ? saved : [];
  } catch {
    return [];
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "请求失败");
  }
  return payload;
}

function postJson(url, body) {
  return fetchJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function parseSseEvent(eventChunk) {
  const eventName = eventChunk.match(/^event:\s*(.+)$/m)?.[1] || "";
  const data = eventChunk
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.replace(/^data:\s?/, ""))
    .join("\n");
  return { eventName, data };
}

function setAgentPanel(agent) {
  els.tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.agent === agent));
  Object.entries(els.panels).forEach(([key, panel]) => {
    panel.classList.toggle("active", key === agent);
  });
  refreshPaperSelects();
}

function renderSessions(sessions) {
  if (!sessions?.length) {
    els.sessionList.innerHTML = `<div class="empty-state compact">暂无历史论文库。</div>`;
    return;
  }
  els.sessionList.innerHTML = sessions
    .map(
      (session) => `
        <article class="session-item ${session.id === state.sessionId ? "active" : ""}" data-session-id="${escapeAttr(session.id)}">
          <button class="session-main" type="button" data-action="open">
            <span class="session-title">${escapeHtml(session.title || "新的论文库")}</span>
            <span class="session-meta">${escapeHtml(session.paper_count ?? 0)} 篇 · ${escapeHtml(
              session.message_count ?? 0,
            )} 条 · ${escapeHtml(formatTime(session.updated_at))}</span>
          </button>
          <div class="session-actions">
            <button class="tiny-button" type="button" data-action="rename">改名</button>
            <button class="tiny-button danger" type="button" data-action="delete">删除</button>
          </div>
        </article>
      `,
    )
    .join("");
}

function applySession(session, { preserveCandidates = true } = {}) {
  state.sessionId = session.id;
  localStorage.setItem(STORAGE_SESSION, state.sessionId);
  state.libraryPapers = Array.isArray(session.papers) ? session.papers : [];
  state.candidates = preserveCandidates ? loadCandidates() : [];
  els.profileInput.value = session.profile || "";
  els.libraryStatus.textContent = `论文库：${session.title || "新的论文库"} · ${state.libraryPapers.length} 篇`;
  refreshPaperSelects();
  renderCandidateList();
  renderBuilderChat(session.messages || []);
}

async function loadSession() {
  const url = state.sessionId ? `/api/session/${state.sessionId}` : "/api/session";
  const method = state.sessionId ? "GET" : "POST";
  const payload = await fetchJson(url, { method });
  applySession(payload.session);
  await loadSessions();
}

async function loadSessions() {
  const payload = await fetchJson("/api/sessions");
  renderSessions(payload.sessions);
}

async function createNewSession() {
  const payload = await fetchJson("/api/session", { method: "POST" });
  sessionStorage.removeItem(candidateStorageKey());
  applySession(payload.session, { preserveCandidates: false });
  await loadSessions();
}

async function openSession(sessionId) {
  const payload = await fetchJson(`/api/session/${sessionId}`);
  applySession(payload.session);
  await loadSessions();
}

function currentSessionTitle(sessionId) {
  const item = [...els.sessionList.querySelectorAll(".session-item")].find((node) => node.dataset.sessionId === sessionId);
  return item?.querySelector(".session-title")?.textContent || "新的论文库";
}

async function renameSession(sessionId) {
  const title = window.prompt("输入新的论文库名称", currentSessionTitle(sessionId));
  if (!title?.trim()) return;
  const payload = await fetchJson(`/api/session/${sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: title.trim() }),
  });
  if (sessionId === state.sessionId) applySession(payload.session);
  await loadSessions();
}

async function deleteSession(sessionId) {
  if (!window.confirm("确定删除这个论文库吗？对话和论文关联会一起隐藏。")) return;
  await fetchJson(`/api/session/${sessionId}`, { method: "DELETE" });
  if (sessionId === state.sessionId) {
    localStorage.removeItem(STORAGE_SESSION);
    state.sessionId = "";
    await createNewSession();
  } else {
    await loadSessions();
  }
}

async function saveProfile() {
  if (!state.sessionId) return;
  await fetchJson(`/api/session/${state.sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile: els.profileInput.value }),
  });
  await loadSessions();
}

function refreshPaperSelects() {
  const pool = paperPool();
  const options = [
    `<option value="">不指定，使用当前论文库或自动检索</option>`,
    ...pool.map(
      (paper) =>
        `<option value="${escapeAttr(paperKey(paper))}">${escapeHtml(paper.title || "Untitled")} · ${escapeHtml(
          paper.arxiv_id || paper.source || "paper",
        )}</option>`,
    ),
  ].join("");
  els.readerPaperSelect.innerHTML = options;
  els.codePaperSelect.innerHTML = options;
}

function renderCandidateList() {
  if (!state.candidates.length) {
    els.candidateList.innerHTML = `<div class="empty-state">暂无候选论文。先让 Paper Builder 检索一个研究方向。</div>`;
    return;
  }
  els.candidateList.innerHTML = state.candidates
    .map((paper, index) => {
      const inLibrary = state.libraryPapers.some((item) => paperKey(item) === paperKey(paper));
      return `
        <article class="paper-card">
          <div class="paper-card-main">
            <div class="paper-meta">${escapeHtml(formatDate(paper.published))} · ${escapeHtml(
              paper.source || "paper source",
            )} · score ${escapeHtml(paper.relevance_score ?? "n/a")}</div>
            <h3>${index + 1}. ${escapeHtml(paper.title || "Untitled")}</h3>
            <p>${escapeHtml(paper.summary || paper.abstract || "当前候选没有摘要。")}</p>
            <p class="reason">${escapeHtml(paper.recommendation_reason || "与研究方向相关。")}</p>
          </div>
          <div class="paper-actions">
            <button class="tiny-button" type="button" data-action="read" data-index="${index}">精读</button>
            <button class="tiny-button" type="button" data-action="add" data-index="${index}" ${inLibrary ? "disabled" : ""}>
              ${inLibrary ? "已加入" : "加入库"}
            </button>
            <a href="${escapeAttr(paper.url || "#")}" target="_blank" rel="noreferrer">打开</a>
          </div>
        </article>
      `;
    })
    .join("");
}

function mergeCandidates(papers) {
  const incoming = Array.isArray(papers) ? papers : [];
  if (!incoming.length) return [];

  const seen = new Set(state.candidates.map((paper) => paperKey(paper)).filter(Boolean));
  const added = [];
  for (const paper of incoming) {
    const key = paperKey(paper);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    state.candidates.push(paper);
    added.push(paper);
  }
  if (added.length) {
    saveCandidates();
    renderCandidateList();
    refreshPaperSelects();
  }
  return added;
}

function renderBuilderMessage(role, content = "") {
  const message = document.createElement("article");
  message.className = `builder-message ${role}`;
  message.innerHTML = `
    <div class="builder-message-role">${role === "user" ? "你" : "Paper Builder"}</div>
    <div class="builder-message-content">${role === "assistant" ? renderMarkdown(content) : escapeHtml(content)}</div>
  `;
  els.builderChatMessages.appendChild(message);
  els.builderChatMessages.scrollTop = els.builderChatMessages.scrollHeight;
  return message.querySelector(".builder-message-content");
}

function updateBuilderMessage(el, content) {
  el.innerHTML = renderMarkdown(content);
  els.builderChatMessages.scrollTop = els.builderChatMessages.scrollHeight;
}

function renderBuilderChat(messages) {
  if (!els.builderChatMessages) return;
  els.builderChatMessages.innerHTML = "";
  const useful = (Array.isArray(messages) ? messages : []).filter((message) =>
    ["user", "assistant"].includes(message.role),
  );
  if (!useful.length) {
    renderBuilderMessage(
      "assistant",
      "你可以先用左侧表单做一次自动检索，也可以直接在这里告诉我：研究方向、筛选偏好、是否需要代码、年份范围和你想排除的论文类型。我给出的候选只会进入候选池，不会自动加入知识库。",
    );
    return;
  }
  useful.slice(-8).forEach((message) => renderBuilderMessage(message.role, message.content));
}

function renderBuilderSuggestionCard(paper, index) {
  const inLibrary = state.libraryPapers.some((item) => paperKey(item) === paperKey(paper));
  return `
    <article class="builder-suggestion-card">
      <div>
        <h4>${escapeHtml(paper.title || "Untitled")}</h4>
        <p>${escapeHtml(formatDate(paper.published))} · ${escapeHtml(paper.source || "paper")} · ${escapeHtml(
          paper.recommendation_reason || paper.summary || "候选论文",
        )}</p>
      </div>
      <div class="paper-actions">
        <button class="tiny-button" type="button" data-action="chat-read" data-index="${index}">精读</button>
        <button class="tiny-button" type="button" data-action="chat-add" data-index="${index}" ${inLibrary ? "disabled" : ""}>
          ${inLibrary ? "已加入" : "加入库"}
        </button>
        <a href="${escapeAttr(paper.url || "#")}" target="_blank" rel="noreferrer">打开</a>
      </div>
    </article>
  `;
}

function renderBuilderSuggestions(container, papers) {
  const list = Array.isArray(papers) ? papers : [];
  if (!list.length) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = `
    <div class="builder-suggestion-title">本轮候选，等待你确认</div>
    <div class="builder-suggestion-list">${list.map(renderBuilderSuggestionCard).join("")}</div>
  `;
}

function refreshBuilderSuggestionButtons() {
  document.querySelectorAll(".builder-suggestions").forEach((container) => {
    const papers = state.builderSuggestionBuckets[container.dataset.suggestionId] || [];
    renderBuilderSuggestions(container, papers);
  });
}

function renderBuilderTrace(payload) {
  els.builderTrace.innerHTML = renderMarkdown(payload.message || "");
  els.keywordList.innerHTML = (payload.expanded_keywords || [])
    .map((keyword) => `<span class="chip">${escapeHtml(keyword)}</span>`)
    .join("");
  els.sourceStats.innerHTML = Object.entries(payload.sources || {})
    .map(([source, count]) => `<span><strong>${escapeHtml(count)}</strong>${escapeHtml(source)}</span>`)
    .join("");
}

async function addPaperObjectToLibrary(paper) {
  if (!paper || !state.sessionId) return;
  const payload = await postJson(`/api/session/${state.sessionId}/papers`, { paper });
  state.libraryPapers = payload.session.papers || [];
  els.libraryStatus.textContent = `论文库：${payload.session.title || "新的论文库"} · ${state.libraryPapers.length} 篇`;
  renderCandidateList();
  refreshBuilderSuggestionButtons();
  refreshPaperSelects();
  await loadSessions();
}

async function runBuilder(event) {
  event.preventDefault();
  els.builderButton.disabled = true;
  els.builderStatus.textContent = "Paper Builder 正在扩展关键词并检索论文源...";
  els.builderTrace.innerHTML = "";
  els.keywordList.innerHTML = "";
  els.sourceStats.innerHTML = "";

  try {
    const payload = await postJson("/api/agents/paper-builder", {
      session_id: state.sessionId,
      direction: els.directionInput.value.trim(),
      limit: Number(els.limitInput.value || 5),
      sort: els.sortInput.value,
      skip_pdf: els.skipPdfInput.checked,
      skip_citations: els.skipPdfInput.checked,
    });
    state.sessionId = payload.session_id;
    localStorage.setItem(STORAGE_SESSION, state.sessionId);
    state.candidates = payload.papers || [];
    saveCandidates();
    renderBuilderTrace(payload);
    renderCandidateList();
    refreshPaperSelects();
    els.builderStatus.textContent = `找到 ${payload.candidate_count || state.candidates.length} 条候选，推荐 ${state.candidates.length} 篇优先阅读。`;
    await loadSessions();
  } catch (error) {
    els.builderStatus.textContent = `构建失败：${error.message}`;
    els.candidateList.innerHTML = `<div class="error-state">${escapeHtml(error.message)}</div>`;
  } finally {
    els.builderButton.disabled = false;
  }
}

async function streamBuilderChat(event) {
  event.preventDefault();
  const content = els.builderChatInput.value.trim();
  if (!content) return;

  els.builderChatInput.value = "";
  els.builderChatButton.disabled = true;
  renderBuilderMessage("user", content);
  const assistantEl = renderBuilderMessage("assistant", "");
  const suggestionContainer = document.createElement("div");
  suggestionContainer.className = "builder-suggestions";
  const suggestionId = `builder-suggestions-${++state.builderSuggestionSeq}`;
  suggestionContainer.dataset.suggestionId = suggestionId;
  assistantEl.parentElement.appendChild(suggestionContainer);
  state.builderSuggestionBuckets[suggestionId] = [];

  let assistantText = "";
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: state.sessionId,
        agent: "paper_builder",
        messages: [{ role: "user", content }],
        profile: els.profileInput.value,
        papers: paperPool(),
      }),
    });

    if (!response.ok || !response.body) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Paper Builder 对话失败");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";

      for (const eventChunk of events) {
        const { eventName, data } = parseSseEvent(eventChunk);
        if (!data || eventName === "done") continue;
        if (eventName === "error") {
          const payload = JSON.parse(data);
          throw new Error(payload.error || "Paper Builder stream failed");
        }
        const payload = JSON.parse(data);
        if (eventName === "papers") {
          const papers = payload.papers || [];
          state.builderSuggestionBuckets[suggestionId] = papers;
          mergeCandidates(papers);
          renderBuilderSuggestions(suggestionContainer, papers);
          els.builderStatus.textContent = `对话中发现 ${papers.length} 篇候选，仍需你手动加入知识库。`;
          continue;
        }
        assistantText += payload.delta || "";
        updateBuilderMessage(assistantEl, assistantText);
      }
    }

    if (!assistantText) {
      updateBuilderMessage(assistantEl, "我已经更新候选池。你可以继续告诉我筛选偏好，或点击候选卡片加入知识库。");
    }
    await loadSessions();
  } catch (error) {
    updateBuilderMessage(assistantEl, `请求失败：${error.message}`);
  } finally {
    els.builderChatButton.disabled = false;
    els.builderChatInput.focus();
  }
}

async function runReader(event) {
  event.preventDefault();
  els.readerButton.disabled = true;
  els.readerStatus.textContent = "正在结合论文上下文生成精读回答...";
  els.readerOutput.classList.remove("empty-state");
  els.readerOutput.innerHTML = "生成中...";

  try {
    const paper = selectedPaper(els.readerPaperSelect);
    const payload = await postJson("/api/agents/paper-reader", {
      session_id: state.sessionId,
      prompt: els.readerPromptInput.value.trim(),
      paper,
      papers: paper ? [] : state.libraryPapers,
      include_pdf: els.includePdfInput.checked,
    });
    const sections = Object.entries(payload.deep_read || {})
      .map(([name, text]) => `### ${sectionName(name)}\n${text}`)
      .join("\n\n");
    const pdfNote = payload.pdf_error ? `\n\n> PDF 读取失败：${payload.pdf_error}` : "";
    els.readerOutput.innerHTML = renderMarkdown(`${payload.answer || ""}\n\n${sections}${pdfNote}`.trim());
    els.readerStatus.textContent = payload.searched ? "已自动检索并合成回答" : "已基于所选论文生成";
  } catch (error) {
    els.readerStatus.textContent = "精读失败";
    els.readerOutput.innerHTML = `<div class="error-state">${escapeHtml(error.message)}</div>`;
  } finally {
    els.readerButton.disabled = false;
  }
}

function sectionName(name) {
  return (
    {
      overview: "总览",
      method: "方法",
      experiments: "实验",
      critique: "批判阅读",
    }[name] || name
  );
}

async function runCodeInterpreter(event) {
  event.preventDefault();
  els.codeButton.disabled = true;
  els.codeStatus.textContent = "正在读取仓库并分析结构...";
  els.codeOutput.classList.remove("empty-state");
  els.codeOutput.innerHTML = "分析中...";

  try {
    const payload = await postJson("/api/agents/code-interpreter", {
      session_id: state.sessionId,
      repo_url: els.repoInput.value.trim(),
      paper: selectedPaper(els.codePaperSelect),
      question: els.codeQuestionInput.value.trim(),
    });
    els.codeOutput.innerHTML = renderMarkdown(formatCodeOutput(payload));
    els.codeStatus.textContent = "仓库分析完成";
  } catch (error) {
    els.codeStatus.textContent = "代码解读失败";
    els.codeOutput.innerHTML = `<div class="error-state">${escapeHtml(error.message)}</div>`;
  } finally {
    els.codeButton.disabled = false;
  }
}

function formatCodeOutput(payload) {
  const structure = payload.structure || {};
  const commands = (payload.run_commands || []).map((cmd) => `- \`${cmd}\``).join("\n");
  const mappings = (payload.paper_code_map || [])
    .map((item) => `- ${item.paper_concept} → \`${item.code_path}\`：${item.reason}`)
    .join("\n");
  return [
    payload.answer || "",
    "## 自动识别结果",
    `- 仓库路径：\`${payload.repo_path || "unknown"}\``,
    `- 训练入口：${(structure.train_entries || []).map((item) => `\`${item}\``).join(", ") || "未识别"}`,
    `- 配置文件：${(structure.configs || []).slice(0, 8).map((item) => `\`${item}\``).join(", ") || "未识别"}`,
    `- 核心文件候选：${(structure.core_files || []).slice(0, 8).map((item) => `\`${item}\``).join(", ") || "未识别"}`,
    "",
    "## 运行命令",
    commands || "- 未识别",
    "",
    mappings ? `## 论文-代码映射\n${mappings}` : "",
  ]
    .filter(Boolean)
    .join("\n\n");
}

async function runWriter(event) {
  event.preventDefault();
  els.writerButton.disabled = true;
  els.writerStatus.textContent = "Paper Writing Agent 正在生成...";
  els.writerOutput.classList.remove("empty-state");
  els.writerOutput.innerHTML = "生成中...";

  try {
    const payload = await postJson("/api/agents/paper-writer", {
      session_id: state.sessionId,
      mode: els.writerModeSelect.value,
      prompt: els.writerPromptInput.value.trim(),
      papers: state.libraryPapers,
      experiment_notes: els.experimentNotesInput.value.trim(),
      draft: els.draftInput.value.trim(),
    });
    els.writerOutput.innerHTML = renderMarkdown(payload.answer || "");
    els.writerStatus.textContent = "写作输出已生成";
  } catch (error) {
    els.writerStatus.textContent = "写作失败";
    els.writerOutput.innerHTML = `<div class="error-state">${escapeHtml(error.message)}</div>`;
  } finally {
    els.writerButton.disabled = false;
  }
}

els.tabs.forEach((tab) => tab.addEventListener("click", () => setAgentPanel(tab.dataset.agent)));

els.builderForm.addEventListener("submit", runBuilder);
els.builderChatForm.addEventListener("submit", streamBuilderChat);
els.readerForm.addEventListener("submit", runReader);
els.codeForm.addEventListener("submit", runCodeInterpreter);
els.writerForm.addEventListener("submit", runWriter);

els.profileInput.addEventListener("input", () => {
  clearTimeout(state.profileTimer);
  state.profileTimer = setTimeout(() => saveProfile().catch(() => {}), 600);
});

els.newSessionButton.addEventListener("click", async () => {
  els.newSessionButton.disabled = true;
  try {
    await createNewSession();
  } catch (error) {
    els.libraryStatus.textContent = `创建失败：${error.message}`;
  } finally {
    els.newSessionButton.disabled = false;
  }
});

els.refreshSessionsButton.addEventListener("click", () => loadSessions().catch((error) => {
  els.sessionList.innerHTML = `<div class="error-state compact">${escapeHtml(error.message)}</div>`;
}));

els.sessionList.addEventListener("click", async (event) => {
  const item = event.target.closest(".session-item");
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (!item || !action) return;
  try {
    if (action === "open") await openSession(item.dataset.sessionId);
    if (action === "rename") await renameSession(item.dataset.sessionId);
    if (action === "delete") await deleteSession(item.dataset.sessionId);
  } catch (error) {
    els.libraryStatus.textContent = `操作失败：${error.message}`;
  }
});

els.candidateList.addEventListener("click", async (event) => {
  const actionEl = event.target.closest("[data-action]");
  if (!actionEl) return;
  const paper = state.candidates[Number(actionEl.dataset.index)];
  if (!paper) return;
  if (actionEl.dataset.action === "read") {
    setAgentPanel("reader");
    els.readerPaperSelect.value = paperKey(paper);
    els.readerPromptInput.value = `请结合原文内容精读《${paper.title || "这篇论文"}》，总结问题定义、核心方法、实验设置、贡献和局限。`;
    return;
  }
  if (actionEl.dataset.action === "add") {
    actionEl.disabled = true;
    try {
      await addPaperObjectToLibrary(paper);
    } catch (error) {
      els.builderStatus.textContent = `加入论文库失败：${error.message}`;
      actionEl.disabled = false;
    }
  }
});

els.builderChatMessages.addEventListener("click", async (event) => {
  const actionEl = event.target.closest("[data-action]");
  if (!actionEl) return;
  const container = actionEl.closest(".builder-suggestions");
  const papers = state.builderSuggestionBuckets[container?.dataset.suggestionId || ""] || [];
  const paper = papers[Number(actionEl.dataset.index)];
  if (!paper) return;

  if (actionEl.dataset.action === "chat-read") {
    setAgentPanel("reader");
    els.readerPaperSelect.value = paperKey(paper);
    els.readerPromptInput.value = `请结合原文内容精读《${paper.title || "这篇论文"}》，总结问题定义、核心方法、实验设置、贡献和局限。`;
    return;
  }

  if (actionEl.dataset.action === "chat-add") {
    actionEl.disabled = true;
    try {
      await addPaperObjectToLibrary(paper);
    } catch (error) {
      els.builderStatus.textContent = `加入论文库失败：${error.message}`;
      actionEl.disabled = false;
    }
  }
});

loadSession().catch((error) => {
  els.libraryStatus.textContent = `加载失败：${error.message}`;
  renderCandidateList();
  refreshPaperSelects();
});
