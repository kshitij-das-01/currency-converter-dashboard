# 05 — WebAssembly Module (Emscripten Transport)

Goal: compile the **same** `currency_core` to a browser-runnable module exposing the exact same JSON contract as the REST API. This is what makes GitHub Pages a complete backend-less deployment. Covers PRD FR-B2, FR-B3, §7.2 · Milestone M3 · Day 6.

## 5.1 Bindings (`wasm/bindings.cpp`)

Use Embind; return **JSON strings** everywhere so marshalling stays trivial and identical to REST:

```cpp
#include <emscripten/bind.h>
#include <ccd/csv_parser.h>
#include <ccd/rate_engine.h>
#include <ccd/stats_engine.h>

using namespace emscripten;

namespace {
std::unique_ptr<ccd::RateEngine> g_engine;      // module-lifetime singleton

nlohmann::json errJson(const ccd::Error& e) {
    return {{"error", {{"code", codeString(e.code)}, {"message", e.message}}}};
}

ccd::RateEngine& engine() {
    if (!g_engine) throw std::runtime_error("Dataset not loaded. Call loadDataset() first.");
    return *g_engine;
}
} // namespace

std::string loadDataset(const std::string& csvText) {          // FR-C1 via text input
    ccd::ParseResult parsed = ccd::parseCsvText(csvText);
    if (parsed.series.empty())
        return nlohmann::json({{"error",{{"code","PARSE_FAILED"},
                               {"message","No valid rows in CSV"}}}}).dump();
    g_engine = std::make_unique<ccd::RateEngine>(std::move(parsed));
    return toJsonMeta(g_engine->meta()).dump();                 // same shape as /api/meta
}

std::string convert(const std::string& from, const std::string& to,
                    double amount, const std::string& date) {   // "" date ⇒ latest
    ccd::ConversionResult out;
    if (ccd::Error err = engine().convert(from, to, amount, date, out))
        return errJson(err).dump();
    return toJson(out).dump();                                  // byte-same as REST (round6!)
}

std::string historical(const std::string& f, const std::string& t,
                       const std::string& s, const std::string& e) { /* filterRange → JSON */ }
std::string stats(...)       { /* computeStats → JSON */ }
std::string movingAverage(..., int window) { /* → JSON */ }

EMSCRIPTEN_BINDINGS(ccd_core) {
    function("loadDataset",   &loadDataset);
    function("convert",       &convert);
    function("historical",    &historical);
    function("stats",         &stats);
    function("movingAverage", &movingAverage);
}
```

> Reuse the **same** `toJson*()` helpers as the server. Extract them into a tiny shared header (e.g. `core/include/ccd/json_serialize.h` guarded by `#ifndef EMSCRIPTEN` for the httplib parts) so REST/WASM parity is structural, not aspirational.

## 5.2 Build Config (`wasm/CMakeLists.txt`)

```cmake
add_executable(currency_core bindings.cpp)
target_link_libraries(currency_core PRIVATE currency_core_lib)  # rename core lib if clash
target_compile_options(currency_core PRIVATE -O3)
target_link_options(currency_core PRIVATE
  -O3
  -sMODULARIZE=1
  -sEXPORT_NAME=CurrencyCore
  -sALLOW_MEMORY_GROWTH=1
  -sENVIRONMENT=web,node
  "-sEXPORTED_RUNTIME_METHODS=['UTF8ToString','stringToUTF8']")
set_target_properties(currency_core PROPERTIES
  OUTPUT_NAME "currency_core"
  SUFFIX ".js")
```

Build:

```bash
emcmake cmake -S . -B build-wasm -DCMAKE_BUILD_TYPE=Release -DBUILD_SERVER=OFF -DBUILD_TESTS=OFF
cmake --build build-wasm
# artifacts: build-wasm/wasm/currency_core.js + currency_core.wasm
```

## 5.3 Browser Loader (frontend side, consumed by doc 06's api.js)

Copy artifacts into `frontend/wasm/` during dev/deploy:

```bash
mkdir -p frontend/wasm && cp build-wasm/wasm/currency_core.* frontend/wasm/
```

Loader contract used by `api.js`:

```javascript
// <script src="wasm/currency_core.js"></script> is included conditionally by config.MODE === "wasm"
export async function initWasm(fetchCsvText) {
  const mod = await CurrencyCore();                    // instantiates + downloads .wasm
  const meta = JSON.parse(mod.loadDataset(await fetchCsvText));
  if (meta.error) throw new Error(meta.error.message);
  return wrapModule(mod);                              // exposes convert/historical/stats/movingAverage
}
```

Notes:
- Fetch the CSV with plain `fetch("data/exchange_rates.csv")` — relative path works on Pages.
- Show parse progress state while `loadDataset` runs (a 10 MB parse can block ~1–3 s).
- `currency_core.js` must be served as classic script (not `type="module"`) under MODULARIZE.

## 5.4 Parity Testing (FR-B3) — Node golden test

`scripts/parity_test.mjs`: loads `parity_seeds.json` (generated in doc 03 §3.5), runs each case through **both** transports, asserts byte-equality:

```javascript
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const CurrencyCore = require("../build-wasm/wasm/currency_core.js");

const seeds = JSON.parse((await import("node:fs/promises"))
  .readFile("scripts/fixtures/parity_seeds.json", "utf8"));

const mod = await CurrencyCore();
mod.loadDataset(seeds.csvText);

let pass = 0;
for (const s of seeds.cases) {
  const wasmOut = mod.convert(s.from, s.to, s.amount, s.date);
  const restOut = await fetch(`${seeds.restBase}/api/convert?from=${s.from}&to=${s.to}` +
    `&amount=${s.amount}&date=${s.date}`).then(r => r.text());
  if (wasmOut !== restOut) { console.error("MISMATCH", s, wasmOut, restOut); process.exit(1); }
  pass++;
}
console.log(`parity: ${pass}/${pass} cases identical`);
```

Run with native server up on :8080:

```bash
node scripts/parity_test.mjs
```

Byte-equality depends on the shared serializers + round6 rule from doc 04 — if these diverge, fix the serializer, not the test.

## 5.5 Known Pitfalls

| Pitfall | Fix |
|---------|-----|
| `memory access out of bounds` on big CSV | Confirm `ALLOW_MEMORY_GROWTH`; enforce ≤ 10 MB dataset budget |
| Module loads but functions missing | `-sMODULARIZE` + EXPORT_NAME spelling; check `Object.keys(CurrencyCore)` |
| Different float formatting vs REST | Both sides must go through the same `round6`; never rely on default `dump()` floats |
| Slow first parse in browser | Parse inside `requestIdleCallback` after first paint; show skeleton UI |
| `.wasm` MIME wrong locally | Serve via `python3 -m http.server` or currency_server — not `file://` |

## ✅ Exit Checklist

- [ ] WASM build succeeds with pinned emsdk; artifacts land in `frontend/wasm/`
- [ ] All 5 exports callable from browser console; error objects match REST shape
- [ ] `node scripts/parity_test.mjs` reports N/N identical against running server
- [ ] Sample page loads dataset over HTTP and renders `/api/meta`-equivalent info
- [ ] Commits: `feat(wasm): embind bindings`, `test: rest/wasm parity harness`
