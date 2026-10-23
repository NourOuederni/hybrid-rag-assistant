/* Lumen: frontend (vanilla JS, no build step). Talks to the FastAPI backend under /api. */
(() => {
  "use strict";

  /* ------------------------------------------------------------ helpers */
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const P = {
    home: '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h5v-6h4v6h5V10"/>',
    library: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    graph: '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="7" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="M8.3 7l7.3 0M7.2 8.3l3.6 7.4M16.8 9.3l-3.6 6.4"/>',
    chart: '<path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/>',
    gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    clip: '<path d="M21 11l-9 9a5 5 0 0 1-7-7l9-9a3.5 3.5 0 0 1 5 5l-9 9a2 2 0 0 1-3-3l8-8"/>',
    sliders: '<path d="M4 6h8M18 6h2M4 12h2M12 12h8M4 18h10M20 18h0"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
    options: '<path d="M4 7h16M4 12h16M4 17h10"/>',
    up: '<path d="M12 19V5M5 12l7-7 7 7"/>',
    stop: '<rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor"/>',
    trash: '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/>',
    file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M21 16l-5-5-8 8"/>',
    spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    x: '<path d="M6 6l12 12M18 6L6 18"/>',
    pencil: '<path d="M4 20l4-1 11-11a2.1 2.1 0 0 0-3-3L5 16z"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    route: '<circle cx="6" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 6h6a3 3 0 0 1 0 6h-4a3 3 0 0 0 0 6h6"/>',
  };
  const icon = (n) => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${P[n] || ""}</svg>`;

  let starN = 0;
  const star = (cls = "") => {
    const id = "g" + ++starN;
    return `<svg class="${cls}" viewBox="0 0 100 100" aria-hidden="true"><defs>
      <linearGradient id="${id}a" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#b9a6dc"/><stop offset="1" stop-color="#f2a98c"/></linearGradient>
      <linearGradient id="${id}b" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f6c9b6"/><stop offset="1" stop-color="#cdbfe6"/></linearGradient></defs>
      <path d="M50 2C53 30 70 47 98 50 70 53 53 70 50 98 47 70 30 53 2 50 30 47 47 30 50 2Z" fill="url(#${id}a)" opacity=".95"/>
      <path transform="rotate(45 50 50) scale(.78) translate(14 14)" d="M50 2C53 30 70 47 98 50 70 53 53 70 50 98 47 70 30 53 2 50 30 47 47 30 50 2Z" fill="url(#${id}b)" opacity=".85"/></svg>`;
  };

  const timeAgo = (iso) => {
    const s = Math.max(1, (Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return Math.floor(s / 60) + "m ago";
    if (s < 86400) return Math.floor(s / 3600) + "h ago";
    return Math.floor(s / 86400) + "d ago";
  };
  const bytes = (n) => (n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB");

  function toast(msg, err = false) {
    const t = document.createElement("div");
    t.className = "toast" + (err ? " err" : "");
    t.textContent = msg;
    $("#toasts").append(t);
    setTimeout(() => t.remove(), err ? 6000 : 3200);
  }

  async function request(method, url, body) {
    const opt = { method, headers: {} };
    if (body !== undefined) {
      opt.headers["Content-Type"] = "application/json";
      opt.body = JSON.stringify(body);
    }
    const r = await fetch(url, opt);
    if (!r.ok) {
      let m = r.statusText;
      try { m = (await r.json()).error?.message || m; } catch { /* ignore */ }
      throw new Error(m);
    }
    return r.status === 204 ? null : r.json();
  }
  const api = { get: (u) => request("GET", u), post: (u, b) => request("POST", u, b ?? {}), patch: (u, b) => request("PATCH", u, b), del: (u) => request("DELETE", u) };

  /* -------------------------------------------------------------- state */
  const prefs = Object.assign({ web: true, mode: "auto", route: true }, JSON.parse(localStorage.getItem("lumen.prefs") || "{}"));
  const savePrefs = () => localStorage.setItem("lumen.prefs", JSON.stringify(prefs));
  const S = { view: "home", convs: [], cid: null, messages: [], docs: [], cfg: {}, search: "", streaming: false, abort: null, menu: null };

  /* ------------------------------------------------------ markdown-lite */
  function inline(s) {
    return s.replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
  }
  function md(src, citeFn) {
    const out = [];
    let para = [], list = null;
    const flushP = () => { if (para.length) { out.push("<p>" + para.join(" ") + "</p>"); para = []; } };
    const flushL = () => { if (list) { out.push(`<${list.t}>` + list.items.map((i) => "<li>" + i + "</li>").join("") + `</${list.t}>`); list = null; } };
    for (const raw of esc(src).split("\n")) {
      const ul = /^\s*[-*•]\s+(.*)/.exec(raw), ol = /^\s*\d+[.)]\s+(.*)/.exec(raw);
      if (ul || ol) {
        flushP();
        const t = ul ? "ul" : "ol";
        if (!list || list.t !== t) { flushL(); list = { t, items: [] }; }
        list.items.push(inline((ul || ol)[1]));
      } else if (!raw.trim()) { flushP(); flushL(); }
      else { flushL(); para.push(inline(raw.trim())); }
    }
    flushP(); flushL();
    return out.join("").replace(/\[(\d+)\]/g, (_, n) => citeFn(n));
  }

  /* ------------------------------------------------------ source helpers */
  const srcHref = (s) => (s.source_type === "web" ? s.url : s.doc_id ? `/api/documents/${s.doc_id}/file#page=${s.page || 1}` : null);
  function srcLabel(s) {
    if (s.source_type === "web") return s.title || s.url;
    if (s.source_type === "image") return `${s.figure_label || "Figure"}, ${s.file_name} p.${s.page}`;
    if (s.source_type === "graph") return "Graph: " + (s.entities || []).slice(0, 3).join(", ");
    return `${s.file_name}, p.${s.page}`;
  }
  const tagFor = (s) => `<span class="tag ${s.source_type}">${{ local: "Local", web: "Web", graph: "Graph", image: "Figure" }[s.source_type]}</span>`;

  /* --------------------------------------------------------- sidebar UI */
  function renderSidebar() {
    const ready = S.docs.filter((d) => d.status === "ready").length;
    const busy = S.docs.filter((d) => ["uploaded", "processing"].includes(d.status)).length;
    const nav = [["home", "Home", "home"], ["library", "Library", "library"], ["graph", "Knowledge graph", "graph"], ["eval", "Evaluation", "chart"], ["settings", "Settings", "gear"]];
    const webOk = S.cfg.web_search_available;
    $("#sidebar").innerHTML = `
      <div class="brand">${star()}<span>LUMEN</span></div>
      <nav class="nav">${nav.map(([v, l, i]) => `<button data-view="${v}" ${S.view === v ? 'aria-current="page"' : ""}>${icon(i)}${l}${v === "library" && S.docs.length ? `<span class="badge">${S.docs.length}</span>` : ""}</button>`).join("")}</nav>
      <div class="group-title">AI tools</div>
      <div class="tool-row" title="${webOk ? "" : "Add a TAVILY_API_KEY in .env to enable web search"}">${icon("globe")}<span class="grow">Web search</span>
        <button class="switch" role="switch" aria-label="Web search" aria-checked="${prefs.web && webOk}" id="swWeb" ${webOk ? "" : "disabled"}></button></div>
      <div class="tool-row">${icon("route")}<span class="grow">Retrieval</span>
        <select id="selMode" aria-label="Retrieval mode">${[["auto", "Auto"], ["rag", "RAG"], ["graphrag", "GraphRAG"]].map(([v, l]) => `<option value="${v}" ${prefs.mode === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>
      <div class="status-card">
        <div class="t">Your library</div>
        <div class="s">${ready} ready${busy ? `, ${busy} processing` : ""}${S.docs.length === 0 ? "No documents yet" : ""}</div>
        <button class="btn-light" id="btnUpload">${icon("plus")}Upload files</button>
      </div>`;
    $$("[data-view]", $("#sidebar")).forEach((b) => b.onclick = () => setView(b.dataset.view));
    $("#swWeb").onclick = () => { prefs.web = !prefs.web; savePrefs(); renderSidebar(); };
    $("#selMode").onchange = (e) => { prefs.mode = e.target.value; savePrefs(); };
    $("#btnUpload").onclick = () => $("#filePicker").click();
  }

  /* ---------------------------------------------------------- history UI */
  function renderHistory() {
    const el = $("#history");
    el.innerHTML = `
      <header><span>Chat history</span><button class="icon-btn only-narrow" id="hClose" aria-label="Close history" title="Close">${icon("x")}</button></header>
      <label class="search">${icon("search")}<input id="hSearch" type="search" placeholder="Search chats" value="${esc(S.search)}" aria-label="Search chats"></label>
      <div class="convs" id="convs"></div>
      <button class="btn-dark" id="newChat">${icon("plus")}Create new chat</button>`;
    paintConvs();
    $("#hSearch").oninput = (e) => { S.search = e.target.value; clearTimeout(renderHistory.t); renderHistory.t = setTimeout(async () => { await loadConvs(); paintConvs(); }, 220); };
    $("#newChat").onclick = newChat;
    $("#hClose").onclick = () => $("#shell").classList.remove("show-history");
  }
  function paintConvs() {
    const box = $("#convs");
    if (!box) return;
    if (!S.convs.length) { box.innerHTML = `<div class="empty-note">${S.search ? "No chats match this search." : "No chats yet. Ask your first question."}</div>`; return; }
    box.innerHTML = S.convs.map((c) => `
      <div class="conv" role="button" tabindex="0" data-id="${c.id}" ${c.id === S.cid ? 'aria-current="true"' : ""}>
        <span class="dot"></span><div class="t">${esc(c.title)}</div>
        ${c.preview ? `<div class="p">${esc(c.preview)}</div>` : ""}<div class="time">${timeAgo(c.updated_at)}</div>
        <div class="acts"><span data-act="rename" title="Rename" role="button" aria-label="Rename chat">${icon("pencil")}</span><span data-act="delete" title="Delete" role="button" aria-label="Delete chat">${icon("trash")}</span></div>
      </div>`).join("");
    $$(".conv", box).forEach((n) => {
      const id = n.dataset.id;
      n.onclick = (e) => {
        const act = e.target.closest("[data-act]")?.dataset.act;
        if (act === "rename") return renameConv(id);
        if (act === "delete") return deleteConv(id);
        openConv(id);
      };
      n.onkeydown = (e) => { if (e.key === "Enter" && e.target === n) openConv(id); };
    });
  }
  async function loadConvs() { try { S.convs = await api.get("/api/conversations" + (S.search ? "?q=" + encodeURIComponent(S.search) : "")); } catch (e) { toast(e.message, true); } }
  async function openConv(id) {
    if (S.streaming) return toast("Stop the current answer before switching chats.");
    try {
      const c = await api.get("/api/conversations/" + id);
      S.cid = id;
      S.messages = c.messages.map((m) => ({ ...m, route: (m.route || []).map((r) => (typeof r === "string" ? { node: r, detail: "" } : r)) }));
      $("#shell").classList.remove("show-history");
      if (S.view !== "home") setView("home"); else { paintConvs(); renderStage(true); }
    } catch (e) { toast(e.message, true); }
  }
  async function renameConv(id) {
    const cur = S.convs.find((c) => c.id === id);
    const t = prompt("Rename chat", cur?.title || "");
    if (t === null) return;
    try { await api.patch("/api/conversations/" + id, { title: t }); await loadConvs(); paintConvs(); } catch (e) { toast(e.message, true); }
  }
  async function deleteConv(id) {
    if (!confirm("Delete this chat and its messages?")) return;
    try {
      await api.del("/api/conversations/" + id);
      if (id === S.cid) { S.cid = null; S.messages = []; renderStage(true); }
      await loadConvs(); paintConvs(); toast("Chat deleted");
    } catch (e) { toast(e.message, true); }
  }
  function newChat() {
    if (S.streaming) return toast("Stop the current answer first.");
    S.cid = null; S.messages = [];
    $("#shell").classList.remove("show-history");
    if (S.view !== "home") setView("home"); else { paintConvs(); renderStage(true); $("#ta")?.focus(); }
  }

  /* ----------------------------------------------------------- chat view */
  let chatMounted = false;
  function mountChat() {
    const main = $("#main");
    main.innerHTML = `
      <div class="mobile-bar"><button class="icon-btn" id="mNav" aria-label="Open menu">${icon("menu")}</button><b>LUMEN</b><button class="icon-btn" id="mHist" aria-label="Open chat history">${icon("clock")}</button></div>
      <button class="icon-btn only-narrow" id="hOpen" aria-label="Open chat history" title="Chat history" style="position:absolute;top:14px;right:14px;z-index:2">${icon("clock")}</button>
      <div class="view" id="stage"></div>
      <div class="composer-wrap">
        <div class="composer">
          <textarea id="ta" rows="1" placeholder="Ask a question about your documents or send a command" aria-label="Message"></textarea>
          <div class="row">
            <button class="pill" id="bAttach">${icon("clip")}Attach</button>
            <button class="pill" id="bSettings" aria-haspopup="true">${icon("sliders")}Settings</button>
            <button class="pill" id="bOptions" aria-haspopup="true">${icon("options")}Options</button>
            <button class="send" id="bSend" aria-label="Send">${icon("up")}</button>
          </div>
        </div>
      </div>`;
    const ta = $("#ta");
    ta.oninput = () => { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 160) + "px"; };
    ta.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); } };
    $("#bSend").onclick = () => (S.streaming ? S.abort?.abort() : submit());
    $("#bAttach").onclick = () => $("#filePicker").click();
    $("#bSettings").onclick = (e) => toggleMenu(e, "settings");
    $("#bOptions").onclick = (e) => toggleMenu(e, "options");
    $("#mNav").onclick = () => $("#shell").classList.toggle("show-nav");
    $("#mHist").onclick = () => $("#shell").classList.toggle("show-history");
    $("#hOpen").onclick = () => $("#shell").classList.toggle("show-history");
    chatMounted = true;
  }
  function toggleMenu(e, kind) {
    e.stopPropagation();
    const had = $(".menu");
    had?.remove();
    if (had && S.menu === kind) { S.menu = null; return; }
    S.menu = kind;
    const m = document.createElement("div");
    m.className = "menu";
    m.onclick = (ev) => ev.stopPropagation();
    if (kind === "settings") {
      const webOk = S.cfg.web_search_available;
      m.innerHTML = `<h4>Retrieval mode</h4><div class="seg">${[["auto", "Auto"], ["rag", "RAG"], ["graphrag", "GraphRAG"]].map(([v, l]) => `<button data-mode="${v}" aria-pressed="${prefs.mode === v}">${l}</button>`).join("")}</div>
        <p class="hint">Auto lets the agent choose. RAG searches passages only; GraphRAG follows entity links.</p>
        <button class="opt" id="mWeb" ${webOk ? "" : "disabled"}><span>Web fallback</span><span class="switch" aria-checked="${prefs.web && webOk}"></span></button>
        ${webOk ? "" : '<p class="hint">Add TAVILY_API_KEY in .env to enable.</p>'}`;
    } else {
      m.innerHTML = `<h4>Display</h4><button class="opt" id="mRoute"><span>Show how I answered</span><span class="switch" aria-checked="${prefs.route}"></span></button>`;
    }
    $(".composer .row").append(m);
    $$("[data-mode]", m).forEach((b) => b.onclick = () => { prefs.mode = b.dataset.mode; savePrefs(); renderSidebar(); $$("[data-mode]", m).forEach((x) => x.setAttribute("aria-pressed", x === b)); });
    $("#mWeb", m)?.addEventListener("click", () => { prefs.web = !prefs.web; savePrefs(); renderSidebar(); $(".switch", $("#mWeb")).setAttribute("aria-checked", prefs.web); });
    $("#mRoute", m)?.addEventListener("click", () => { prefs.route = !prefs.route; savePrefs(); $(".switch", $("#mRoute")).setAttribute("aria-checked", prefs.route); renderStage(); });
  }
  document.addEventListener("click", () => { $(".menu")?.remove(); S.menu = null; });

  function renderStage(scroll) {
    const stage = $("#stage");
    if (!stage) return;
    if (!S.messages.length) {
      const first = S.docs.find((d) => d.status === "ready");
      stage.innerHTML = `<div class="home">${star("star")}
        <h1>Ask anything about your documents</h1>
        <p>${S.docs.length ? "Answers come with citations from your library, or from the web when needed." : "Upload a PDF to begin. Your library stays here between sessions."}</p>
        <div class="cards">
          <button class="action" data-fill="${esc(first ? "Summarise the main points of " + first.name : "Summarise the main points of my documents")}"><span class="chip">${icon("spark")}</span><b>Summarise a document</b><span>Get the key points with page citations</span></button>
          <button class="action" data-fill="Show me the figure that explains "><span class="chip">${icon("image")}</span><b>Find a figure</b><span>Search diagrams and charts by description</span></button>
          <button class="action" data-fill="Which methods are related to each other, and what do they have in common?"><span class="chip">${icon("graph")}</span><b>Ask across documents</b><span>Connect ideas with the knowledge graph</span></button>
        </div></div>`;
      $$(".action", stage).forEach((b) => b.onclick = () => { const ta = $("#ta"); ta.value = b.dataset.fill; ta.oninput(); ta.focus(); });
      return;
    }
    stage.innerHTML = `<div class="thread" id="thread"><div class="thread-inner" id="tin"></div></div>`;
    stage.style.overflow = "hidden";
    $("#tin").innerHTML = S.messages.map((m, i) => (m.role === "user" ? `<div class="msg user">${esc(m.text)}</div>` : `<div class="msg assistant" data-i="${i}">${assistantHtml(m)}</div>`)).join("");
    bindMessage($("#tin"));
    if (scroll !== false) $("#thread").scrollTop = $("#thread").scrollHeight;
  }

  function assistantHtml(m) {
    const cmap = {};
    (m.citations || []).forEach((c) => { cmap[c.marker.replace(/\D/g, "")] = m.sources.find((s) => s.id === c.source_id); });
    const body = m.text
      ? md(m.text, (n) => (cmap[n] ? `<button class="cite" data-n="${n}" aria-label="Source ${n}">${n}</button>` : `<span class="cite">${n}</span>`))
      : (m.streaming ? "" : "");
    const waiting = m.streaming && !m.text ? `<span class="hint">Searching your documents...</span>` : "";
    const srcs = (m.sources || []).length ? `<div class="sources">${m.citations.map((c) => { const s = m.sources.find((x) => x.id === c.source_id); if (!s) return ""; const h = srcHref(s); return `<${h ? `a href="${esc(h)}" target="_blank" rel="noopener"` : "span"} class="src"><span class="n">${c.marker.replace(/\D/g, "")}</span>${tagFor(s)}<span class="t">${esc(srcLabel(s))}</span></${h ? "a" : "span"}>`; }).join("")}</div>` : "";
    const figs = (m.images || []).length ? `<div class="figs">${m.images.map((im) => `<figure><img src="/api/images/${esc(im.image_path)}" alt="${esc(im.figure_label)} from ${esc(im.file_name)}" data-full="/api/images/${esc(im.image_path)}"><figcaption>${esc(im.figure_label)}, ${esc(im.file_name)} p.${im.page}</figcaption></figure>`).join("")}</div>` : "";
    const route = prefs.route && (m.route || []).length ? `<details class="route"><summary>${icon("route")}How I answered${m.used_web ? ' <span class="tag web">Web used</span>' : ""}</summary><ol>${m.route.map((r) => `<li><b>${esc(r.node.replace(/_/g, " "))}</b>${r.detail ? ": " + esc(r.detail) : ""}</li>`).join("")}</ol></details>` : "";
    const err = m.error ? `<p class="err">${esc(m.error)}</p>` : "";
    return `<div class="body ${m.streaming && m.text ? "cursor" : ""}">${body}${waiting}</div>${err}${figs}${srcs}${route}`;
  }
  function bindMessage(root) {
    $$(".cite[data-n]", root).forEach((b) => {
      const idx = +b.closest(".msg").dataset.i;
      const show = () => showCite(b, S.messages[idx], b.dataset.n);
      b.onmouseenter = show; b.onfocus = show; b.onmouseleave = hidePop; b.onblur = hidePop;
      b.onclick = (e) => { e.stopPropagation(); const s = srcFor(S.messages[idx], b.dataset.n); const h = s && srcHref(s); if (h) window.open(h, "_blank", "noopener"); };
    });
    $$(".figs img", root).forEach((im) => im.onclick = () => { const lb = $("#lightbox"); lb.innerHTML = `<img src="${im.dataset.full}" alt="${esc(im.alt)}">`; lb.hidden = false; });
  }
  const srcFor = (m, n) => { const c = (m.citations || []).find((x) => x.marker === `[${n}]`); return c && m.sources.find((s) => s.id === c.source_id); };
  function showCite(el, m, n) {
    const s = srcFor(m, n);
    if (!s) return;
    const pop = $("#popover");
    pop.innerHTML = `<b>${tagFor(s)} ${esc(srcLabel(s))}</b><p>${esc((s.snippet || "").slice(0, 260))}${(s.snippet || "").length > 260 ? "..." : ""}</p>${srcHref(s) ? `<p><small>Click to open the source</small></p>` : ""}`;
    pop.hidden = false;
    const r = el.getBoundingClientRect();
    pop.style.left = Math.min(r.left, innerWidth - 340) + "px";
    pop.style.top = Math.max(8, r.top - pop.offsetHeight - 8) + "px";
    if (r.top - pop.offsetHeight - 8 < 8) pop.style.top = r.bottom + 8 + "px";
  }
  const hidePop = () => { $("#popover").hidden = true; };
  $("#lightbox").onclick = () => { $("#lightbox").hidden = true; };
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { $("#lightbox").hidden = true; hidePop(); $(".menu")?.remove(); } });

  function setSendIcon() {
    const b = $("#bSend");
    if (!b) return;
    b.innerHTML = icon(S.streaming ? "stop" : "up");
    b.setAttribute("aria-label", S.streaming ? "Stop generating" : "Send");
  }

  async function submit() {
    const ta = $("#ta");
    const q = ta.value.trim();
    if (!q || S.streaming) return;
    ta.value = ""; ta.style.height = "auto";
    try {
      if (!S.cid) S.cid = (await api.post("/api/conversations")).id;
    } catch (e) { return toast(e.message, true); }
    const am = { role: "assistant", text: "", route: [], images: [], sources: [], citations: [], streaming: true, used_web: false };
    S.messages.push({ role: "user", text: q }, am);
    renderStage();
    S.streaming = true; S.abort = new AbortController(); setSendIcon();
    const el = () => $(`.msg.assistant[data-i="${S.messages.length - 1}"]`);
    const paint = () => { const n = el(); if (!n) return; const th = $("#thread"); const stick = th.scrollHeight - th.scrollTop - th.clientHeight < 120; n.innerHTML = assistantHtml(am); bindMessage(n); if (stick) th.scrollTop = th.scrollHeight; };
    const handlers = {
      token: (d) => { am.text = d.reset ? d.text : am.text + d.text; paint(); },
      route: (d) => { am.route.push(d); paint(); },
      image: (d) => { am.images.push(d.source); paint(); },
      final: (d) => { const route = am.route; Object.assign(am, d.answer); am.route = route; },
      error: (d) => { am.error = d.message; },
    };
    try {
      await streamChat(S.cid, { question: q, web_search_enabled: prefs.web && !!S.cfg.web_search_available, mode: prefs.mode }, handlers, S.abort.signal);
    } catch (e) {
      if (e.name === "AbortError") { am.text = (am.text.trim() || "") + (am.text ? "\n\n" : "") + "*(stopped)*"; } else am.error = e.message;
    } finally {
      am.streaming = false; S.streaming = false; setSendIcon(); paint();
      loadConvs().then(paintConvs);
    }
  }

  async function streamChat(cid, body, handlers, signal) {
    const res = await fetch(`/api/conversations/${cid}/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
    if (!res.ok) { let m = res.statusText; try { m = (await res.json()).error?.message || m; } catch { /* ignore */ } throw new Error(m); }
    const reader = res.body.getReader(), dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const frame = buf.slice(0, i); buf = buf.slice(i + 2);
        let ev = "message", data = "";
        for (const line of frame.split("\n")) { if (line.startsWith("event:")) ev = line.slice(6).trim(); else if (line.startsWith("data:")) data += line.slice(5).trim(); }
        if (data && handlers[ev]) handlers[ev](JSON.parse(data));
      }
    }
  }

  /* ---------------------------------------------------------- documents */
  async function loadDocs() { try { S.docs = await api.get("/api/documents"); } catch (e) { toast(e.message, true); } }
  async function uploadFiles(files) {
    for (const f of files) {
      if (!f.name.toLowerCase().endsWith(".pdf")) { toast(`${f.name} is not a PDF.`, true); continue; }
      const fd = new FormData(); fd.append("file", f);
      try {
        const r = await fetch("/api/documents", { method: "POST", body: fd });
        if (!r.ok) throw new Error((await r.json()).error?.message || r.statusText);
        toast(`${f.name} uploaded. Indexing started.`);
      } catch (e) { toast(e.message, true); }
    }
    await loadDocs(); renderSidebar();
    if (S.view === "library") renderLibrary(); else if (!S.messages.length) renderStage();
    pollDocs();
  }
  $("#filePicker").onchange = (e) => { uploadFiles([...e.target.files]); e.target.value = ""; };
  let pollT = null;
  function pollDocs() {
    clearTimeout(pollT);
    if (!S.docs.some((d) => ["uploaded", "processing"].includes(d.status))) return;
    pollT = setTimeout(async () => { await loadDocs(); renderSidebar(); if (S.view === "library") paintDocs(); pollDocs(); }, 1800);
  }

  function renderLibrary() {
    $("#main").innerHTML = `<div class="mobile-bar"><button class="icon-btn" id="mNav" aria-label="Open menu">${icon("menu")}</button><b>Library</b><span></span></div>
      <div class="view"><div class="page"><h1>Library</h1><p class="lede">Documents you add stay here and are searched in every chat.</p>
      <div class="drop" id="drop"><b>Drop PDF files here</b><span>Text, tables and figures are indexed. Up to ${S.cfg.max_upload_mb || 50} MB each.</span><br><button class="btn-dark" id="dropBtn">${icon("plus")}Choose files</button></div>
      <div id="docs"></div></div></div>`;
    $("#mNav").onclick = () => $("#shell").classList.toggle("show-nav");
    const drop = $("#drop");
    ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
    drop.addEventListener("drop", (e) => uploadFiles([...e.dataTransfer.files]));
    $("#dropBtn").onclick = () => $("#filePicker").click();
    paintDocs();
  }
  function paintDocs() {
    const box = $("#docs");
    if (!box) return;
    if (!S.docs.length) { box.innerHTML = `<div class="empty"><b>Your library is empty</b>Drop a PDF above to start asking questions about it.</div>`; return; }
    box.innerHTML = `<div class="docs">${S.docs.map((d) => `
      <div class="doc" data-id="${d.id}"><div class="top"><span class="ic">${icon("file")}</span><div><div class="name">${esc(d.name)}</div><div class="meta">${bytes(d.size)} · added ${timeAgo(d.uploaded_at)}</div></div></div>
        ${d.status === "ready" ? `<div class="facts"><span>${d.pages} page${d.pages === 1 ? "" : "s"}</span><span>${d.chunks} passages</span><span>${d.images} figure${d.images === 1 ? "" : "s"}</span><span>${d.entities} entities</span></div>` : ""}
        ${d.errors?.length ? `<div class="warn">${esc(d.errors[0])}</div>` : ""}
        <div class="foot"><span class="status ${d.status}">${["uploaded", "processing"].includes(d.status) ? '<i class="spin"></i>' : ""}${{ uploaded: "Queued", processing: "Indexing", ready: "Ready", failed: "Failed" }[d.status]}</span>
          <span class="acts"><a class="icon-btn" href="/api/documents/${d.id}/file" target="_blank" rel="noopener" aria-label="Open ${esc(d.name)}" title="Open">${icon("ext")}</a><button class="icon-btn" data-del="${d.id}" aria-label="Delete ${esc(d.name)}" title="Delete">${icon("trash")}</button></span></div></div>`).join("")}</div>`;
    $$("[data-del]", box).forEach((b) => b.onclick = async () => {
      const d = S.docs.find((x) => x.id === b.dataset.del);
      if (!confirm(`Delete "${d.name}"? It will be removed from search and the knowledge graph.`)) return;
      try { await api.del("/api/documents/" + d.id); toast("Document deleted"); await loadDocs(); renderSidebar(); paintDocs(); } catch (e) { toast(e.message, true); }
    });
  }

  /* -------------------------------------------------------------- graph */
  const TYPE_COLORS = { Concept: "#c9785c", Method: "#7a55c7", Model: "#3b6fd4", Dataset: "#2f8f5b", Metric: "#b7791f", Person: "#c0568a", Organization: "#5b8a9a", Tool: "#888" };
  async function renderGraph() {
    $("#main").innerHTML = `<div class="mobile-bar"><button class="icon-btn" id="mNav" aria-label="Open menu">${icon("menu")}</button><b>Knowledge graph</b><span></span></div>
      <div class="view"><div class="page"><h1>Knowledge graph</h1><p class="lede">Entities and relations extracted from your documents. GraphRAG follows these links to answer multi-hop questions.</p>
      <div id="gbox"><div class="empty">Loading...</div></div></div></div>`;
    $("#mNav").onclick = () => $("#shell").classList.toggle("show-nav");
    let g;
    try { g = await api.get("/api/graph"); } catch (e) { $("#gbox").innerHTML = `<div class="empty err">${esc(e.message)}</div>`; return; }
    if (!g.nodes.length) { $("#gbox").innerHTML = `<div class="empty"><b>The graph is empty</b>Upload a document and make sure GRAPH_EXTRACTION is on in .env.</div>`; return; }
    const nodes = [...g.nodes].sort((a, b) => b.degree - a.degree).slice(0, 140);
    const ids = new Set(nodes.map((n) => n.id));
    const links = g.links.filter((l) => ids.has(l.source) && ids.has(l.target));
    const types = [...new Set(nodes.map((n) => n.type))];
    $("#gbox").innerHTML = `<div class="legend">${types.map((t) => `<span><i style="background:${TYPE_COLORS[t] || "#999"}"></i>${esc(t)}</span>`).join("")}<span>${g.nodes.length} entities, ${g.links.length} relations</span></div><canvas class="graph" id="cv" role="img" aria-label="Knowledge graph visualisation"></canvas>`;
    drawGraph($("#cv"), nodes, links);
  }
  function drawGraph(cv, nodes, links) {
    const dpr = devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
    cv.width = W * dpr; cv.height = H * dpr;
    const ctx = cv.getContext("2d"); ctx.scale(dpr, dpr);
    const idx = new Map(nodes.map((n, i) => [n.id, i]));
    nodes.forEach((n, i) => { const a = (i / nodes.length) * 6.283; n.x = W / 2 + Math.cos(a) * 120 * Math.random(); n.y = H / 2 + Math.sin(a) * 120 * Math.random(); n.vx = n.vy = 0; });
    const L = links.map((l) => [idx.get(l.source), idx.get(l.target)]);
    for (let it = 0; it < 320; it++) {
      const cool = 1 - it / 320;
      for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
        let dx = nodes[i].x - nodes[j].x, dy = nodes[i].y - nodes[j].y, d2 = dx * dx + dy * dy + 0.01;
        const f = 1800 / d2, d = Math.sqrt(d2);
        dx = (dx / d) * f; dy = (dy / d) * f;
        nodes[i].vx += dx; nodes[i].vy += dy; nodes[j].vx -= dx; nodes[j].vy -= dy;
      }
      for (const [a, b] of L) {
        const dx = nodes[b].x - nodes[a].x, dy = nodes[b].y - nodes[a].y, d = Math.sqrt(dx * dx + dy * dy) + 0.01, f = (d - 70) * 0.02;
        nodes[a].vx += (dx / d) * f; nodes[a].vy += (dy / d) * f; nodes[b].vx -= (dx / d) * f; nodes[b].vy -= (dy / d) * f;
      }
      for (const n of nodes) {
        n.vx += (W / 2 - n.x) * 0.004; n.vy += (H / 2 - n.y) * 0.004;
        n.x = Math.min(W - 60, Math.max(60, n.x + Math.max(-12, Math.min(12, n.vx)) * cool)); n.y = Math.min(H - 20, Math.max(34, n.y + Math.max(-12, Math.min(12, n.vy)) * cool));
        n.vx *= 0.6; n.vy *= 0.6;
      }
    }
    const draw = (hover) => {
      ctx.clearRect(0, 0, W, H);
      ctx.strokeStyle = "rgba(20,20,20,.16)"; ctx.lineWidth = 1;
      for (const [a, b] of L) { ctx.beginPath(); ctx.moveTo(nodes[a].x, nodes[a].y); ctx.lineTo(nodes[b].x, nodes[b].y); ctx.stroke(); }
      ctx.font = "11px Inter, sans-serif"; ctx.textAlign = "center";
      nodes.forEach((n, i) => {
        const r = 4 + Math.min(8, n.degree);
        ctx.fillStyle = TYPE_COLORS[n.type] || "#999"; ctx.globalAlpha = hover === i ? 1 : 0.85;
        ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 6.283); ctx.fill(); ctx.globalAlpha = 1;
        if (nodes.length < 45 || n.degree >= 3 || hover === i) { ctx.fillStyle = "#141414"; ctx.fillText(n.label, n.x, n.y - r - 4); }
      });
    };
    draw(-1);
    cv.onmousemove = (e) => {
      const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
      let best = -1, bd = 14;
      nodes.forEach((n, i) => { const d = Math.hypot(n.x - x, n.y - y); if (d < bd) { bd = d; best = i; } });
      draw(best);
      const pop = $("#popover");
      if (best >= 0) { const n = nodes[best]; pop.innerHTML = `<b>${esc(n.label)}</b><p>${esc(n.type)} · ${n.degree} connection${n.degree === 1 ? "" : "s"}</p>`; pop.hidden = false; pop.style.left = e.clientX + 14 + "px"; pop.style.top = e.clientY + 14 + "px"; } else pop.hidden = true;
    };
    cv.onmouseleave = () => { hidePop(); draw(-1); };
  }

  /* --------------------------------------------------------- evaluation */
  async function renderEval() {
    $("#main").innerHTML = `<div class="mobile-bar"><button class="icon-btn" id="mNav" aria-label="Open menu">${icon("menu")}</button><b>Evaluation</b><span></span></div>
      <div class="view"><div class="page"><h1>Evaluation</h1><p class="lede">How RAG, GraphRAG and the hybrid agent score on your question set.</p><div id="ebox"><div class="empty">Loading...</div></div></div></div>`;
    $("#mNav").onclick = () => $("#shell").classList.toggle("show-nav");
    let d;
    try { d = await api.get("/api/eval"); } catch (e) { $("#ebox").innerHTML = `<div class="empty err">${esc(e.message)}</div>`; return; }
    if (!d.configs?.length) { $("#ebox").innerHTML = `<div class="empty"><b>No results yet</b>Run <code>python -m eval.run_eval</code> to benchmark your system.</div>`; return; }
    const pct = (v) => (v == null ? "n/a" : (v * 100).toFixed(0) + "%");
    $("#ebox").innerHTML = `${d.sample ? '<div class="banner">These are placeholder numbers that ship with the project so you can see the layout. Run <code>python -m eval.run_eval</code> to replace them with your real results.</div>' : `<p class="hint" style="margin:0 0 10px">Generated ${esc(d.generated_at || "")}${d.judge ? " · judge: " + esc(d.judge) : ""}</p>`}
      <table class="metrics"><thead><tr><th>Configuration</th>${d.metrics.map((m) => `<th>${esc(m.replace(/_/g, " "))}</th>`).join("")}</tr></thead><tbody>
      ${d.configs.map((c) => `<tr><td><b>${esc(c)}</b></td>${d.metrics.map((m) => { const v = d.scores?.[c]?.[m]; return `<td>${pct(v)}<div class="bar"><i style="width:${v == null ? 0 : v * 100}%"></i></div></td>`; }).join("")}</tr>`).join("")}</tbody></table>
      ${d.route_stats ? `<p class="hint" style="margin-top:12px">Route statistics: ${Object.entries(d.route_stats).map(([k, v]) => `${esc(k.replace(/_/g, " "))}: ${typeof v === "number" && v <= 1 ? pct(v) : esc(v)}`).join(" · ")}</p>` : ""}
      <div class="qlist">${(d.questions || []).map((q) => `<details><summary>${esc(q.question)} <span class="tag">${esc(q.category || "")}</span></summary>${d.configs.map((c) => { const r = q.results?.[c]; return r ? `<p><b>${esc(c)}</b>: ${esc((r.answer || "").slice(0, 400))}</p>` : ""; }).join("")}</details>`).join("")}</div>`;
  }

  /* ----------------------------------------------------------- settings */
  async function renderSettings() {
    $("#main").innerHTML = `<div class="mobile-bar"><button class="icon-btn" id="mNav" aria-label="Open menu">${icon("menu")}</button><b>Settings</b><span></span></div>
      <div class="view"><div class="page"><h1>Settings</h1><p class="lede">What the assistant is running on. Change these in the <code>.env</code> file, then restart the server.</p><div id="sbox"></div></div></div>`;
    $("#mNav").onclick = () => $("#shell").classList.toggle("show-nav");
    const [cfg, st] = await Promise.all([api.get("/api/config"), api.get("/api/stats")]).catch(() => [S.cfg, {}]);
    const row = (k, v) => `<div>${k}</div><div>${v}</div>`;
    const warn = (cfg.llm_active || cfg.llm) === "fake" ? ' <span class="tag image">Offline test model: set LLM_PROVIDER</span>' : "";
    $("#sbox").innerHTML = `<div class="kv">
      ${row("Language model", esc(cfg.llm_active || cfg.llm) + warn)}
      ${row("Embeddings", esc(cfg.embeddings_active || cfg.embeddings) + ((cfg.embeddings_active === "hash") ? ' <span class="tag image">Offline fallback: install requirements-ml.txt</span>' : ""))}
      ${row("Image search", esc(cfg.image_search || "n/a") + (cfg.image_search === "caption" ? ' <span class="tag image">Caption search: install requirements-ml.txt for CLIP</span>' : ""))}
      ${row("Web search", cfg.web_search_available ? "Available" : "Not configured")}
      ${row("Mock core", cfg.mock_core ? "On (no AI)" : "Off")}
      ${row("Documents", `${st.documents ?? 0} (${st.ready ?? 0} ready)`)}
      ${row("Passages indexed", st.chunks ?? 0)}
      ${row("Graph", `${st.graph?.nodes ?? 0} entities, ${st.graph?.edges ?? 0} relations`)}</div>`;
  }

  /* ------------------------------------------------------------ routing */
  function setView(v) {
    S.view = v;
    $("#shell").classList.remove("show-nav");
    $("#shell").classList.toggle("no-history", v !== "home");
    renderSidebar();
    if (v === "home") { chatMounted = false; mountChat(); renderStage(true); renderHistory(); setSendIcon(); }
    else if (v === "library") renderLibrary();
    else if (v === "graph") renderGraph();
    else if (v === "eval") renderEval();
    else if (v === "settings") renderSettings();
  }

  /* --------------------------------------------------------------- boot */
  (async function boot() {
    try { S.cfg = await api.get("/api/config"); } catch { toast("Cannot reach the server. Is it running?", true); }
    await Promise.all([loadDocs(), loadConvs()]);
    setView("home");
    pollDocs();
  })();
})();
