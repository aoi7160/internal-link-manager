/* ─────────────────────────────────────────────
   Internal Link Manager – Frontend
───────────────────────────────────────────── */

const API = "";

let articles = [];
let links    = [];
let clusters = [];
let linkSuggestions = [];
let graphData = null;
let network  = null;
let sortState = { col: "main_kw", dir: 1 };

// ─── Init ────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await checkSettings();
  await loadAll();

  document.getElementById("articleSearch").addEventListener("input", renderArticlesTable);
  document.getElementById("linkSearch").addEventListener("input", renderLinksTable);
  document.getElementById("clusterSearch").addEventListener("input", renderClustersTable);
  document.getElementById("showUnconfirmed").addEventListener("change", renderClustersTable);

  document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tab => {
    tab.addEventListener("shown.bs.tab", e => {
      const target = e.target.getAttribute("href");
      if (target === "#tabGraph") renderGraph();
    });
  });

  // Sort headers
  document.querySelectorAll(".sortable").forEach(th => {
    th.addEventListener("click", () => {
      const col = th.dataset.col;
      if (sortState.col === col) sortState.dir *= -1;
      else { sortState.col = col; sortState.dir = 1; }
      renderArticlesTable();
    });
  });
});

async function loadAll() {
  [articles, links, clusters, linkSuggestions] = await Promise.all([
    fetchJSON("/api/articles"),
    fetchJSON("/api/links"),
    fetchJSON("/api/clusters"),
    fetchJSON("/api/link-suggestions"),
  ]);
  renderArticlesTable();
  renderLinksTable();
  renderClustersTable();
  renderLinkSuggestions();
  populateSelects();
}

// ─── Settings ────────────────────────────────
async function checkSettings() {
  const s = await fetchJSON("/api/settings");
  const el = document.getElementById("apiKeyStatus");
  if (s.anthropic_api_key_set) {
    el.className = "badge bg-success";
    el.textContent = "API Key 設定済み";
  }
}

async function saveSettings() {
  const key = document.getElementById("apiKeyInput").value.trim();
  await postJSON("/api/settings", { anthropic_api_key: key });
  await checkSettings();
  bootstrap.Modal.getInstance(document.getElementById("settingsModal")).hide();
  toast("設定を保存しました", "success");
}

// ─── Articles ────────────────────────────────
function renderArticlesTable() {
  const q = document.getElementById("articleSearch").value.toLowerCase();
  let rows = articles.filter(a =>
    (a.main_kw || "").toLowerCase().includes(q) ||
    a.url.toLowerCase().includes(q)
  );

  rows.sort((a, b) => {
    const av = a[sortState.col] ?? "";
    const bv = b[sortState.col] ?? "";
    if (typeof av === "number") return (av - bv) * sortState.dir;
    return String(av).localeCompare(String(bv), "ja") * sortState.dir;
  });

  document.getElementById("articleCount").textContent = `${rows.length} 件`;
  const tbody = document.getElementById("articlesBody");
  tbody.innerHTML = rows.map(a => {
    const inCls  = countClass(a.inbound_count);
    const outCls = countClass(a.outbound_count);
    const crawledIcon = a.crawled_at
      ? `<span class="crawl-indicator crawled" title="${a.crawled_at}"><i class="bi bi-check-circle-fill"></i></span>`
      : `<span class="crawl-indicator" title="未クロール"><i class="bi bi-circle"></i></span>`;
    return `
    <tr>
      <td class="kw-cell" title="${esc(a.main_kw || "")}">${esc(a.main_kw || "（未設定）")}</td>
      <td class="url-cell"><a href="${esc(a.url)}" target="_blank" title="${esc(a.url)}">${shortUrl(a.url)}</a></td>
      <td class="text-center">
        <span class="inbound-count ${inCls}">${a.inbound_count}</span>
      </td>
      <td class="text-center">
        <span class="outbound-count ${outCls}">${a.outbound_count}</span>
      </td>
      <td class="text-center">
        ${crawledIcon}
        <button class="btn btn-xs btn-outline-secondary ms-1 py-0 px-1" onclick="crawlArticle(${a.id})" title="クロール">
          <i class="bi bi-cloud-download"></i>
        </button>
      </td>
      <td class="text-center">
        <button class="btn btn-xs btn-outline-primary py-0 px-1" onclick="showArticleDetail(${a.id})" title="詳細">
          <i class="bi bi-eye"></i>
        </button>
        <button class="btn btn-xs btn-outline-secondary py-0 px-1" onclick="openEditArticle(${a.id})" title="編集">
          <i class="bi bi-pencil"></i>
        </button>
        <button class="btn btn-xs btn-outline-danger py-0 px-1" onclick="deleteArticle(${a.id})" title="削除">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    </tr>`;
  }).join("");
}

function countClass(n) {
  if (n === 0) return "count-zero";
  if (n < 3)  return "count-low";
  return "count-good";
}

function openAddArticleModal() {
  document.getElementById("addArticleTitle").textContent = "記事追加";
  document.getElementById("editArticleId").value = "";
  document.getElementById("articleUrlInput").value = "";
  document.getElementById("articleKwInput").value = "";
  document.getElementById("articleTitleInput").value = "";
  new bootstrap.Modal(document.getElementById("addArticleModal")).show();
}

function openEditArticle(id) {
  const a = articles.find(x => x.id === id);
  if (!a) return;
  document.getElementById("addArticleTitle").textContent = "記事編集";
  document.getElementById("editArticleId").value = id;
  document.getElementById("articleUrlInput").value = a.url;
  document.getElementById("articleKwInput").value = a.main_kw || "";
  document.getElementById("articleTitleInput").value = a.title || "";
  new bootstrap.Modal(document.getElementById("addArticleModal")).show();
}

async function saveArticle() {
  const editId = document.getElementById("editArticleId").value;
  const url    = document.getElementById("articleUrlInput").value.trim();
  const kw     = document.getElementById("articleKwInput").value.trim();
  const title  = document.getElementById("articleTitleInput").value.trim();

  if (!url) { toast("URLを入力してください", "danger"); return; }

  if (editId) {
    await putJSON(`/api/articles/${editId}`, { main_kw: kw, title });
  } else {
    await postJSON("/api/articles", { url, main_kw: kw, title });
  }

  bootstrap.Modal.getInstance(document.getElementById("addArticleModal")).hide();
  toast("保存しました", "success");
  await loadAll();
}

async function deleteArticle(id) {
  if (!confirm("この記事を削除しますか？関連するリンク情報も削除されます。")) return;
  await deleteReq(`/api/articles/${id}`);
  toast("削除しました", "warning");
  await loadAll();
}

async function crawlArticle(id) {
  toast("クロール中...", "info");
  const result = await postJSON(`/api/crawl/${id}`, {});
  if (result.error) {
    toast(`クロール失敗: ${result.error}`, "danger");
  } else {
    toast(`クロール完了: ${result.links_found} 件のリンクを取得`, "success");
  }
  await loadAll();
}

async function startCrawlAll() {
  if (!confirm("全記事をクロールします。時間がかかる場合があります（約10〜20分）。")) return;
  await postJSON("/api/crawl/all", {});
  showCrawlProgress();
}

function showCrawlProgress() {
  let bar = document.getElementById("crawlProgressBar");
  if (!bar) {
    const div = document.createElement("div");
    div.id = "crawlProgressBar";
    div.className = "alert alert-info p-2 mb-2";
    div.innerHTML = `
      <div class="d-flex justify-content-between align-items-center mb-1">
        <strong><i class="bi bi-cloud-download me-1"></i>全記事クロール中...</strong>
        <span id="crawlProgressText" class="small text-muted"></span>
      </div>
      <div class="progress" style="height:8px">
        <div id="crawlProgressInner" class="progress-bar progress-bar-striped progress-bar-animated" style="width:0%"></div>
      </div>
      <div id="crawlCurrentUrl" class="small text-muted mt-1 text-truncate"></div>`;
    document.querySelector("#tabArticles .d-flex.justify-content-between").insertAdjacentElement("beforebegin", div);
    bar = div;
  }

  const timer = setInterval(async () => {
    const s = await fetchJSON("/api/crawl/status");
    const pct = s.total ? Math.round((s.done / s.total) * 100) : 0;
    document.getElementById("crawlProgressInner").style.width = pct + "%";
    document.getElementById("crawlProgressText").textContent = `${s.done} / ${s.total} 件 (エラー: ${s.errors})`;
    document.getElementById("crawlCurrentUrl").textContent = s.current_url ? `処理中: ...${s.current_url.split("/useful_info_ec/")[1] || s.current_url}` : "";

    if (!s.running && s.done > 0) {
      clearInterval(timer);
      document.getElementById("crawlProgressInner").classList.remove("progress-bar-animated");
      document.getElementById("crawlProgressInner").classList.add("bg-success");
      document.getElementById("crawlProgressText").textContent = `完了: ${s.done} 件クロール (エラー: ${s.errors})`;
      document.getElementById("crawlCurrentUrl").textContent = "";
      toast(`クロール完了！${s.done}記事のリンクを取得しました。`, "success");
      await loadAll();
      setTimeout(() => bar.remove(), 5000);
    }
  }, 2000);
}

// ─── Article Detail Drawer ───────────────────
async function showArticleDetail(id) {
  const a = articles.find(x => x.id === id);
  const detail = await fetchJSON(`/api/articles/${id}/links`);
  document.getElementById("drawerTitle").textContent = a.main_kw || shortUrl(a.url);

  const makeList = (items, dir) => {
    if (!items.length) return `<p class="text-muted small">なし</p>`;
    return items.map(l => `
      <div class="link-item">
        <span class="kw">${esc(l.main_kw || "（未設定）")}</span>
        <div>
          <a href="${esc(l.url)}" target="_blank" class="d-block" style="font-size:0.75rem">${shortUrl(l.url)}</a>
          ${l.anchor_text ? `<span class="anchor">${esc(l.anchor_text)}</span>` : ""}
        </div>
      </div>`).join("");
  };

  document.getElementById("drawerBody").innerHTML = `
    <div class="mb-1"><strong>URL:</strong> <a href="${esc(a.url)}" target="_blank" class="small" title="${esc(a.url)}">${esc(shortUrl(a.url))}</a></div>
    <div class="mb-1"><strong>メインKW:</strong> ${esc(a.main_kw || "未設定")}</div>
    <div class="mb-3"><strong>クロール:</strong> ${a.crawled_at || "未実施"}</div>
    <div class="link-section mb-3">
      <h6><i class="bi bi-arrow-down-circle text-primary me-1"></i>被内部リンク（${detail.inbound.length}件）</h6>
      ${makeList(detail.inbound, "in")}
    </div>
    <div class="link-section">
      <h6><i class="bi bi-arrow-up-circle text-success me-1"></i>発内部リンク（${detail.outbound.length}件）</h6>
      ${makeList(detail.outbound, "out")}
    </div>`;

  new bootstrap.Offcanvas(document.getElementById("articleDrawer")).show();
}

// ─── AI Link Suggestions ─────────────────────

async function runAILinkSuggest() {
  document.getElementById("aiLinkProgress").classList.remove("d-none");
  try {
    const result = await postJSON("/api/ai/suggest-links", {});
    if (result.error) {
      toast(`エラー: ${result.error}`, "danger");
    } else {
      toast(`${result.count} 件のリンク提案を生成しました`, "success");
      await loadAll();
    }
  } catch (e) {
    toast(`エラー: ${e.message}`, "danger");
  } finally {
    document.getElementById("aiLinkProgress").classList.add("d-none");
  }
}

function renderLinkSuggestions() {
  const q = (document.getElementById("suggSearch")?.value || "").toLowerCase();
  const hideConfirmed = document.getElementById("hideConfirmedSugg")?.checked;

  let rows = linkSuggestions.filter(s =>
    (s.from_kw || "").toLowerCase().includes(q) ||
    (s.to_kw   || "").toLowerCase().includes(q)
  );
  if (hideConfirmed) rows = rows.filter(s => !s.confirmed);

  document.getElementById("suggCount").textContent = `${rows.length} 件`;
  document.getElementById("suggBody").innerHTML = rows.map(s => `
    <tr class="${s.confirmed ? "table-success" : ""}">
      <td class="kw-cell fw-semibold">${esc(s.from_kw || "（未設定）")}</td>
      <td class="kw-cell">${esc(s.to_kw || "（未設定）")}</td>
      <td class="text-primary small fw-semibold">${esc(s.anchor_text || "")}</td>
      <td class="text-muted small">${esc(s.reason || "")}</td>
      <td class="text-center text-nowrap">
        ${s.confirmed
          ? `<span class="badge bg-success">追加済</span>`
          : `<button class="btn btn-xs btn-outline-success py-0 px-1" onclick="confirmSugg(${s.id})" title="リンクとして追加">
               <i class="bi bi-check-circle"></i> 追加
             </button>`}
        <button class="btn btn-xs btn-outline-danger py-0 px-1 ms-1" onclick="deleteSugg(${s.id})" title="却下">
          <i class="bi bi-x-circle"></i>
        </button>
      </td>
    </tr>`).join("") || `<tr><td colspan="5" class="text-center text-muted py-3">提案なし。「AIに提案させる」ボタンを押してください。</td></tr>`;
}

async function confirmSugg(id) {
  await postJSON(`/api/link-suggestions/${id}/confirm`, {});
  toast("リンクを追加しました", "success");
  await loadAll();
}

async function deleteSugg(id) {
  await deleteReq(`/api/link-suggestions/${id}`);
  toast("提案を却下しました", "warning");
  await loadAll();
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("suggSearch")?.addEventListener("input", renderLinkSuggestions);
  document.getElementById("hideConfirmedSugg")?.addEventListener("change", renderLinkSuggestions);
});

// ─── Links ───────────────────────────────────
function renderLinksTable() {
  const q = document.getElementById("linkSearch").value.toLowerCase();
  const rows = links.filter(l =>
    (l.from_kw || "").toLowerCase().includes(q) ||
    (l.to_kw   || "").toLowerCase().includes(q) ||
    l.from_url.toLowerCase().includes(q) ||
    l.to_url.toLowerCase().includes(q)
  );
  document.getElementById("linkCount").textContent = `${rows.length} 件`;
  document.getElementById("linksBody").innerHTML = rows.map(l => `
    <tr>
      <td class="kw-cell" title="${esc(l.from_kw || "")}">${esc(l.from_kw || "（未設定）")}</td>
      <td class="url-cell"><a href="${esc(l.from_url)}" target="_blank">${shortUrl(l.from_url)}</a></td>
      <td class="kw-cell" title="${esc(l.to_kw || "")}">${esc(l.to_kw || "（未設定）")}</td>
      <td class="url-cell"><a href="${esc(l.to_url)}" target="_blank">${shortUrl(l.to_url)}</a></td>
      <td class="text-muted small">${esc(l.anchor_text || "")}</td>
      <td class="text-center">
        <button class="btn btn-xs btn-outline-danger py-0 px-1" onclick="deleteLink(${l.id})">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    </tr>`).join("");
}

function openAddLinkModal() {
  new bootstrap.Modal(document.getElementById("addLinkModal")).show();
}

async function saveLink() {
  const from = document.getElementById("linkFromSelect").value;
  const to   = document.getElementById("linkToSelect").value;
  const anchor = document.getElementById("linkAnchorInput").value.trim();
  if (!from || !to) { toast("発リンク元とリンク先を選択してください", "danger"); return; }
  if (from === to)  { toast("同じ記事にはリンクできません", "danger"); return; }
  await postJSON("/api/links", { from_article_id: from, to_article_id: to, anchor_text: anchor });
  bootstrap.Modal.getInstance(document.getElementById("addLinkModal")).hide();
  toast("リンクを追加しました", "success");
  await loadAll();
}

async function deleteLink(id) {
  if (!confirm("このリンクを削除しますか？")) return;
  await deleteReq(`/api/links/${id}`);
  toast("削除しました", "warning");
  await loadAll();
}

// ─── Clusters ────────────────────────────────
function renderClustersTable() {
  const q = document.getElementById("clusterSearch").value.toLowerCase();
  const unconfirmedOnly = document.getElementById("showUnconfirmed").checked;

  let rows = clusters.filter(c =>
    (c.parent_kw || "").toLowerCase().includes(q) ||
    (c.child_kw  || "").toLowerCase().includes(q)
  );
  if (unconfirmedOnly) rows = rows.filter(c => !c.confirmed);

  document.getElementById("clustersBody").innerHTML = rows.map(c => {
    const aiB = c.ai_suggested
      ? `<span class="badge badge-ai">AI</span>`
      : `<span class="badge bg-secondary">手動</span>`;
    const confB = c.confirmed
      ? `<span class="badge badge-confirmed">確認済</span>`
      : `<span class="badge badge-pending">未確認</span>`;
    const confirmBtn = c.confirmed
      ? `<button class="btn btn-xs btn-outline-warning py-0 px-1" onclick="toggleConfirm(${c.id}, false)" title="未確認に戻す"><i class="bi bi-x-circle"></i></button>`
      : `<button class="btn btn-xs btn-outline-success py-0 px-1" onclick="toggleConfirm(${c.id}, true)" title="確認済みにする"><i class="bi bi-check-circle"></i></button>`;
    return `
    <tr class="${c.ai_suggested && !c.confirmed ? "cluster-row-ai" : c.confirmed ? "cluster-row-confirmed" : ""}">
      <td class="kw-cell fw-semibold" title="${esc(c.parent_kw || "")}">${esc(c.parent_kw || "（未設定）")}</td>
      <td class="kw-cell" title="${esc(c.child_kw || "")}">${esc(c.child_kw || "（未設定）")}</td>
      <td class="text-muted small" style="max-width:300px">${esc(c.reason || "")}</td>
      <td class="text-center">${aiB}</td>
      <td class="text-center">${confB}</td>
      <td class="text-center">
        ${confirmBtn}
        <button class="btn btn-xs btn-outline-danger py-0 px-1 ms-1" onclick="deleteCluster(${c.id})"><i class="bi bi-trash"></i></button>
      </td>
    </tr>`;
  }).join("");
}

async function runAISuggest() {
  document.getElementById("aiSuggestProgress").classList.remove("d-none");
  try {
    const result = await postJSON("/api/ai/suggest-clusters", {});
    if (result.error) {
      toast(`エラー: ${result.error}`, "danger");
    } else {
      toast(`${result.count} 件の親子関係を提案しました`, "success");
      await loadAll();
    }
  } catch (e) {
    toast(`エラー: ${e.message}`, "danger");
  } finally {
    document.getElementById("aiSuggestProgress").classList.add("d-none");
  }
}

function openAddClusterModal() {
  new bootstrap.Modal(document.getElementById("addClusterModal")).show();
}

async function saveCluster() {
  const parent = document.getElementById("clusterParentSelect").value;
  const child  = document.getElementById("clusterChildSelect").value;
  const reason = document.getElementById("clusterReasonInput").value.trim();
  if (!parent || !child) { toast("親記事と子記事を選択してください", "danger"); return; }
  if (parent === child)  { toast("同じ記事は選択できません", "danger"); return; }
  await postJSON("/api/clusters", { parent_article_id: parent, child_article_id: child, reason });
  bootstrap.Modal.getInstance(document.getElementById("addClusterModal")).hide();
  toast("追加しました", "success");
  await loadAll();
}

async function toggleConfirm(id, confirmed) {
  await patchJSON(`/api/clusters/${id}`, { confirmed });
  await loadAll();
}

async function deleteCluster(id) {
  if (!confirm("このクラスター関係を削除しますか？")) return;
  await deleteReq(`/api/clusters/${id}`);
  toast("削除しました", "warning");
  await loadAll();
}

// ─── Graph ───────────────────────────────────
async function renderGraph() {
  graphData = await fetchJSON("/api/graph");

  const showLinks    = document.getElementById("showLinksToggle").checked;
  const showClusters = document.getElementById("showClustersToggle").checked;
  const hideIsolated = document.getElementById("isolatedToggle").checked;

  // Build connected node IDs
  const connectedIds = new Set();
  if (showLinks) {
    graphData.edges.forEach(e => { connectedIds.add(e.from); connectedIds.add(e.to); });
  }
  if (showClusters) {
    graphData.cluster_edges.forEach(e => { connectedIds.add(e.from); connectedIds.add(e.to); });
  }

  const nodeList = hideIsolated
    ? graphData.nodes.filter(n => connectedIds.has(n.id))
    : graphData.nodes;

  const maxIn  = Math.max(...nodeList.map(n => n.inbound),  1);
  const maxOut = Math.max(...nodeList.map(n => n.outbound), 1);

  const nodes = new vis.DataSet(nodeList.map(n => {
    const size = 10 + (n.inbound / maxIn) * 30;
    return {
      id: n.id,
      label: n.label,
      title: `${n.label}\n被リンク: ${n.inbound}  発リンク: ${n.outbound}\n${shortUrl(n.url)}`,
      size,
      color: {
        background: inboundColor(n.inbound, maxIn),
        border: "#666",
        highlight: { background: "#ffd700", border: "#333" },
      },
      font: { size: 11 },
    };
  }));

  const edgeList = [];
  if (showLinks) {
    graphData.edges.forEach(e => edgeList.push({
      from: e.from, to: e.to,
      arrows: "to",
      color: { color: "#0d6efd", opacity: 0.5 },
      width: 1,
      title: e.label || "",
      dashes: false,
    }));
  }
  if (showClusters) {
    graphData.cluster_edges.forEach(e => edgeList.push({
      from: e.from, to: e.to,
      arrows: "to",
      color: { color: e.confirmed ? "#198754" : "#fd7e14", opacity: 0.8 },
      width: 2,
      dashes: !e.confirmed,
      title: e.confirmed ? "クラスター（確認済）" : "クラスター（未確認）",
    }));
  }
  const edges = new vis.DataSet(edgeList);

  document.getElementById("graphStats").textContent =
    `ノード ${nodes.length} / リンクエッジ ${showLinks ? graphData.edges.length : 0} / クラスターエッジ ${showClusters ? graphData.cluster_edges.length : 0}`;

  const container = document.getElementById("graphContainer");

  if (network) network.destroy();
  network = new vis.Network(container, { nodes, edges }, {
    physics: {
      enabled: true,
      stabilization: { iterations: 150 },
      barnesHut: { gravitationalConstant: -3000, springLength: 150 },
    },
    interaction: {
      hover: true,
      tooltipDelay: 200,
      zoomView: true,
    },
    edges: {
      smooth: { type: "continuous" },
    },
  });
}

function inboundColor(n, max) {
  if (n === 0)        return "#e9ecef";
  if (n < max * 0.25) return "#cfe2ff";
  if (n < max * 0.5)  return "#6ea8fe";
  if (n < max * 0.75) return "#0d6efd";
  return "#084298";
}

document.querySelectorAll("#showLinksToggle, #showClustersToggle, #isolatedToggle").forEach(el => {
  el.addEventListener("change", () => {
    if (document.getElementById("tabGraph").classList.contains("active")) renderGraph();
  });
});

// ─── Select population ───────────────────────
function populateSelects() {
  const opts = articles
    .sort((a, b) => (a.main_kw || "").localeCompare(b.main_kw || "", "ja"))
    .map(a => `<option value="${a.id}">${esc(a.main_kw || shortUrl(a.url))}</option>`)
    .join("");

  ["linkFromSelect", "linkToSelect", "clusterParentSelect", "clusterChildSelect"].forEach(id => {
    document.getElementById(id).innerHTML = `<option value="">選択してください</option>` + opts;
  });
}

// ─── Helpers ─────────────────────────────────
async function fetchJSON(url) {
  const r = await fetch(API + url);
  return r.json();
}

async function postJSON(url, body) {
  const r = await fetch(API + url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return r.json();
}

async function putJSON(url, body) {
  const r = await fetch(API + url, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return r.json();
}

async function patchJSON(url, body) {
  const r = await fetch(API + url, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return r.json();
}

async function deleteReq(url) {
  const r = await fetch(API + url, { method: "DELETE" });
  return r.json();
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function shortUrl(url) {
  // 旧 ".../{id}" 形式から "/{id}" 形式に統一（window.shortLabel を使用）
  if (typeof window !== "undefined" && typeof window.shortLabel === "function") {
    return window.shortLabel(url);
  }
  if (!url) return "";
  const m = url.match(/\/useful_info_ec\/(\d+)\/?/);
  return m ? "/" + m[1] : url;
}

function toast(msg, type = "secondary") {
  const c = document.getElementById("toast-container");
  const id = "t" + Date.now();
  c.insertAdjacentHTML("beforeend", `
    <div id="${id}" class="toast align-items-center text-bg-${type} border-0 show" role="alert">
      <div class="d-flex">
        <div class="toast-body">${msg}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" onclick="document.getElementById('${id}').remove()"></button>
      </div>
    </div>`);
  setTimeout(() => document.getElementById(id)?.remove(), 4000);
}
