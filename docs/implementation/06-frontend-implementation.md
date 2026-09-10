# 06 — Frontend Implementation

Goal: build the complete vanilla HTML/CSS/JS single-page app that talks to either transport through one adapter. Covers PRD FR-F1–FR-F12, §9 · Milestones M4 (Days 7–9).

## 6.1 File Responsibilities

| File | Responsibility |
|------|----------------|
| `index.html` | Semantic structure, three sections, script tags |
| `css/style.css` | Design tokens, layout, components, responsive rules |
| `js/config.js` | `MODE` ("wasm" \| "rest"), `API_BASE`, dataset path |
| `js/utils.js` | Formatting, dates, DOM helpers, CSV export |
| `js/api.js` | Transport adapter (WASM or REST) — the only file that knows the difference |
| `js/chart_panel.js` | Chart.js line chart + MA overlay + downsampling |
| `js/app.js` | State store, event wiring, rendering, history/favorites |

Script order in `index.html`:

```html
<script src="vendor/chart.umd.min.js"></script>          <!-- vendored Chart.js v4 -->
<script src="js/config.js"></script>
<script type="module" src="js/app.js"></script>          <!-- app imports api.js etc. -->
<script src="wasm/currency_core.js"></script>            <!-- only when MODE==='wasm' -->
```

Set mode by editing `config.js` (or a deploy-time sed in CI): production = `"wasm"`; local REST dev = `"rest"` with `API_BASE = "http://localhost:8080"`.

## 6.2 index.html Skeleton (semantics + a11y hooks)

```html
<body>
  <header class="app-header">
    <h1>Currency Converter & Economic Dashboard</h1>
    <span id="dataset-range" class="badge">Loading dataset…</span>
  </header>

  <main>
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

    <section id="trends" aria-labelledby="trends-h">
      <h2>Trends</h2>
      <form id="range-form">
        <label>Pair <select id="pair-select"></select></label>
        <label>Start <input type="date" id="start-date"></label>
        <label>End <input type="date" id="end-date"></label>
        <label><input type="checkbox" id="ma-toggle"> 30-day moving average</label>
        <button class="primary">Apply</button>
      </form>
      <div class="chart-wrap"><canvas id="rate-chart" role="img"
           aria-label="Historical exchange rate chart"></canvas></div>
      <dl id="stats-grid" class="stats-grid"></dl>
    </section>

    <section id="history" aria-labelledby="history-h">
      <h2>History <button id="export-csv">Export CSV</button></h2>
      <ul id="history-list"></ul>
    </section>
  </main>

  <footer><p>Data source & license: see <a href="https://github.com/<user>/…/data/CREDITS.md">CREDITS</a>.</p></footer>
</body>
```

Include a CSP meta tag: `<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'">`.

## 6.3 api.js — the Adapter (FR-F10)

```javascript
import { MODE, API_BASE } from "./config.js";

let wasmMod = null;

async function ensureWasm() {
  if (wasmMod) return wasmMod;
  const mod = await CurrencyCore();
  const csvResp = await fetch("data/exchange_rates.csv");
  const meta = JSON.parse(mod.loadDataset(await csvResp.text()));
  if (meta.error) throw new Error(meta.error.message);
  wasmMod = { meta, mod };
  return wasmMod;
}

async function call(path, params, wasmFn) {
  if (MODE === "wasm") {
    await ensureWasm();
    return JSON.parse(wasmFn(wasmMod.mod));
  }
  const url = `${API_BASE}${path}?${new URLSearchParams(params)}`;
  const resp = await fetch(url);
  const body = await resp.json();
  if (!resp.ok || body.error) throw Object.assign(new Error(body.error?.message ?? resp.statusText),
                                                { code: body.error?.code });
  return body;
}

export const api = {
  async init() {                                   // returns meta either way
    return MODE === "wasm"
      ? (await ensureWasm()).meta
      : call("/api/meta", {}, () => {});
  },
  convert:   (from, to, amount, date = "") =>
      call("/api/convert", { from, to, amount }, m => m.convert(from, to, amount, date)),
  historical:(from, to, start, end) =>
      call("/api/historical", { from, to, start, end }, m => m.historical(from, to, start, end)),
  stats:     (from, to, start, end) =>
      call("/api/stats", { from, to, start, end }, m => m.stats(from, to, start, end)),
  movingAvg: (from, to, start, end, window) =>
      call("/api/moving-average", { from, to, start, end, window },
           m => m.movingAverage(from, to, start, end, window)),
};
```

Every consumer catches errors and renders friendly messages — adapter throws typed errors uniformly in both modes.

## 6.4 app.js — State & Flow

Minimal store pattern (no framework):

```javascript
const state = {
  meta: null,
  favorites: loadLS("ccd.favorites.v1", []),
  history:   loadLS("ccd.history.v1", []),
  settings:  loadLS("ccd.settings.v1", { defaultFrom: "USD", defaultTo: "EUR" }),
  trend: { pair: null, start: null, end: null, maOn: false },
};
```

Startup sequence:
1. `renderLoading()` on header badge + panels.
2. `await api.init()` → populate both dropdowns (favorites first), clamp date inputs to `[dateMin, dateMax]`, set defaults from settings, fill range badge.
3. Auto-run initial conversion + trend render so the page is never empty.

**Convert flow:** validate amount > 0 → `api.convert(...)` → render result banner (FR-F2 format: `100.00 USD = 92.35 EUR · rate 0.9235 · as of DATE`) → unshift into history (cap 50, FR-F7) → persist → re-render list.

**Trend flow:** apply form → parallel `Promise.all([historical, stats])` (+ optional `movingAvg` when toggled) → feed chart + stats grid (FR-F5) → caption shows point count after any downsampling.

**Empty/error states (FR-F11):** every panel implements three states — spinner, data, message. Map adapter error codes: `UNKNOWN_CURRENCY`/`EMPTY_RANGE` → "No data available for this range." Others → generic retry line.

## 6.5 chart_panel.js

- Instantiate once; update datasets in place (Chart.js v4 UMD global).
- X axis = category labels of ISO dates; y axis begins at zero? No — `beginAtZero:false` for rates.
- Downsampling (FR-F4/§9.2): stride `ceil(n/400)` before assigning labels/data.
- MA overlay: second dataset, dashed, only when checkbox on; legend labels "Close rate"/"30-day MA".
- Destroy/recreate never needed except theme change; keep `responsive:true, maintainAspectRatio:false` inside fixed-height wrapper.

## 6.6 utils.js Essentials

```javascript
export const fmtMoney = (v, cur) => new Intl.NumberFormat(undefined,
  { style: "currency", currency: cur, maximumFractionDigits: 2 }).format(v);

export const fmtNum6 = v => new Intl.NumberFormat(undefined,
  { maximumFractionDigits: 6 }).format(v);

export function exportHistoryCsv(rows) {             // FR-F8
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
```

localStorage helpers are namespaced per PRD §9.3 and wrapped in try/catch (private browsing).

## 6.7 CSS Approach

- Custom properties for tokens: `--bg, --fg, --accent, --card, --radius, --shadow, --ok, --err`.
- Layout: single column flex; `@media (min-width: 768px)` two-column trends row (chart 2fr / stats 1fr); converter card uses `display:flex; gap; flex-wrap`.
- Breakpoints tested (PRD acceptance 6): **360 px**, **768 px**, **1280 px**.
- Focus-visible outlines, contrast ≥ 4.5:1, `.visually-hidden` utility, `prefers-reduced-motion` disables transitions.

## 6.8 Dev Workflows

```bash
# Mode A — full local stack (REST):
./build/server/currency_server --port 8080          # serves frontend itself
open http://localhost:8080                          # config.js MODE='rest', API_BASE='' (same origin)

# Mode B — static-only iteration on WASM (production parity):
python3 -m http.server 9000 -d frontend             # MODE='wasm'; needs wasm/ artifacts copied
```

## ✅ Exit Checklist

- [ ] Page fully usable at 360/768/1280 px; keyboard-only walkthrough passes
- [ ] Convert produces correct number matching curl output for same inputs
- [ ] Trend chart + stats render; empty range shows friendly message, no console errors
- [ ] History persists across reload; Export CSV opens correctly in spreadsheet apps
- [ ] Favorites chips reorder dropdown options and survive reload
- [ ] Both MODE values work without touching anything but `config.js`
- [ ] Lighthouse ≥ 90 performance & accessibility on the static build
- [ ] Commits: `feat(frontend): layout/styles`, `feat(frontend): converter flow`,
      `feat(frontend): trends panel`, `feat(frontend): history+favorites`
