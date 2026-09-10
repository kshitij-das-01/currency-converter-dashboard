# Product Requirements Document (PRD)

## Currency Converter & Economic Dashboard

| Field            | Value                                          |
|------------------|------------------------------------------------|
| Document version | 1.0                                            |
| Status           | Approved for implementation                    |
| Owner            | Project owner                                  |
| Source inputs    | `currency_converter_dashboard_idea.md`, `RECONFIGURATION_PLAN.md` |
| Last updated     | 2026-08-25                                     |

---

## 1. Product Overview

### 1.1 Vision

A free, publicly accessible web application that lets anyone convert between world currencies and analyze historical exchange-rate trends — powered entirely by a C++ data engine, with **no database** and **no paid infrastructure**. The app is deployed as a single public URL (GitHub Pages) that any user can open in a browser.

### 1.2 Problem Statement

Existing currency tools are either:
- Simple web converters with no historical analysis, or
- Desktop apps requiring installation with hard-coded, stale rates.

Users who travel, budget internationally, or study currency trends need a **zero-install** tool that combines instant conversion with historical statistics (min/max/average/percent change/moving averages).

### 1.3 What This Project Demonstrates (Portfolio Goal)

- C++ applied to real-world financial data parsing and numerical computation
- A dual-target architecture: the same C++ core compiles to a native HTTP server **and** a WebAssembly module
- Modern web frontend engineering (vanilla HTML/CSS/JS, no framework)
- Professional Git/GitHub practices: CI, releases, and automated deployment to GitHub Pages

---

## 2. Goals & Non-Goals

### 2.1 Goals

| # | Goal |
|---|------|
| G1 | Public, shareable URL where the app runs for any visitor, with zero setup |
| G2 | Convert any supported currency pair using the latest rate in the dataset |
| G3 | Visualize historical rates as an interactive line chart over any date range |
| G4 | Compute statistics: min, max, average, % change, standard deviation, moving averages |
| G5 | All computation performed in C++ (native server locally; WebAssembly in production) |
| G6 | No database — the single source of truth is a Kaggle CSV dataset |
| G7 | Conversion history and favorites persist client-side via `localStorage` |
| G8 | Automated CI (build + test on every push) and automated deploy to GitHub Pages |

### 2.2 Non-Goals (v1.x)

- Live/exchange-rate API integration (dataset is static by design)
- Server-side user accounts or server-side persistence
- Mobile native apps
- Cryptocurrency support (deferred to v1.1+ backlog)
- Framework-based frontend (React/Vue/etc.)

---

## 3. Target Users & Personas

| Persona | Description | Primary use case |
|---------|-------------|------------------|
| **Traveler Tina** | Plans international trips, needs quick conversions | Enter amount → pick currencies → see result instantly |
| **Analyst Alex** | Studies currency movements, budgets across borders | Pick a pair + date range → read chart + stats |
| **Reviewer Rita** | Recruiter/portfolio reviewer evaluating engineering skill | Open public URL → use the app → inspect repo quality |

---

## 4. Architecture Overview

The defining constraint: **GitHub Pages serves static files only — it cannot run a C++ HTTP server.** Therefore the system is built as one platform-independent C++ core library with two transport layers:

```
                        ┌───────────────────────────────┐
                        │   core/ (C++17 static lib)    │
                        │   csv_parser · rate_engine    │
                        │   stats_engine · models       │
                        │   (no HTTP, no JS deps)       │
                        └──────────┬────────────────────┘
                                   │ compiled by…
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
┌──────────────────────────┐             ┌──────────────────────────────┐
│ server/ (native target)  │             │ wasm/ (Emscripten target)    │
│ cpp-httplib REST API     │             │ embind → CurrencyCore.js/wasm│
│ JSON responses           │             │ called directly from JS      │
│ Local dev / Docker /     │             │ GitHub Pages production      │
│ optional cloud hosting   │             │ (fully static, free)         │
└────────────┬─────────────┘             └──────────────┬───────────────┘
             │ HTTP :8080                               │ direct function calls
             ▼                                          ▼
        ┌───────────────────────────────────────────────────┐
        │        frontend/ (HTML5 + CSS3 + Vanilla JS)      │
        │   api.js adapter detects mode: REST or WASM       │
        │   Converter card · Chart.js line chart · Stats ·  │
        │   History & favorites (localStorage)              │
        └───────────────────────────────────────────────────┘
```

### 4.1 Data Flow

1. On startup/load, the CSV dataset (`data/exchange_rates.csv`) is parsed **once** into in-memory structures.
2. User performs actions in the UI.
3. Frontend calls the backend through one adapter interface:
   - Production (Pages): `api.js` calls exported WASM functions (`CurrencyCore`).
   - Local dev / hosted server: `api.js` issues `fetch()` calls to `/api/*`.
4. The C++ core computes results (conversion, filtering, statistics) and returns JSON.
5. UI renders results; history/favorites are stored in `localStorage` only.

### 4.2 Deployment Targets

| Target | Where it runs | Purpose | Cost |
|--------|---------------|---------|------|
| **WASM on GitHub Pages** (primary) | `https://<user>.github.io/<repo>/` | The public link any user can use | Free |
| Native HTTP server | Developer machine; optionally Render/Fly.io via Docker | API demonstration, local development | Free tier available |

---

## 5. Data Requirements

### 5.1 Source Dataset (acquired)

Raw export `daily_forex_rates.csv` (repo root, **gitignored**, 21.8 MB) — long format, one row per currency per day:

```csv
currency,base_currency,currency_name,exchange_rate,date
USD,EUR,United States Dollar,1.168765,2026-08-22
```

| Property | Audited value |
|----------|---------------|
| Rows | 497,430 |
| Currencies | 174 codes (incl. BTC, XAU, XDR) |
| Native base | EUR only (verified) |
| Date range | 2004-08-30 → 2026-08-23 · 6,551 unique dates |
| Quality | 0 duplicate pairs · 0 empty cells · exponent-notation tokens (BTC) |
| Coverage shape | Sparse ramp: ~2 currencies/day (2004) → ~172/day (2025); blanks are expected |
| Known quirk | No USD quotes on ~Sundays (542 dates); other currencies present |

> ⚠️ **Licensing:** confirm the Kaggle dataset's license permits redistribution and record it in `data/CREDITS.md` before the repo goes public. If redistribution is barred, ship only `data/sample_rates.csv` plus self-download instructions.

### 5.2 Canonical Schema (normalized)

**`data/exchange_rates.csv`** — wide format, **native EUR base preserved**. Column `X` = units of X per 1 EUR; pivot column `EUR` is constant `1`; blank cell = "no quote that day" (never row-dropping):

```csv
Date,AED,AUD,BTC,...,EUR,...,USD,...
2026-08-23,4.292815,1.630081,1.5082909e-05,...,1,...,1.16843,
```

Rules:
- Column 1 header must be `Date`; ISO-8601 (`YYYY-MM-DD`), ascending, unique.
- Remaining headers are ISO-4217-style codes; values are verbatim tokens (`.` decimal, exponents allowed).
- Cross conversion: `rate(A→B) = col[B] / col[A]`; direct from base: `rate(EUR→X) = col[X]`.

**Base decision:** NOT rebased to USD. The ratio formula is invariant to the base, but rebasing would delete the 542 Sunday dates lacking USD quotes (~8% of history) for zero functional benefit. Full rationale: [`implementation/A-data-pipeline.md`](implementation/A-data-pipeline.md).

Produced exclusively by `tools/normalize_dataset.py`, gated by `scripts/verify_dataset.py`, attributed in `data/CREDITS.md`. Regeneration steps: [`implementation/A-data-pipeline.md`](implementation/A-data-pipeline.md) §A.4.

### 5.3 Size Budgets (actuals)

- Canonical committed dataset: **4.6 MB** (budget ≤ 10 MB) → ≈1–1.5 MB gzipped in transit on Pages.
- Test fixture `sample_rates.csv`: **3.1 KB** (40 days × 8 majors).
- Raw export stays local-only (gitignored).

---

## 6. Functional Requirements

Priority key: **M** = Must (v1.0 MVP), **S** = Should (v1.0 stretch), **C** = Could (post-v1.0).

### 6.1 Data Engine (C++ Core)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-C1 | Parse canonical CSV schema into in-memory structures at load time | M |
| FR-C2 | Expose list of currencies plus min/max date of coverage | M |
| FR-C3 | Compute cross rate `from→to` for a given date; default to latest available date | M |
| FR-C4 | Skip malformed rows/cells gracefully; report skipped-row count in metadata | M |
| FR-C5 | Filter daily series for a pair within `[start,end]` inclusive | M |
| FR-C6 | Statistics over a filtered range: min, max, avg, % change (first→last), stddev, count | M |
| FR-C7 | Simple moving average series for configurable window N | S |
| FR-C8 | Deterministic error values for unknown currency, empty range, invalid date | M |

### 6.2 Backend Interfaces

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-B1 | Native HTTP server exposing all `/api/*` endpoints (§7.1) serving frontend statically | M |
| FR-B2 | WASM module exporting functions mirroring every REST endpoint (§7.2) | M |
| FR-B3 | Identical JSON response shapes between REST and WASM modes | M |
| FR-B4 | Structured error object `{ "error": { "code", "message" } }` in both modes | M |
| FR-B5 | Server CLI flags: `--port`, `--data <csv>`, `--static <dir>`; also honors `PORT` env var | S |

### 6.3 Frontend

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-F1 | Converter card: From/To dropdowns (populated from meta), amount input (numeric validation), live result display | M |
| FR-F2 | Result shows converted amount, rate used, and as-of date | M |
| FR-F3 | Swap button exchanging From/To instantly | S |
| FR-F4 | Trends view: pair picker, start/end date pickers bounded by data range, Chart.js line chart | M |
| FR-F5 | Stats panel rendering min/max/avg/%change/stddev/count for the selected range | M |
| FR-F6 | Moving-average overlay toggle (7-day / 30-day) on chart | S |
| FR-F7 | Conversion history (last 50) stored in `localStorage`, newest first | M |
| FR-F8 | Export history to CSV download | M |
| FR-F9 | Favorites: star pairs, shown as quick-pick chips | S |
| FR-F10 | api.js adapter auto-detects WASM vs REST mode | M |
| FR-F11 | Loading, empty ("No data for this range"), and error states for every async panel | M |
| FR-F12 | Responsive layout usable from 360 px mobile width to desktop | M |

---

## 7. Interface Specifications

### 7.1 REST API (native server)

Base URL: `http://localhost:8080`. All responses `application/json; charset=utf-8`. Field naming: camelCase.

| Method | Path | Query params | Purpose |
|--------|------|--------------|---------|
| GET | `/healthz` | – | Liveness probe → `{ "status": "ok" }` |
| GET | `/api/meta` | – | `{ base, currencies[], dateMin, dateMax, rowCount, rowsSkipped }` |
| GET | `/api/rate` | `from, to[, date]` | `{ from, to, date, rate }` |
| GET | `/api/convert` | `from, to, amount[, date]` | `{ from, to, amount, date, rate, result }` |
| GET | `/api/historical` | `from, to, start, end` | `{ from, to, points: [{ date, rate }] }` |
| GET | `/api/stats` | `from, to, start, end` | `{ min, max, avg, pctChange, stddev, count, firstDate, lastDate }` |
| GET | `/api/moving-average` | `from, to, start, end, window` | `{ window, points: [{ date, value }] }` |

Validation rules: ISO codes uppercase A–Z{3}; `amount` > 0 and finite; dates valid ISO-8601; `window` ≥ 2. Violations → HTTP 400. Unknown currency or empty range → 404. Internal failures → 500.

Error shape (all non-2xx):

```json
{ "error": { "code": "UNKNOWN_CURRENCY", "message": "Currency 'XYZ' is not in the dataset." } }
```

Static serving: `/` maps to the frontend directory (`index.html` fallback), so the server needs no CORS configuration in normal use.

### 7.2 WASM Module Interface

Build artifacts: `wasm/currency_core.js` + `currency_core.wasm`, built with `-sMODULARIZE=1 -sEXPORT_NAME=CurrencyCore -sALLOW_MEMORY_GROWTH=1 -O3`.

JS usage:

```javascript
const mod = await CurrencyCore();                 // instantiate
const meta = JSON.parse(mod.loadDataset(csvText)); // parse once, returns /api/meta shape
const conv = JSON.parse(mod.convert("USD","EUR",100,"2024-06-28")); // "" date ⇒ latest
const hist = JSON.parse(mod.historical("USD","EUR","2024-01-01","2024-12-31"));
const st   = JSON.parse(mod.stats("USD","EUR","2024-01-01","2024-12-31"));
const ma   = JSON.parse(mod.movingAverage("USD","EUR","2024-01-01","2024-12-31",30));
```

Contract: every export returns a **JSON string** matching the §7.1 response shapes, including errors (`{"error":{...}}`). Strings passed in are UTF-8; dates are `"YYYY-MM-DD"`.

---

## 8. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Performance — native | Parse a 10 MB CSV < 800 ms cold; API p95 latency < 10 ms after warm-up |
| Performance — WASM | Parse a 10 MB CSV < 3 s on a mid-range laptop; convert call < 1 ms post-load |
| Performance — web | First Contentful Paint < 1.5 s on GitHub Pages; Lighthouse Performance ≥ 90 |
| Accessibility | WCAG 2.1 AA basics: keyboard operable, labeled controls, contrast ≥ 4.5:1, result announced via `aria-live` |
| Compatibility | Latest two versions of Chrome, Firefox, Safari, Edge (all support WASM) |
| Portability (native) | Builds on macOS (clang), Linux (gcc), Windows (MSVC) via CMake |
| Security | No secrets, no user input persisted server-side; strict numeric/date parsing; recommended CSP `<meta>` tag |
| Privacy | All user state stays in browser `localStorage`; no analytics, no cookies |
| Reliability | Malformed CSV rows are skipped, counted, never crash; empty ranges produce clean "no data" states |
| Maintainability | Core has unit tests (doctest); CI runs build + tests on every push/PR |

---

## 9. UX Specification

### 9.1 Page Layout (single page, three stacked sections)

```
┌──────────────────────────────────────────────────────────────┐
│ Header: title · dataset range badge ("Jan 2015 – Aug 2026")  │
├──────────────────────────────────────────────────────────────┤
│ ① CONVERTER CARD                                             │
│   [FROM ▼] [⇄] [TO ▼]   AMOUNT [______]   [Convert]          │
│   Result banner: "100.00 USD = 92.35 EUR · rate 0.9235       │
│                    · as of 2026-08-21"   [☆ favorite]         │
├──────────────────────────────────────────────────────────────┤
│ ② TRENDS                                                     │
│   Pair chips (favorites first) · [start date] [end date]     │
│   ┌ LineChart (Chart.js): close rate, MA overlay toggle ┐    │
│   Stats grid: Min · Max · Avg · %Δ · StdDev · Points     │    │
├──────────────────────────────────────────────────────────────┤
│ ③ HISTORY                                    [Export CSV]     │
│   rows: time · from→to · amount · rate · result              │
│   Footer: data source credit + license note                  │
└──────────────────────────────────────────────────────────────┘
```

### 9.2 Interaction Rules

- Conversions append to history only when the user clicks **Convert** (not on typing).
- Date inputs clamp to `dateMin..dateMax`; invalid ranges disable the Apply button with helper text.
- Chart downsamples beyond ~400 points (stride sampling) to stay responsive; point count shown in caption.
- Every async panel has loading skeleton/spinner, then data, then a friendly empty/error message.
- Number formatting via `Intl.NumberFormat` with the target locale's currency style.

### 9.3 Client Persistence Keys

| Key | Contents |
|-----|----------|
| `ccd.history.v1` | Array of `{ ts, from, to, amount, rate, result }` (max 50) |
| `ccd.favorites.v1` | Array of `"FROM/TO"` strings |
| `ccd.settings.v1` | `{ defaultFrom, defaultTo }` |

---

## 10. Acceptance Criteria

**v1.0 ships when all of the following pass:**

1. `cmake && ctest`: all core unit tests green (parser, rate engine, stats, edge cases).
2. `curl` smoke suite against the native server returns correct JSON for every endpoint, including 400/404 paths.
3. WASM build loads in Chrome/Firefox/Safari and produces identical JSON outputs to the native server for the same inputs (golden-file comparison of ≥ 20 cases).
4. On the deployed Pages site: convert USD→EUR with a known dataset row and get the exact expected number; render a 1-year chart; stats match manual spreadsheet calculation on the sample dataset.
5. History survives page reload; Export CSV downloads a well-formed file.
6. Layout verified at 360 px, 768 px, 1280 px widths.
7. CI workflow green on the main branch; Pages deploy workflow produced the live URL automatically.
8. README documents: dataset placement, local run (server + Pages build), license/attribution.

---

## 11. Milestones & Timeline

| Milestone | Scope | Exit criteria |
|-----------|-------|---------------|
| **M0** (Day 1) | Repo scaffold, toolchain install, git init, branch protection, CI skeleton | Empty project builds in CI |
| **M1** (Days 2–4) | Core library: parser, engines, models + doctest suites | ctest green; golden CSV fixtures |
| **M2** (Day 5) | Native REST server + curl smoke tests | All endpoints correct |
| **M3** (Day 6) | Emscripten bindings + JS loader | WASM parity with REST |
| **M4** (Days 7–9) | Frontend complete (converter, chart, stats, history, export) | FR-F1…F12 done |
| **M5** (Day 10) | Polish, a11y, performance, docs, QA checklist | Acceptance 1–6 pass |
| **M6** (Day 11) | Deploy workflows live; tag `v1.0.0`; GitHub Release | Acceptance 7–8 pass; public URL shared |

Post-v1.0 backlog (Could-have): crypto columns, multi-pair comparison chart, inflation adjustment via CPI CSV, PWA offline mode, i18n, custom domain.

---

## 12. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Kaggle dataset format varies wildly | Parsing rework | Canonical schema + `tools/normalize_dataset.py` + sample fixture committed |
| Dataset license forbids redistribution | Can't ship data on Pages | Ship tiny sample; document self-download; normalize at runtime? (no—keep static) |
| Emscripten/CI flakiness | Broken deploys | Pin SDK version, cache toolchain, retry once |
| Large CSV bloats page weight | Slow first load | Trim columns/rows; gzip automatic on Pages; cap ≤ 10 MB |
| WASM memory limits on huge datasets | Load failure | `ALLOW_MEMORY_GROWTH=1`; enforce size budget; stream-parse |
| Path B host cold starts (if used) | 30–60 s first hit | Primary path is static WASM; Path B is optional demo only |
| Rate lookups off-by-one day | Wrong conversions | Unit tests pin exact dates against fixture values |

---

## 13. Success Metrics

- Public URL uptime ≈ 100% (static hosting)
- Median conversion interaction < 200 ms perceived (after load)
- Lighthouse ≥ 90 Performance / Accessibility
- Zero known incorrect-conversion defects after release
- Repo hygiene: conventional commits, tagged releases, green CI badge

---

## 14. Glossary

| Term | Meaning |
|------|---------|
| Base currency | Currency all CSV columns are quoted against (native EUR — see §5.2 decision) |
| Cross rate | Rate between two non-base currencies derived via the base |
| MA | Simple moving average over N observations |
| Dual-target | One C++ core built both as native binary and WASM |
| Golden test | Expected-output fixture used for parity checks |

---

*Implementation guidance begins in `docs/implementation/README.md` (read in numbered order).*
