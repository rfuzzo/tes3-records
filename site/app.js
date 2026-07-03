/* TES3 Records search — no dependencies, index is loaded once,
   full records are lazy-loaded per Source__Type shard. */
"use strict";

const PAGE_SIZE = 200;
const state = {
  records: [],      // [id, name, type, source, lowerName, lowerId]
  meta: null,
  query: "",
  sources: new Set(),
  types: new Set(),
  results: [],
  shown: 0,
  sortKey: null,    // null = relevance
  sortAsc: true,
  selected: null,   // "source/type/id"
  shardCache: new Map(),
};

const $ = (sel) => document.querySelector(sel);
const statusEl = $("#status");
const tbody = $("#results tbody");
const showMoreBtn = $("#show-more");
const detailPane = $("#detail");
const detailBody = $("#detail-body");

const COL = { id: 0, name: 1, type: 2, source: 3 };

/* ---------- boot ---------- */

async function boot() {
  try {
    const [meta, index] = await Promise.all([
      fetch("data/meta.json").then((r) => r.json()),
      fetch("data/index.json").then((r) => r.json()),
    ]);
    state.meta = meta;
    state.records = index.records.map((r) => {
      r.push(r[1].toLowerCase(), r[0].toLowerCase());
      return r;
    });
    $("#meta-info").textContent =
      `${meta.total.toLocaleString()} records · generated ${meta.generated}`;
    buildFilters();
    readHash();
    runSearch();
    if (state.selected) {
      const [src, type, ...idParts] = state.selected.split("/");
      openRecord(src, type, idParts.join("/"), false);
    }
  } catch (err) {
    statusEl.textContent = "Failed to load the record index: " + err;
  }
}

/* ---------- filters ---------- */

function buildFilters() {
  const srcBox = $("#source-filters");
  for (const [src, count] of Object.entries(state.meta.sources)) {
    srcBox.appendChild(makeChip(src, count, state.sources));
  }
  const typeBox = $("#type-filters");
  for (const [type, count] of Object.entries(state.meta.types)) {
    typeBox.appendChild(makeChip(type, count, state.types));
  }
}

function makeChip(label, count, set) {
  const chip = document.createElement("button");
  chip.className = "chip";
  chip.dataset.value = label;
  chip.innerHTML = `${escapeHtml(label)}<span class="count">${count.toLocaleString()}</span>`;
  chip.addEventListener("click", () => {
    set.has(label) ? set.delete(label) : set.add(label);
    chip.classList.toggle("active", set.has(label));
    runSearch();
    writeHash();
  });
  return chip;
}

function syncChips() {
  document.querySelectorAll("#source-filters .chip").forEach((c) =>
    c.classList.toggle("active", state.sources.has(c.dataset.value)));
  document.querySelectorAll("#type-filters .chip").forEach((c) =>
    c.classList.toggle("active", state.types.has(c.dataset.value)));
}

/* ---------- search ---------- */

function runSearch() {
  const terms = state.query.toLowerCase().split(/\s+/).filter(Boolean);
  const bySource = state.sources.size > 0;
  const byType = state.types.size > 0;
  const scored = [];

  for (const rec of state.records) {
    if (bySource && !state.sources.has(rec[3])) continue;
    if (byType && !state.types.has(rec[2])) continue;
    let score = 0;
    if (terms.length) {
      score = scoreRecord(rec[4], rec[5], terms);
      if (score < 0) continue;
    }
    scored.push([score, rec]);
  }

  if (state.sortKey) {
    const k = COL[state.sortKey];
    const dir = state.sortAsc ? 1 : -1;
    scored.sort((a, b) => dir * a[1][k].localeCompare(b[1][k]));
  } else if (terms.length) {
    scored.sort((a, b) => b[0] - a[0] || a[1][4].localeCompare(b[1][4]));
  } else {
    scored.sort((a, b) => a[1][4].localeCompare(b[1][4]));
  }

  state.results = scored.map((s) => s[1]);
  state.shown = 0;
  tbody.innerHTML = "";
  renderMore();
  statusEl.textContent = `${state.results.length.toLocaleString()} of ` +
    `${state.records.length.toLocaleString()} records match`;
}

/* All terms must match name or id; higher score = better placement. */
function scoreRecord(lname, lid, terms) {
  let total = 0;
  for (const t of terms) {
    let s = -1;
    const ni = lname.indexOf(t);
    if (ni === 0) s = lname.length === t.length ? 100 : 80;
    else if (ni > 0) s = lname[ni - 1] === " " ? 60 : 40;
    if (s < 0) {
      const ii = lid.indexOf(t);
      if (ii === 0) s = lid.length === t.length ? 90 : 70;
      else if (ii > 0) s = 30;
    }
    if (s < 0) return -1;
    total += s;
  }
  return total;
}

/* ---------- results table ---------- */

function renderMore() {
  const frag = document.createDocumentFragment();
  const terms = state.query.toLowerCase().split(/\s+/).filter(Boolean);
  const end = Math.min(state.shown + PAGE_SIZE, state.results.length);
  for (let i = state.shown; i < end; i++) {
    const [id, name, type, source] = state.results[i];
    const tr = document.createElement("tr");
    const key = `${source}/${type}/${id}`;
    tr.dataset.key = key;
    if (key === state.selected) tr.classList.add("selected");
    tr.innerHTML =
      `<td>${highlight(name, terms)}</td>` +
      `<td class="dim">${highlight(id, terms)}</td>` +
      `<td class="dim">${escapeHtml(type)}</td>` +
      `<td class="dim">${escapeHtml(source)}</td>`;
    tr.addEventListener("click", () => openRecord(source, type, id, true));
    frag.appendChild(tr);
  }
  state.shown = end;
  tbody.appendChild(frag);
  showMoreBtn.hidden = state.shown >= state.results.length;
  showMoreBtn.textContent =
    `Show more (${(state.results.length - state.shown).toLocaleString()} remaining)`;
}

function highlight(text, terms) {
  if (!terms.length) return escapeHtml(text);
  const lower = text.toLowerCase();
  const ranges = [];
  for (const t of terms) {
    let from = 0, idx;
    while ((idx = lower.indexOf(t, from)) !== -1) {
      ranges.push([idx, idx + t.length]);
      from = idx + 1;
    }
  }
  if (!ranges.length) return escapeHtml(text);
  ranges.sort((a, b) => a[0] - b[0]);
  const merged = [ranges[0]];
  for (const r of ranges.slice(1)) {
    const last = merged[merged.length - 1];
    if (r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push(r);
  }
  let html = "", pos = 0;
  for (const [a, b] of merged) {
    html += escapeHtml(text.slice(pos, a)) + "<mark>" + escapeHtml(text.slice(a, b)) + "</mark>";
    pos = b;
  }
  return html + escapeHtml(text.slice(pos));
}

/* ---------- detail panel ---------- */

async function openRecord(source, type, id, updateHash) {
  state.selected = `${source}/${type}/${id}`;
  document.querySelectorAll("#results tbody tr.selected")
    .forEach((tr) => tr.classList.remove("selected"));
  const row = tbody.querySelector(`tr[data-key="${CSS.escape(state.selected)}"]`);
  if (row) row.classList.add("selected");

  detailPane.hidden = false;
  detailBody.innerHTML = "<p>Loading…</p>";
  if (updateHash) writeHash();

  const shardKey = `${source}__${type}`;
  try {
    let shard = state.shardCache.get(shardKey);
    if (!shard) {
      shard = await fetch(`data/shards/${encodeURIComponent(shardKey)}.json`)
        .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
      state.shardCache.set(shardKey, shard);
    }
    const rec = shard[id];
    if (!rec) { detailBody.innerHTML = "<p>Record not found.</p>"; return; }
    renderRecord(rec, source, type);
  } catch (err) {
    detailBody.innerHTML = `<p>Failed to load record: ${escapeHtml(String(err))}</p>`;
  }
}

function renderRecord(rec, source, type) {
  const ghUrl = `https://github.com/${state.meta.repo}/blob/main/` +
    rec._file.split("/").map(encodeURIComponent).join("/");

  let html = `<h2>${escapeHtml(rec.name || rec.id)}</h2>` +
    `<div class="rec-id">${escapeHtml(rec.id)} · ${escapeHtml(type)} · ${escapeHtml(source)}</div>` +
    `<div class="rec-links"><a href="${ghUrl}" target="_blank" rel="noopener">View YAML on GitHub ↗</a></div>` +
    `<table class="kv"><tbody>`;

  const skip = new Set(["id", "name", "type", "_file", "text", "data"]);
  for (const [k, v] of Object.entries(rec)) {
    if (skip.has(k) || v === "" || v === null) continue;
    html += kvRow(k, v);
  }
  if (rec.data && typeof rec.data === "object") {
    html += `<tr class="section"><td colspan="2">data</td></tr>`;
    for (const [k, v] of Object.entries(rec.data)) {
      if (v === "" || v === null) continue;
      html += kvRow(k, v);
    }
  }
  html += "</tbody></table>";

  if (rec.text) {
    html += `<div class="book-text">${escapeHtml(stripHtmlTags(String(rec.text)))}</div>`;
  }
  detailBody.innerHTML = html;
}

function kvRow(key, value) {
  return `<tr><td class="k">${escapeHtml(key)}</td><td class="v">${formatValue(value)}</td></tr>`;
}

function formatValue(v) {
  if (Array.isArray(v)) {
    return v.map((x) => typeof x === "object" && x !== null
      ? escapeHtml(JSON.stringify(x)) : escapeHtml(String(x))).join("<br>");
  }
  if (typeof v === "object" && v !== null) {
    return Object.entries(v)
      .map(([k, x]) => `${escapeHtml(k)}: ${escapeHtml(
        typeof x === "object" && x !== null ? JSON.stringify(x) : String(x))}`)
      .join("<br>");
  }
  return escapeHtml(String(v));
}

/* Book text is raw Morrowind markup — show it as readable plain text. */
function stripHtmlTags(text) {
  return text
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div)>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/* ---------- URL hash state ---------- */

function writeHash() {
  const p = new URLSearchParams();
  if (state.query) p.set("q", state.query);
  if (state.sources.size) p.set("src", [...state.sources].join(","));
  if (state.types.size) p.set("type", [...state.types].join(","));
  if (state.selected) p.set("r", state.selected);
  const h = p.toString();
  history.replaceState(null, "", h ? "#" + h : location.pathname);
}

function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  state.query = p.get("q") || "";
  $("#search").value = state.query;
  // Mutate the existing sets — the filter chips hold references to them.
  state.sources.clear();
  (p.get("src") || "").split(",").filter(Boolean).forEach((s) => state.sources.add(s));
  state.types.clear();
  (p.get("type") || "").split(",").filter(Boolean).forEach((t) => state.types.add(t));
  state.selected = p.get("r") || null;
  syncChips();
}

/* ---------- misc ---------- */

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

let debounceTimer;
$("#search").addEventListener("input", (e) => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    state.query = e.target.value.trim();
    runSearch();
    writeHash();
  }, 120);
});

showMoreBtn.addEventListener("click", renderMore);

$("#detail-close").addEventListener("click", () => {
  detailPane.hidden = true;
  state.selected = null;
  document.querySelectorAll("#results tbody tr.selected")
    .forEach((tr) => tr.classList.remove("selected"));
  writeHash();
});

document.querySelectorAll("thead th").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.sort;
    if (state.sortKey === key) {
      if (state.sortAsc) state.sortAsc = false;
      else { state.sortKey = null; state.sortAsc = true; } // back to relevance
    } else {
      state.sortKey = key;
      state.sortAsc = true;
    }
    document.querySelectorAll("thead th").forEach((h) => {
      h.classList.toggle("sorted", h.dataset.sort === state.sortKey);
      h.classList.toggle("asc", h.dataset.sort === state.sortKey && state.sortAsc);
    });
    runSearch();
  });
});

boot();
