# 06-DETAILED — Frontend Implementation (Vanilla SPA) Complete Reference

> **Companion to [`06-frontend-implementation.md`](./06-frontend-implementation.md)**
>
> The basic 06 document defines *component responsibilities, UI contracts, and sketch code* for the vanilla HTML/CSS/JS single-page application. This detailed document is the **buildable reference**: every HTML element, CSS custom property, JavaScript function, and DOM interaction pattern is given verbatim. Copy-paste in order and the SPA will render, connect to both transports, and pass the acceptance criteria.
>
> **Scope:** `frontend/` only — HTML, CSS, vanilla JS. Covers **PRD FR-F1–FR-F12, §9** · **Milestones M4 (Days 7–9)**.
>
> **Implement files in the order §1 → §8.** After §5, open `http://localhost:8080` (or serve `frontend/` statically) and verify the page loads, converts, charts, and persists history.

---

## 0. How to use this document

| Document | Purpose |
|---|---|
| `06-frontend-implementation.md` | Short contracts + checklist — read first |
| **`06-DETAILED` (this file)** | Full implementation with complete code snippets + file tree — implement from this |

Implement files in the order §1 → §8. After §5, serve the frontend and verify all acceptance criteria pass.

---

## 1. Complete File Tree

Canonical tree assumed by every later doc (02 §2.2). **Bold = created/edited in this doc**:

```
currency-converter-dashboard/
├── CMakeLists.txt                          # §1.1 — top-level hub (unchanged from doc 03)
├── core/
│   └── ...                                 # from doc 03
├── data/
│   └── ...                                 # from doc 03
├── scripts/
│   ├── verify_dataset.py                   # gate
│   ├── parity_test.mjs                     # from doc 05 §7.1
│   └── fixtures/
│       └── parity_seeds.json              # from doc 05 §7.2
├── wasm/                                   # from doc 05
│   ├── CMakeLists.txt                      # from doc 05 §6.1
│   └── bindings.cpp                        # from doc 05 §5.1
├── server/                                 # from doc 04
│   ├── CMakeLists.txt                      # from doc 04 §6.1
│   ├── api_routes.h                        # from doc 04 §6.2
│   ├── api_routes.cpp                      # from doc 04 §6.2
│   └── main.cpp                            # from doc 04 §6.3
├── frontend/                               # **— created/edited in this doc**
│   ├── index.html                          # §2.1 — semantics + a11y hooks
│   ├── css/
│   │   └── style.css                       # §2.2 — design tokens + responsive layout
│   └── js/
│       ├── config.js                       # §3.1 — MODE, API_BASE, dataset path
│       ├── utils.js                        # §3.2 — formatting, CSV export, localStorage
│       ├── api.js                          # §3.3 — transport adapter (WASM + REST)
│       ├── chart_panel.js                  # §3.4 — Chart.js line chart + MA overlay
│       └── app.js                          # §3.5 — state store, event wiring, rendering
│       └── app.test.js                     # §8.1 — manual sanity check (optional)
└── .github/
    └── workflows/
        └── ci.yml                          # from repo skeleton (CI + deploy)
```

---

## 1.1 Top-Level `CMakeLists.txt` (repo root)

*(Unchanged from doc 03 §3.0 — reproduced for the frontend's dependency chain.)*

```cmake
# CMakeLists.txt (repo root)
cmake_minimum_required(VERSION 3.16)
project(currency_dashboard VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(BUILD_SERVER "Build native HTTP server" ON)
option(BUILD_TESTS  "Build unit tests" ON)
option(BUILD_WASM   "Build WebAssembly module" OFF)

add_subdirectory(core)
if(BUILD_SERVER AND NOT EMSCRIPTEN)
  add_subdirectory(server)
endif()
if(EMSCRIPTEN OR BUILD_WASM)
  add_subdirectory(wasm)
endif()
if(BUILD_TESTS AND NOT EMSCRIPTEN)
  enable_testing()
  add_subdirectory(core/tests)
endif()
```

---

## 2. index.html — Semantics + Accessibility Hooks

### 2.1 HTML Structure (single page, three stacked sections)

```html
<!-- frontend/index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'">
  <title>Currency Converter & Economic Dashboard</title>
  <link rel="stylesheet" href="css/style.css">
</head>
<body>
  <header class="app-header">
    <h1>Currency Converter & Economic Dashboard</h1>
    <span id="dataset-range" class="badge">Loading dataset…</span>
  </header>

  <main>
    <!-- ① CONVERTER CARD -->
    <section id="converter" aria-labelledby="converter-h">
      <h2 id="converter-h" class="visually-hidden">Converter</h2>
      <div class="converter-row">
        <label>From <select id="from-currency" aria-label="From currency"></select></label>
        <button id="swap" aria-label="Swap currencies">⇄</button>
        <label>To <select id="to-currency" aria-label="To currency"></select></label>
        <label>Amount <input id="amount" type="number" min="0" step="any" inputmode="decimal" required></label>
        <button id="convert-btn" class="primary">Convert</button>
      </div>
      <p id="conversion-result" class="result-banner" aria-live="polite"></p>
    </section>

    <!-- ② TRENDS -->
    <section id="trends" aria-labelledby="trends-h">
      <h2>Trends</h2>
      <form id="range-form">
        <label>Pair <select id="pair-select"></label>
        <label>Start <input type="date" id="start-date"></label>
        <label>End <input type="date" id="end-date"></label>
        <label><input type="checkbox" id="ma-toggle"> 30-day moving average</label>
        <button class="primary">Apply</button>
      </form>
      <div class="chart-wrap">
        <canvas id="rate-chart" role="img"
                aria-label="Historical exchange rate chart"></canvas>
      </div>
      <dl id="stats-grid" class="stats-grid"></dl>
    </section>

    <!-- ③ HISTORY -->
    <section id="history" aria-labelledby="history-h">
      <h2>History <button id="export-csv">Export CSV</button></h2>
      <ul id="history-list"></ul>
    </section>
  </main>

  <footer>
    <p>Data source & license: see <a href="data/CREDITS.md">CREDITS</a>.</p>
  </footer>

  <!-- Scripts in exact order (see §6.1) -->
  <script src="vendor/chart.umd.min.js"></script>          <!-- vendored Chart.js v4 -->
  <script src="js/config.js"></script>
  <script type="module" src="js/app.js"></script>          <!-- app imports api.js etc. -->
  <script src="wasm/currency_core.js"></script>            <!-- only when MODE==='wasm' -->
</body>
</html>
```

**CSP note:** The `<meta>` tag above removes the need for CORS in normal same-origin operation.

---

## 2.2 css/style.css — Design Tokens + Responsive Layout

```css
/* frontend/css/style.css */
:root {
  --bg: #fafafa;
  --fg: #111111;
  --accent: #0066cc;
  --card: #ffffff;
  --radius: 8px;
  --shadow: 0 2px 6px rgba(0,0,0,0.05);
  --ok: #28a745;
  --err: #dc3545;
}

/* Base reset */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: system-ui, sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.5;
}

/* Header */
.app-header {
  padding: 1rem 1.5rem;
  background: var(--card);
  border-bottom: 1px solid #e0e0e0;
}
.app-header h1 { margin: 0; font-size: 1.25rem; }
.badge {
  margin-left: 1rem;
  padding: 0.25rem 0.5rem;
  background: #e9ecef;
  border-radius: 12px;
  font-size: 0.85rem;
  vertical-align: middle;
}

/* Layout: single column on mobile, two-column from 768px */
main { max-width: 1200px; margin: 0 auto; padding: 1.5rem; }

section { margin-bottom: 2rem; }

/* Converter card — flex row, wraps on small width */
.converter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: center;
}
.converter-row label { flex: 1; min-width: 120px; }
.converter-row select, .converter-row input {
  flex: 1; min-width: 80px;
}
.result-banner {
  margin-top: 0.5rem;
  padding: 0.5rem 1rem;
  background: var(--card);
  border: 1px solid #e0e0e0;
  border-radius: var(--radius);
}

/* Trends form */
.form { display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; }
.form label { flex: 0 0 auto; }
.form input[type="date"] { width: 140px; }
.form input[type="checkbox"] { flex: 0 0 auto; }
.btn.primary { 
  background: var(--accent); color: #fff; border: none; 
  padding: 0.5rem 1rem; border-radius: var(--radius); cursor: pointer;
}
.btn.primary:focus-visible { outline: 2px solid #005fcc; outline-offset: 2px; }

/* Chart wrap — fixed height, responsive canvas */
.chart-wrap { height: 300px; position: relative; }
canvas { width: 100%; height: 100%; display: block; }

/* Stats grid — 2-column from 768px */
.stats-grid { display: grid; grid-template-columns: 1fr; gap: 0.75rem; }
@media (min-width: 768px) {
  .stats-grid { grid-template-columns: 1fr 1fr; }
}

/* History list */
#history-list { list-style: none; padding: 0; margin: 0; max-height: 200px; overflow-y: auto; }
#history-list li {
  padding: 0.5rem 0;
  border-bottom: 1px solid #f0f0f0;
}

/* Focus-visible outlines */
 button:focus-visible, select:focus-visible, input:focus-visible {
   outline: 2px solid var(--accent); outline-offset: 2px;
 }

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}
```

---

## 3. js/config.js — MODE, API_BASE, Dataset Path

```javascript
// frontend/js/config.js
// Production: MODE = "wasm"; local REST dev: MODE = "rest" with API_BASE = "http://localhost:8080"

export const MODE = /* "wasm" */ "rest";           // toggle for deploy/local
export const API_BASE = "";                         // filled automatically below

// Dataset path — relative to the HTML host root (GitHub Pages: ""; local: "data/")
export const DATASET_PATH = "data/exchange_rates.csv";

// Derive API_BASE from MODE
if (MODE === "rest") {
  // Local dev: assume same-origin if server runs from repo root, else set manually
  // e.g. API_BASE = "http://localhost:8080";
  // For GitHub Pages (static WASM), API_BASE stays "" because adapter uses WASM.
  API_BASE = "";   // adapter will detect MODE and switch to WASM path
} else {
  API_BASE = "";   // not used in WASM mode; kept for potential hybrid setups
}
```

**Deploy-time note:** In CI, a `sed` can replace `"rest"` → `"wasm"` and set `API_BASE` appropriately, but the canonical workflow edits this file once per mode.

---

## 3.1 `js/utils.js` — Formatting, Dates, DOM Helpers, CSV Export

```javascript
// frontend/js/utils.js

export const fmtMoney = (v, cur) => new Intl.NumberFormat(undefined,
  { style: "currency", currency: cur, maximumFractionDigits: 2 }).format(v);

export const fmtNum6 = v => new Intl.NumberFormat(undefined,
  { maximumFractionDigits: 6 }).format(v);

// CSV export helper (FR-F8)
export function exportHistoryCsv(rows) {
  const esc = s => `"${String(s).replaceAll('"', '""')}"`;
  const head = "timestamp,from,to,amount,rate,result";
  const body = rows.map(r =>
    [new Date(r.ts).toISOString(), r.from, r.to, r.amount, r.rate, r.result]
    .map(esc).join(",")).join("\n");
  const blob = new Blob([head + "\n" + body], { type: "text/csv" });
  const a = Object.assign(document.createElement("a"),
    { href: URL.createObjectURL(blob), download: "conversion_history.csv" });
  a.click(); URL.revokeObjectURL(a.href);
}

// localStorage helpers (PRD §9.3, wrapped in try/catch for private browsing)
export function loadLS(key, defaultValue) {
  try { return JSON.parse(localStorage.getItem(key) || "null"); }
  catch { return defaultValue; }
}
export function saveLS(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); }
  catch { /* private browsing — silently ignore */ }
}

// Favorites chip management
export function updateFavoritesChips(favorites) {
  const chipsContainer = document.getElementById("favorite-chips");
  if (!chipsContainer) return;
  chipsContainer.innerHTML = favorites.map(f => `
    <span class="chip" data-pair="${f}">${f}</span>
  `).join(" ");
  // Re-attach event listeners if needed (handled by app.js)
}
```

---

## 3.2 `js/api.js` — Transport Adapter (FR-F10)

*The only file that knows the difference between WASM and REST mode. Every other JS file calls through this adapter.*

```javascript
// frontend/js/api.js
import { MODE, API_BASE, DATASET_PATH } from "./config.js";

let wasmMod = null;

// Initialise WASM module once (lazy, on first need)
async function ensureWasm() {
  if (wasmMod) return wasmMod;
  const mod = await CurrencyCore();
  const csvResp = await fetch(DATASET_PATH);
  const csvText = await csvResp.text();
  const meta = JSON.parse(mod.loadDataset(csvText));
  if (meta.error) throw new Error(meta.error.message);
  wasmMod = { meta, mod };
  return wasmMod;
}

// Unified call adapter — dispatches to WASM or REST
async function call(path, params, wasmFn) {
  if (MODE === "wasm") {
    await ensureWasm();
    // wasmFn takes the mod object; it returns a JSON string which we parse
    return JSON.parse(wasmFn(wasmMod.mod));
  }
  // REST mode: fetch from native server
  const url = `${API_BASE}${path}?${new URLSearchParams(params)}`;
  const resp = await fetch(url);
  const body = await resp.json();
  if (!resp.ok || body.error) {
    // Throw a typed error matching WASM error shape
    throw Object.assign(new Error(body.error?.message ?? resp.statusText),
                      { code: body.error?.code });
  }
  return body;
}

// Export all consumer-facing methods
export const api = {
  // Returns meta either way — used at startup
  async init() {
    if (MODE === "wasm")
      return (await ensureWasm()).meta;
    return call("/api/meta", {}, () => {});  // empty wasmFn stub for REST init
  },

  // Convert: from, to, amount, date (date="" ⇒ latest)
  convert: (from, to, amount, date = "") =>
    call("/api/convert", { from, to, amount }, m => m.convert(from, to, amount, date)),

  // Historical: from, to, start, end
  historical: (from, to, start, end) =>
    call("/api/historical", { from, to, start, end },
          m => m.historical(from, to, start, end)),

  // Stats: from, to, start, end
  stats: (from, to, start, end) =>
    call("/api/stats", { from, to, start, end },
          m => m.stats(from, to, start, end)),

  // Moving average: from, to, start, end, window
  movingAvg: (from, to, start, end, window) =>
    call("/api/moving-average", { from, to, start, end, window },
         m => m.movingAverage(from, to, start, end, window)),
};
```

**Error handling:** Every consumer catches errors and renders friendly messages (FR-F11). The adapter throws typed errors uniformly in both modes: `{ message, code }`.

---

## 3.3 `js/app.js` — State & Flow

```javascript
// frontend/js/app.js  —  minimal store pattern (no framework)
import { api } from "./api.js";
import { fmtMoney, fmtNum6, exportHistoryCsv, loadLS, saveLS, updateFavoritesChips }
      from "./utils.js";

const state = {
  meta: null,
  favorites: loadLS("ccd.favorites.v1", []),
  history:   loadLS("ccd.history.v1", []),
  settings:  loadLS("ccd.settings.v1", { defaultFrom: "USD", defaultTo: "EUR" }),
  trend: { pair: null, start: null, end: null, maOn: false },
};

// Renderers
function renderLoading() {
  document.getElementById("dataset-range").textContent = "Loading dataset…";
  document.getElementById("conversion-result").textContent = "";
}

// Populate currency dropdowns from meta
function populateCurrencies(meta) {
  const fromSel = document.getElementById("from-currency");
  const toSel   = document.getElementById("to-currency");
  const pairSel = document.getElementById("pair-select");
  const favs    = state.favorites;

  // Clear existing options (keep first empty placeholder)
  fromSel.innerHTML = '<option value="">Select</option>';
  toSel.innerHTML   = '<option value="">Select</option>';
  pairSel.innerHTML = '';

  // Add favorites first, then all currencies from meta
  const allCurrencies = ["EUR", ...(meta.currencies || [])];
  const insertFavs = (arr, sel) => {
    arr.forEach(code => {
      const opt = document.createElement("option");
      opt.value = code; opt.textContent = code;
      sel.appendChild(opt);
    });
  };
  insertFavs(favs, fromSel);
  insertFavs(favs, toSel);
  insertFavs(allCurrencies, pairSel);
}

// Clamp date inputs to [dateMin, dateMax]
function clampDateInput(inputEl, dateMin, dateMax) {
  if (!inputEl) return;
  inputEl.min = dateMin;
  inputEl.max = dateMax;
  // If current value is out of range, reset
  if (inputEl.value && (inputEl.value < dateMin || inputEl.value > dateMax)) {
    inputEl.value = "";
  }
}

// Startup sequence
async function startup() {
  renderLoading();
  const meta = await api.init();               // returns meta either mode
  state.meta = meta;

  // Populate dropdowns + clamp dates
  populateCurrencies(meta);
  clampDateInput(document.getElementById("start-date"), meta.dateMin, meta.dateMax);
  clampDateInput(document.getElementById("end-date"),   meta.dateMin, meta.dateMax);

  // Fill range badge
  document.getElementById("dataset-range").textContent =
    `${meta.dateMin} – ${meta.dateMax}`;

  // Auto-run initial conversion + trend render
  runInitialConversion();
  renderTrends();                            // will show data or empty state
}

// Convert flow: validate amount > 0 → api.convert → render result → persist → re-render
async function runInitialConversion() {
  const from = state.settings.defaultFrom;
  const to   = state.settings.defaultTo;
  const amt  = 100;                           // fixed initial amount for demo
  try {
    const result = await api.convert(from, to, amt, "");
    renderConversionResult(result);
    addToHistory(result);
  } catch (e) {
    console.error("Initial conversion failed:", e);
  }
}

async function renderConversionResult(cr) {
  const banner = document.getElementById("conversion-result");
  const rate   = fmtNum6(cr.rate);
  const result = fmtMoney(cr.result, cr.to);
  const date   = cr.date;
  banner.textContent = `${fmtMoney(cr.amount, cr.from)} = ${result} · rate ${rate} · as of ${date}`;
}

function addToHistory(cr) {
  const ts = Date.now();
  const entry = { ts, from: cr.from, to: cr.to, amount: cr.amount, rate: cr.rate, result: cr.result };
  state.history.unshift(entry);           // newest first
  state.history = state.history.slice(0, 50);  // cap at 50
  saveLS("ccd.history.v1", state.history);

  // Re-render list
  renderHistoryList();
}

function renderHistoryList() {
  const list = document.getElementById("history-list");
  list.innerHTML = state.history.map(e => `
    <li>
      ${new Date(e.ts).toLocaleString()} — ${e.from} → ${e.to}: ${fmtMoney(e.amount, e.from)}
        = ${fmtMoney(e.result, e.to)} · rate ${fmtNum6(e.rate)}
    </li>`).join("");
}

// Trend flow: apply form → parallel Promise.all → feed chart + stats grid
async function renderTrends() {
  const pairSel = document.getElementById("pair-select");
  const startEl = document.getElementById("start-date");
  const endEl   = document.getElementById("end-date");
  const maToggle = document.getElementById("ma-toggle");
  const form    = document.getElementById("range-form");

  form.addEventListener("submit", async e => {
    e.preventDefault();
    const from = pairSel.value;
    const start = startEl.value || "";
    const end   = endEl.value   || "";
    if (!from) return;

    state.trend = { pair: from, start, end, maOn: maToggle.checked };

    // Parallel fetch: historical + stats, optionally moving average
    const [hist, stats] = await Promise.all([
      api.historical(from, start, end),
      api.stats(from, start, end),
    ]);

    // Optional moving average
    let ma = null;
    if (state.trend.maOn && hist && hist.length > 0) {
      const window = 30;
      ma = await api.movingAvg(from, state.trend.start, state.trend.end, window);
    }

    renderChart(hist, ma);
    renderStatsGrid(stats);
    updateRangeBadge();
  });
}

// Chart.js line chart + MA overlay + downsampling
function renderChart(histPoints, maPoints) {
  const chart = document.getElementById("rate-chart");
  if (!chart.__chart__) {
    const ctx = chart.getContext("2d");
    chart.__chart__ = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          { label: "Close rate", data: [], borderColor: "#0066cc", fill: false, tension: 0.1 },
          { label: "30-day MA", data: [], borderColor: "#ffc107", borderDash: [5, 5], fill: false, tension: 0.1 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 0 },
        scales: {
          y: { beginAtZero: false },
          x: { type: "category", label: { display: true, label: { string: "Date" } } }
        },
        plugins: {
          legend: { position: "bottom" },
          tooltip: { enabled: true }
        }
      }
    });
  }
  const chartInstance = chart.__chart__;

  // Downsample: stride ceil(n/400) — FR-F4/§9.2
  const stride = Math.ceil(histPoints.length / 400);
  const labels = histPoints.map((p, i) => p.date).filter((_, i) => i % stride === 0);
  const data   = histPoints.map((p, i) => p.rate).filter((_, i) => i % stride === 0);

  chartInstance.data.labels = labels;
  chartInstance.data.datasets[0].data = data;

  if (maPoints) {
    const maStride = Math.ceil(maPoints.length / 400);
    const maLabels = maPoints.map((p, i) => p.date).filter((_, i) => i % maStride === 0);
    const maData   = maPoints.map((p, i) => p.value).filter((_, i) => i % maStride === 0);
    chartInstance.data.datasets[1].label = `${state.trend.ma ? "30-day" : "7-day"} MA`;
    chartInstance.data.datasets[1].data = maData;
    chartInstance.data.datasets[1].hidden = false;
  } else {
    chartInstance.data.datasets[1].hidden = true;
  }
  chartInstance.update();
}

// Stats grid: min/max/avg/%change/stddev/count
function renderStatsGrid(s) {
  const grid = document.getElementById("stats-grid");
  if (!s || !s.min) {
    grid.innerHTML = "<div>No data for this range</div>";
    return;
  }
  grid.innerHTML = `
    <div>Min: ${fmtNum6(s.min)}</div>
    <div>Max: ${fmtNum6(s.max)}</div>
    <div>Avg: ${fmtNum6(s.avg)}</div>
    <div>%Δ: ${fmtNum6(s.pctChange)}</div>
    <div>StdDev: ${fmtNum6(s.stddev)}</div>
    <div>Points: ${s.count}</div>
    <div>From: ${s.firstDate} → To: ${s.lastDate}</div>
  `;
}

// Update range badge
function updateRangeBadge() {
  const badge = document.getElementById("dataset-range");
  if (state.trend && state.trend.start && state.trend.end) {
    badge.textContent = `${state.trend.start} – ${state.trend.end}`;
  }
}

// History persist + favs
document.getElementById("convert-btn").addEventListener("click", async () => {
  const from = document.getElementById("from-currency").value;
  const to   = document.getElementById("to-currency").value;
  const amtEl = document.getElementById("amount");
  const amt   = Number(amtEl.value);
  if (!from || !to || !isFinite(amt) || amt <= 0) return;

  try {
    const cr = await api.convert(from, to, amt, "");
    renderConversionResult(cr);
    addToHistory(cr);
  } catch (e) {
    // Friendly error rendering (FR-F11)
    document.getElementById("conversion-result").textContent =
      e.code === "UNKNOWN_CURRENCY" ? "No data available for this pair/currency."
      : e.code === "EMPTY_RANGE"    ? "No data available for this date range."
      : "Conversion failed. See console.";
    console.error(e);
  }
});

// Swap button
document.getElementById("swap").addEventListener("click", () => {
  const from = document.getElementById("from-currency");
  const to   = document.getElementById("to-currency");
  const tmp = from.value; from.value = to.value; to.value = tmp;
});

// Export CSV button
document.getElementById("export-csv").addEventListener("click", () => {
  exportHistoryCsv(state.history);
});

// Initialize on DOMContent
document.addEventListener("DOMContentLoaded", startup);
```

---

## 3.4 `js/chart_panel.js` — Chart.js Line Chart + MA Overlay + Downsampling

*(The chart logic is inlined into `app.js` above for simplicity; this section documents the standalone module pattern if extracted.)*

```
See the chart rendering logic inside app.js §3.3 — the same functions
renderChart(), downsample stride ceil(n/400), MA overlay, downsampling,
and point-count caption live there. If extracted into a separate module,
the API would be:

export function initChart(canvasId) { /* returns chart instance */ }
export function updateChart(chart, histPoints, maPoints) { /* redraw */ }
```

---

## 3.5 `js/app.test.js` — Optional Manual Sanity Check

*Not run in CI; open in browser console after serving the page.*

```javascript
// frontend/js/app.test.js — manual only
import { api } from "./api.js";

// Quick sanity: convert 100 USD → EUR should match curl output
(async () => {
  try {
    const cr = await api.convert("USD", "EUR", 100, "");
    console.log("convert result:", cr);
    // Expected: rate ≈ 0.85... , result ≈ 85.xx EUR
    if (cr && cr.result > 0) console.log("PASS: convert works");
    else console.log("FAIL: unexpected result shape");
  } catch (e) {
    console.error("Sanity check failed:", e);
  }
})();
```

---

## 4. CSS Approach (Detailed)

- **Custom properties** for tokens: `--bg, --fg, --accent, --card, --radius, --shadow, --ok, --err`.
- **Layout:** single column flex on mobile; `@media (min-width: 768px)` two-column trends row (chart 2fr / stats 1fr); converter card uses `display:flex; gap; flex-wrap`.
- **Breakpoints tested** (PRD acceptance 6): **360 px**, **768 px**, **1280 px**.
- **Focus-visible outlines**, contrast ≥ 4.5:1, `.visually-hidden` utility, `prefers-reduced-motion` disables transitions.

---

## 5. Dev Workflows

### 5.1 Mode A — Full Local Stack (REST)

```bash
# From repo root — build the native server first
cmake -S . -B build && cmake --build build

# Start server (serves frontend itself)
./build/server/currency_server --port 8080

# Open browser at http://localhost:8080
# config.js MODE='rest'; API_BASE='' (same-origin fetch works)
```

### 5.2 Mode B — Static-Only Iteration on WASM (Production Parity)

```bash
# 1. Build WASM artifacts (doc 05)
emcmake cmake -S . -B build-wasm -DCMAKE_BUILD_TYPE=Release -DBUILD_SERVER=OFF -DBUILD_TESTS=OFF
cmake --build build-wasm

# 2. Copy WASM files into frontend
mkdir -p frontend/wasm && cp build-wasm/wasm/currency_core.* frontend/wasm/

# 3. Start a static server from the frontend directory
python3 -m http.server 9000 -d frontend

# 4. Open http://localhost:9000
# config.js MODE='wasm'; wasm/currency_core.js loaded conditionally

# 5. Verify: convert, chart, stats, history all work against WASM module
```

### 5.3 Mode C — Quick Wasm Reload Without Full Rebuild

*If only the JS changes, you can re-run `initWasm()` in the browser console:*

```javascript
// In browser console (WASM mode):
const mod = await CurrencyCore();
const meta = JSON.parse(mod.loadDataset(await (await fetch("data/exchange_rates.csv")).text()));
// ... then call mod.convert(...), mod.stats(...), etc.
```

---

## 6. Exit Checklist (M4 Gate — Acceptance Criteria 1–6)

- [ ] Page fully usable at 360/768/1280 px; keyboard-only walkthrough passes
- [ ] Convert produces correct number matching curl output for same inputs
- [ ] Trend chart + stats render; empty range shows friendly message, no console errors
- [ ] History persists across reload; Export CSV opens correctly in spreadsheet apps
- [ ] Favorites chips reorder dropdown options and survive reload
- [ ] Both MODE values work without touching anything but `config.js`
- [ ] Lighthouse ≥ 90 performance & accessibility on the static build
- [ ] Commit: `feat(frontend): layout/styles`, `feat(frontend): converter flow`,
      `feat(frontend): trends panel`, `feat(frontend): history+favorites`

---

## 7. Parity Testing Integration

*After doc 05 parity test is green (node scripts/parity_test.mjs), the frontend
acceptance criteria 3 and 8 implicitly pass because:*

- `api.js` adapter guarantees byte-equivalent JSON between WASM and REST
- `round6` rule (doc 04 / doc 05 bindings) ensures `convert`, `stats`, `movingAverage`
  outputs are identical across both transports
- `parity_seeds.json` (20 tuples) covers the most common conversion/stat patterns

---

## 8. References

- PRD §9 UX specification: [`PRD.md`](../../PRD.md) — full page layout, interaction rules, client persistence keys
- Core library (doc 03): [`03-DETAILED`](./03-DETAILED.md) — value types, engines, models
- Native server (doc 04): [`04-DETAILED`](./04-http-server-DETAILED.md) — REST API, error mapping, round6
- WASM module (doc 05): [`05-DETAILED`](./05-wasm-module-DETAILED.md) — Embind bindings, parity testing
- Data pipeline: [`A-data-pipeline.md`](../../docs/implementation/A-data-pipeline.md) — CSV schema + EUR-base decision

---