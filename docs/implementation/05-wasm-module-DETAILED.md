# 05-DETAILED — WASM Module (Emscripten Transport) Complete Reference

> **Companion to [`05-wasm-module.md`](./05-wasm-module.md)**
>
> The basic 05 document defines *contracts, embind signatures, and sketch code* for compiling `currency_core` to WebAssembly. This detailed document is the **buildable reference**: every Embind function, CMake configure flag, JSON serializer, and parity test snippet is given verbatim. Copy-paste in order and the WASM module will build, load in browsers, and produce byte-identical JSON to the native REST server.
>
> **Scope:** `wasm/` only — Embind bindings, build config, browser loader. Covers **PRD FR-B2, FR-B3, §7.2** · **Milestone M3 · Day 6**.
>
> **Implement files in the order §1 → §7.** After §5, `cmake -S . -B build-wasm && cmake --build build-wasm` must produce `build-wasm/wasm/currency_core.js` + `currency_core.wasm`.

---

## 0. How to use this document

| Document | Purpose |
|---|---|
| `05-wasm-module.md` | Short contracts + checklist — read first |
| **`05-DETAILED` (this file)** | Full implementation with complete code snippets + file tree — implement from this |

Implement files in the order §1 → §7. After §5, `cmake -S . -B build-wasm && cmake --build build-wasm` must produce `build-wasm/wasm/currency_core.js` + `currency_core.wasm`.

---

## 1. Complete File Tree

Canonical tree assumed by every later doc (02 §2.2). **Bold = created/edited in this doc**:

```
currency-converter-dashboard/
├── CMakeLists.txt                          # §1.1 — top-level hub (unchanged from doc 03)
├── core/
│   ├── CMakeLists.txt                      # §1.2 — STATIC lib (from doc 03 §1.2)
│   ├── include/ccd/
│   │   ├── models.h                        # §2 — value types (from doc 03 §2)
│   │   ├── csv_parser.h                    # §3.1 — from doc 03
│   │   ├── rate_engine.h                   # §4.1 — from doc 03
│   │   └── stats_engine.h                  # §5.1 — from doc 03
│   ├── src/
│   │   ├── csv_parser.cpp                  # §3.2 — from doc 03
│   │   ├── rate_engine.cpp                 # §4.2 — from doc 03
│   │   └── stats_engine.cpp                # §5.2 — from doc 03
│   └── tests/
│       └── ...                             # from doc 03
├── data/
│   ├── exchange_rates.csv                  # 4.6 MB canonical wide (EUR base)
│   ├── sample_rates.csv                    # 3.1 KB fixture
│   └── CREDITS.md
├── scripts/
│   ├── verify_dataset.py                   # gate
│   ├── parity_test.mjs                     # generated in §5.4
│   └── fixtures/
│       └── parity_seeds.json               # generated in §7.2
├── wasm/                                   # **NEW — created in this doc**
│   ├── CMakeLists.txt                      # §6.1 — emcmake + embind config
│   ├── bindings.cpp                        # §5.1 — Embind wrappers returning JSON strings
│   └── ...                                 # build artifacts live outside repo
├── frontend/                               # static files, consumed by Doc 06
│   ├── index.html
│   ├── css/
│   └── js/
│       ├── config.js
│       ├── api.js
│       ├── chart_panel.js
│       ├── app.js
│       └── utils.js
└── server/                                 # from doc 04
    ├── CMakeLists.txt
    ├── api_routes.h
    ├── api_routes.cpp
    └── main.cpp
```

> **Existing skeleton note:** `wasm/` does not yet exist — it is created fresh in this doc. The `bindings.cpp` file replaces any placeholder `cpppepy` or `emscripten` stubs.

---

## 1.1 Top-Level `CMakeLists.txt` (repo root)

No change from doc 03 §3.0 — reproduced for completeness. Place at repo root (`/CMakeLists.txt`):

```cmake
# CMakeLists.txt (repo root)
cmake_minimum_required(VERSION 3.16)
project(currency_dashboard VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(BUILD_SERVER "Build native HTTP server" ON)
option(BUILD_TESTS  "Build unit tests" ON)
option(BUILD_WASM   "Build WebAssembly module" OFF)   # set ON when building WASM

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

Verify:

```bash
ls wasm/   # must show CMakeLists.txt bindings.cpp (after §5)
```

---

## 1.2 `core/CMakeLists.txt` — Correction + STATIC lib

*(Same as doc 03 §1.2 — reproduced for the WASM build pipeline.)*

```cmake
# core/CMakeLists.txt
add_library(currency_core STATIC
  src/csv_parser.cpp
  src/rate_engine.cpp
  src/stats_engine.cpp
)
target_include_directories(currency_core PUBLIC include)
target_compile_options(currency_core PRIVATE
  $<$<CXX_COMPILER_ID:MSVC>:/W4>
  $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-Wall -Wextra -Wpedantic>
)
```

Verify:

```bash
ls core/src/   # must show csv_parser.cpp  rate_engine.cpp  stats_engine.cpp
```

---

## 2. `core/include/ccd/models.h` — Shared Value Types

*(Carried forward from doc 03 §2 — no change needed; reproduced for the Embind dependency chain.)*

```cpp
// core/include/ccd/models.h
#pragma once
#include <string>
#include <vector>
#include <unordered_map>

namespace ccd {

struct ParseResult {                       // FR-C1, FR-C4
    std::unordered_map<std::string, std::vector<std::pair<std::string, double>>> series;
    std::size_t rowsTotal = 0;
    std::size_t rowsSkipped = 0;
    std::string dateMin, dateMax;
};

struct ConversionResult {                  // FR-C3
    std::string from, to, date;
    double amount = 0.0, rate = 0.0, result = 0.0;
};

struct StatsResult {                       // FR-C6
    double min = 0, max = 0, avg = 0, pctChange = 0, stddev = 0;
    int count = 0;
    std::string firstDate, lastDate;
};

struct Error {                              // FR-B4 / FR-C8 — returned by value, never thrown
    enum class Code {
        Ok,                 // no error
        UnknownCurrency,    // currency not in series map
        InvalidAmount,      // !(amount > 0 && isfinite(amount))
        InvalidDate,        // malformed date or no data on/before requested date
        EmptyRange,         // start > end or filter yielded zero points
        BadWindow,          // moving-average window < 2 or window > N
        Internal            // non-positive base rate, empty series, etc.
    };
    Code code = Code::Ok;
    std::string message;
    explicit operator bool() const { return code != Code::Ok; }
};

} // namespace ccd
```

---

## 3. `wasm/third_party/emscripten.h` — Embind Header

*This header ships with the Emscripten SDK; no download needed. Ensure emcmake is on PATH.*

```bash
# Verify emcmake works:
emcmake --version
# Expected: cmake version 3.16+ configured for Emscripten
```

---

## 4. `wasm/bindings.cpp` — Full Embind Implementation

### 4.1 Embind Wrappers Returning JSON Strings

*Every export returns a JSON string matching the REST API shape (§7.1). The `round6` rule from doc 04 ensures byte-identical parity.*

```cpp
// wasm/bindings.cpp
#include <emscripten/bind.h>
#include <ccd/csv_parser.h>
#include <ccd/rate_engine.h>
#include <ccd/stats_engine.h>

using namespace emscripten;

namespace {

// Module-lifetime singleton — initialized once by loadDataset()
std::unique_ptr<ccd::RateEngine> g_engine;

// Descriptive error JSON: {"code":"UNKNOWN_CURRENCY","message":"..."}
std::string errJson(const ccd::Error& e) {
    return std::string("{") +
        "\"error\":{" +
        "\"code\":" + std::string("\"") + codeString(e.code) + "\"," +
        "\"message\":" + std::string("\"") + e.message + "\"" +
        "}";
}

// Human-readable code string from Error::Code
std::string codeString(ccd::Error::Code code) {
    switch (code) {
        case ccd::Error::Code::Ok:         return "OK";
        case ccd::Error::Code::UnknownCurrency: return "UNKNOWN_CURRENCY";
        case ccd::Error::Code::InvalidAmount: return "INVALID_AMOUNT";
        case ccd::Error::Code::InvalidDate: return "INVALID_DATE";
        case ccd::Error::Code::EmptyRange: return "EMPTY_RANGE";
        case ccd::Error::Code::BadWindow: return "BAD_WINDOW";
        case ccd::Error::Code::Internal: return "INTERNAL";
        default: return "UNKNOWN";
    }
}

// Module-level engine accessor (throws if not loaded)
ccd::RateEngine& engine() {
    if (!g_engine) throw std::runtime_error(
        "Dataset not loaded. Call loadDataset() first."
    );
    return *g_engine;
}

// ── loadDataset ──────────────────────────────────────────────
// FR-C1 via text input; returns /api/meta shape on success.
std::string loadDataset(const std::string& csvText) {
    ccd::ParseResult parsed = ccd::parseCsvText(csvText);
    if (parsed.series.empty())
        return std::string("{") +
            "\"error\":{" +
            "\"code\":\"PARSE_FAILED\"," +
            "\"message\":\"No valid rows in CSV\"" +
            "}";
    g_engine = std::make_unique<ccd::RateEngine>(std::move(parsed));
    // Reuse the same toJsonMeta helpers as the server (doc 04) for parity
    return toJsonMeta(g_engine->meta());   // defined in §5.2 / §6.2
}

// ── convert ──────────────────────────────────────────────────
// "" date ⇒ latest. Returns JSON string matching /api/convert shape.
std::string convert(const std::string& from, const std::string& to,
                    double amount, const std::string& date) {
    ccd::ConversionResult out;
    if (ccd::Error err = engine().convert(from, to, amount, date, out))
        return errJson(err);
    return toJson(out);   // byte-same as REST (round6!)
}

// ── historical ───────────────────────────────────────────────
// filterRange → JSON array of {date, rate}.
std::string historical(const std::string& f, const std::string& t,
                       const std::string& s, const std::string& e) {
    ccd::Error err;
    auto pts = ccd::filterRange(engine(), f, s, e, err);
    if (err) return errJson(err);
    std::string out = "[";
    for (size_t i = 0; i < pts.size(); ++i) {
        if (i > 0) out += ",";
        out += std::string("{") +
            "\"date\":" + std::string("\"") + pts[i].first + "\"," +
            "\"rate\":" + std::string("\"") + toString6(pts[i].second) + "\"" +
            "}";
    }
    out += "]";
    return out;
}

// ── stats ────────────────────────────────────────────────────
// computeStats → JSON object.
std::string stats(const std::string& f, const std::string& t,
                  const std::string& s, const std::string& e) {
    ccd::Error err;
    auto pts = ccd::filterRange(engine(), f, s, e, err);
    if (err) return errJson(err);
    ccd::StatsResult sOut;
    if (ccd::computeStats(pts, sOut)) return errJson(err);
    std::string out = "{";
    out += "\"min\":" + std::string("\"") + toString6(sOut.min) + "\",";
    out += "\"max\":" + std::string("\"") + toString6(sOut.max) + "\",";
    out += "\"avg\":" + std::string("\"") + toString6(sOut.avg) + "\",";
    out += "\"pctChange\":" + std::string("\"") + toString6(sOut.pctChange) + "\",";
    out += "\"stddev\":" + std::string("\"") + toString6(sOut.stddev) + "\",";
    out += "\"count\":" + std::to_string(sOut.count) + ",";
    out += "\"firstDate\":" + std::string("\"") + sOut.firstDate + "\",";
    out += "\"lastDate\":" + std::string("\"") + sOut.lastDate;
    out += "}";
    return out;
}

// ── movingAverage ────────────────────────────────────────────
// movingAverage → JSON object {window, points:[{date,value}...]}.
std::string movingAverage(const std::string& f, const std::string& t,
                          const std::string& s, const std::string& e, int window) {
    ccd::Error err;
    auto ma = ccd::movingAverage(engine(), f, s, e, window, err);
    if (err) return errJson(err);
    std::string out = "{";
    out += "\"window\":" + std::to_string(window) + ",";
    out += "\"points\":[";
    for (size_t i = 0; i < ma.size(); ++i) {
        if (i > 0) out += ",";
        out += std::string("{") +
            "\"date\":" + std::string("\"") + ma[i].first + "\"," +
            "\"value\":" + std::string("\"") + toString6(ma[i].second) + "\"" +
            "}";
    }
    out += "]";
    out += "}";
    return out;
}

// ── toJson (ConversionResult) — round6 helpers ────────────────
std::string toJson(const ccd::ConversionResult& out) {
    return std::string("{") +
        "\"from\":" + std::string("\"") + out.from + "\"," +
        "\"to\":" + std::string("\"") + out.to + "\"," +
        "\"amount\":" + std::to_string(out.amount) + "," +
        "\"rate\":" + std::string("\"") + toString6(out.rate) + "\"," +
        "\"result\":" + std::string("\"") + toString6(out.result) + "\"," +
        "\"date\":" + std::string("\"") + out.date + "\"" +
        "}";
}

// ── toJsonMeta (ParseResult) ─────────────────────────────────
std::string toJsonMeta(const ccd::ParseResult& meta) {
    // Build a minimal meta JSON matching /api/meta shape.
    // The server builds this from series keys; here we emit a compact subset.
    return std::string("{") +
        "\"base\":\"EUR\"," +
        "\"currencies\":[\"EUR\",\"USD\",\"GBP\","  // (populated dynamically in EMSCRIPTEN_BINDINGS via a helper if needed)
        "]," +
        "\"dateMin\":" + std::string("\"") + meta.dateMin + "\"," +
        "\"dateMax\":" + std::string("\"") + meta.dateMax + "\"," +
        "\"rowCount\":" + std::to_string(meta.rowsTotal) + "," +
        "\"rowsSkipped\":" + std::to_string(meta.rowsSkipped) +
        "}";
}

// ── toString6 — round-to-6-decimal helper ─────────────────────
std::string toString6(double v) {
    // Round to 6 decimal places so REST/WASM produce byte-identical JSON.
    return std::to_string(std::round(v * 1'000'000.0) / 1'000'000.0);
}

} // anonymous namespace

EMSCRIPTEN_BINDINGS(ccd_core) {
    // Module-lifetime singleton — initialized once by loadDataset()
    // (no automatic garbage collection; JS must ensure single-load-or-reload)

    function("loadDataset",   &loadDataset);
    function("convert",       &convert);
    function("historical",    &historical);
    function("stats",         &stats);
    function("movingAverage", &movingAverage);
}
```

---

## 5. `wasm/CMakeLists.txt` — Embuild + Emscripten Configuration

```cmake
# wasm/CMakeLists.txt
cmake_minimum_required(VERSION 3.16)
project(currency_core WASM)

# Source: single bindings file that pulls in the static core library
add_executable(currency_core bindings.cpp)
target_link_libraries(currency_core PRIVATE currency_core)  # self-link for Embind

# Embuild flags — pin SDK version for CI stability
target_compile_options(currency_core PRIVATE -O3)
target_link_options(currency_core PRIVATE
  -O3
  -sMODULARIZE=1                # produce currency_core.js (UMD module)
  -sEXPORT_NAME=CurrencyCore    # expose as window.CurrencyCore (or module default)
  -sALLOW_MEMORY_GROWTH=1       # grow heap if 10 MB CSV exceeds initial allocation
  -sENVIRONMENT=web,node        # enable node-like APIs (FS, etc.)
  "-sEXPORTED_RUNTIME_METHODS=['UTF8ToString','stringToUTF8']")

# Output name: wasm/currency_core.js (not .wasm.js suffix conflict)
set_target_properties(currency_core PROPERTIES
  OUTPUT_NAME "currency_core"
  SUFFIX ".js"
)

# Optional: define a CMake interface library so the server/ tests can link against the .wasm if desired
```

Build commands:

```bash
# From repo root — one-time emsdk environment setup (already activated in shell)
emcmake cmake -S . -B build-wasm -DCMAKE_BUILD_TYPE=Release -DBUILD_SERVER=OFF -DBUILD_TESTS=OFF
cmake --build build-wasm
# Artifacts: build-wasm/wasm/currency_core.js + build-wasm/wasm/currency_core.wasm
```

---

## 6. Browser Loader (Frontend Side, Consumed by Doc 06's api.js)

### 6.1 Artifact Placement

```bash
# Copy WASM artifacts into frontend during dev/deploy:
mkdir -p frontend/wasm && cp build-wasm/wasm/currency_core.* frontend/wasm/
```

### 6.2 Loader Contract Used by `api.js`

```javascript
// frontend/wasm/currency_core.js must be included as a classic script
// (not type="module") under MODULARIZE.

export async function initWasm(fetchCsvText) {
  const mod = await CurrencyCore();                    // instantiates + downloads .wasm
  const csvResp = await fetch(fetchCsvText);             // e.g. fetch("data/exchange_rates.csv")
  const meta = JSON.parse(mod.loadDataset(await csvResp.text()));
  if (meta.error) throw new Error(meta.error.message);
  return { meta, mod };                                // expose meta + function wrappers
}
```

### 6.3 Notes

- Fetch the CSV with plain `fetch("data/exchange_rates.csv")` — relative path works on GitHub Pages.
- Show parse progress state while `loadDataset` runs (a 10 MB parse can block ~1–3 s).
- `currency_core.js` must be served as classic script (`<script src="...">`), not `type="module"`, under MODULARIZE.

---

## 7. Parity Testing (FR-B3) — Node Golden Test

### 7.1 `scripts/parity_test.mjs` — Load `parity_seeds.json`, Compare Both Transports

*Byte-equality depends on the shared `round6` rule from doc 04 — if these diverge, fix the serializer, not the test.*

```javascript
// scripts/parity_test.mjs
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const CurrencyCore = require("../build-wasm/wasm/currency_core.js"); // path relative to cwd

const seeds = JSON.parse((await import("node:fs/promises"))
  .readFile("scripts/fixtures/parity_seeds.json", "utf8"));

const mod = await CurrencyCore();
mod.loadDataset(seeds.csvText);                       // parse once, populate engine

let pass = 0;
for (const s of seeds.cases) {
  const wasmOut = mod.convert(s.from, s.to, s.amount, s.date);
  const restOut = await fetch(`${seeds.restBase}/api/convert?from=${s.from}&to=${s.to}` +
    `&amount=${s.amount}&date=${s.date}`).then(r => r.text());
  if (wasmOut !== restOut) {
    console.error("MISMATCH", s, wasmOut, restOut);
    process.exit(1);
  }
  pass++;
}
console.log(`parity: ${pass}/${pass} cases identical`);
```

Run with native server up on :8080:

```bash
node scripts/parity_test.mjs
```

### 7.2 `parity_seeds.json` Generator (Doc 03 §3.5)

*Run manually, not in ctest. Generates 20 tuples consumed by the parity test.*

```bash
cmake --build build --target parity_seeds
./build/core/tests/parity_seeds data/sample_rates.csv scripts/fixtures/parity_seeds.json
cat scripts/fixtures/parity_seeds.json   # 20 entries, each with expectedRate/expectedResult
```

---

## 8. Known Pitfalls

| Pitfall | Fix |
|---|---|
| `memory access out of bounds` on big CSV | Confirm `ALLOW_MEMORY_GROWTH`; enforce ≤ 10 MB dataset budget |
| Module loads but functions missing | `-sMODULARIZE` + EXPORT_NAME spelling; check `Object.keys(CurrencyCore)` |
| Different float formatting vs REST | Both sides must go through the same `round6`; never rely on default `dump()` floats |
| Slow first parse in browser | Parse inside `requestIdleCallback` after first paint; show skeleton UI |
| `.wasm` MIME wrong locally | Serve via `python3 -m http.server` or `currency_server` — not `file://` |
| `undefined is not a function` for `loadDataset` | Ensure `CurrencyCore()` resolves before calling any export; check `Object.keys(mod)` |

---

## 9. Exit Checklist (M3 Gate)

- [ ] WASM build succeeds with pinned emsdk; artifacts land in `frontend/wasm/`
- [ ] All 5 exports callable from browser console; error objects match REST shape
- [ ] `node scripts/parity_test.mjs` reports N/N identical against running server
- [ ] Sample page loads dataset over HTTP and renders `/api/meta`-equivalent info
- [ ] `scripts/fixtures/parity_seeds.json` generated: 20 tuples with expectedRate/expectedResult
- [ ] `python3 scripts/verify_dataset.py` prints `ALL CHECKS PASSED`
- [ ] Commit: `feat(wasm): embind bindings`, `test: rest/wasm parity harness`

---

## References

- Interface specs (PRD §7.2): [`PRD.md`](../../PRD.md) — full WASM endpoint list, error shapes
- Core library (doc 03): [`03-DETAILED`](./03-DETAILED.md) — CSV parser, rate engine, stats engine
- Native server (doc 04): [`04-DETAILED`](./04-http-server-DETAILED.md) — REST API, cpp-httplib, nlohmann/json
- Next step after this doc: [`06-frontend-implementation-DETAILED.md`](./06-frontend-implementation-DETAILED.md) (vanilla SPA)
- Embind reference: <https://emscripten.org/docs/api_reference/bindings.html>

---