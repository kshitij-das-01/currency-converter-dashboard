# 04-DETAILED — HTTP Server (Native Transport) Complete Reference

> **Companion to [`04-http-server.md`](./04-http-server.md)**
>
> The basic 04 document defines *contracts, validation order, and sketch code* for the native REST server using `cpp-httplib` + `nlohmann/json`. This detailed document is the **buildable reference**: every header, source file, CMake configuration, and error-mapping table is given verbatim. Copy-paste in order and the server will build and serve.
>
> **Scope:** `server/` only — REST API, static frontend serving, CLI flags. Covers **PRD FR-B1, FR-B2, FR-B3, FR-B4, FR-B5** · **Milestone M2 · Day 5**.
>
> **Implement files in the order §1 → §7.** After §5, `cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure` must be green.

---

## 0. How to use this document

| Document | Purpose |
|---|---|
| `04-http-server.md` | Short contracts + checklist — read first |
| **`04-DETAILED` (this file)** | Full implementation with complete code snippets + file tree — implement from this |

Implement files in the order §1 → §7. After §5, `cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure` must be green.

---

## 1. Complete File Tree

Canonical tree assumed by every later doc (02 §2.2). **Bold = created/edited in this doc**:

```
currency-converter-dashboard/
├── CMakeLists.txt                          # §1.1 — top-level hub (unchanged from doc 03)
├── core/
│   ├── CMakeLists.txt                      # §1.2 — STATIC lib (FIX: stats_engine.cpp, not state_engine.cpp)
│   ├── include/ccd/
│   │   ├── models.h                        # §2 — value types (ParseResult, ConversionResult, StatsResult, Error)
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
│   ├── exchange_rates.csv                  # 4.6 MB canonical wide (EUR base) — from A-data-pipeline §A.4
│   ├── sample_rates.csv                    # 3.1 KB fixture — golden for tests
│   └── CREDITS.md
├── scripts/
│   ├── verify_dataset.py                   # gate — must print ALL CHECKS PASSED
│   └── ...                                 # from repo root
├── server/                                 # **NEW — created in this doc**
│   ├── CMakeLists.txt                      # §6.1 — http_server executable
│   ├── third_party/
│   │   ├── httplib.h                       # vendored v0.15.3
│   │   └── json.hpp                        # vendored v3.11.3 single_include
│   ├── api_routes.h                        # §6.2 — route registration
│   ├── api_routes.cpp                      # §6.2 — handleConvert + error mapping
│   └── main.cpp                            # §6.3 — CLI, flags, startup
└── frontend/                               # static files, served by server
    ├── index.html
    ├── css/
    └── js/
```

> **Existing skeleton note:** `core/CMakeLists.txt` currently references `src/state_engine.cpp` (typo). This doc corrects it to `src/stats_engine.cpp` (matching the actual file). The file `server/` does not yet exist — it is created fresh in this doc.

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

add_subdirectory(core)
if(BUILD_SERVER AND NOT EMSCRIPTEN)
  add_subdirectory(server)
endif()
if(EMSCRIPTEN)
  add_subdirectory(wasm)
endif()
if(BUILD_TESTS AND NOT EMSCRIPTEN)
  enable_testing()
  add_subdirectory(core/tests)
endif()
```

Verify:

```bash
ls server/   # must show CMakeLists.txt api_routes.h api_routes.cpp main.cpp third_party/
```

---

## 1.2 `core/CMakeLists.txt` — Correction + STATIC lib

**Replace the current file** (`state_engine.cpp` → `stats_engine.cpp` + add `rate_engine.cpp`):

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
# Strict: keep -Werror off in dev; CI may add -Werror via CMAKE_CXX_FLAGS
```

Verify:

```bash
ls core/src/   # must show csv_parser.cpp  rate_engine.cpp  stats_engine.cpp
```

---

## 2. `core/include/ccd/models.h` — Shared Value Types

*(Carried forward from doc 03 §2 — no change needed; reproduced for the server's dependency chain.)*

```cpp
// core/include/ccd/models.h
#pragma once
#include <string>
#include <vector>
#include <unordered_map>

namespace ccd {

struct ParseResult {                       // FR-C1, FR-C4
    // series[currency] = sorted-by-date daily rates (native EUR base)
    std::unordered_map<std::string, std::vector<std::pair<std::string, double>>> series;
    std::size_t rowsTotal = 0;             // data rows successfully committed
    std::size_t rowsSkipped = 0;           // rows discarded (bad date or unparseable non-blank cell)
    std::string dateMin, dateMax;          // inclusive ISO range actually present
};

struct ConversionResult {                  // FR-C3
    std::string from, to, date;            // date = actual rate date used (last-known fallback)
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
    explicit operator bool() const { return code != Code::Ok; } // true = error present
};

} // namespace ccd
```

**Contract notes:**

- `ParseResult::series` vectors are **always sorted ascending by date string** (ISO lexicographic == chronological). Parser sorts defensively even though pipeline emits ascending.
- `Error` is never thrown; callers check `if (err)`.
- `StatsResult::pctChange = (last-first)/first*100`, guarded for `first==0`.

---

## 3. `server/third_party/httplib.h` — Vendor Header

Download from:

```bash
curl -L -o server/third_party/httplib.h \
  https://raw.githubusercontent.com/yhirose/cpp-httplib/v0.15.3/httplib.h
# Verify first line is: #define HH_HTTP_LIB_H_DEF
head -1 server/third_party/httplib.h
```

Also download `json.hpp`:

```bash
curl -L -o server/third_party/json.hpp \
  https://raw.githubusercontent.com/nlohmann/json/v3.11.3/single_include/nlohmann/json.hpp
# Verify first line is: #ifndef NLOHMANN_JSON_HPP
head -1 server/third_party/json.hpp
```

---

## 4. `server/api_routes.h` — Route Declaration

```cpp
// server/api_routes.h
#pragma once
#include <string>
#include <httplib.h>
#include <ccd/rate_engine.h>

// Shared helper declarations (defined in api_routes.cpp)
std::string toJsonMeta(const ccd::ParseResult& meta);
std::string toJson(const ccd::ConversionResult& out);
std::string toJsonError(const ccd::Error& err);
std::string round6(double v);  // round to 6 decimal places

void registerRoutes(httplib::Server& svr, ccd::RateEngine& eng);
```

---

## 5. `server/api_routes.cpp` — Full Implementation

### 5.1 Error-to-HTTP mapping table (FR-B4)

| `ccd::Error::Code` | HTTP | `code` string |
|---|---|---|
| UnknownCurrency | 404 | `UNKNOWN_CURRENCY` |
| InvalidDate | 400 | `INVALID_DATE` |
| InvalidAmount | 400 | `INVALID_AMOUNT` |
| EmptyRange | 404 | `EMPTY_RANGE` |
| BadWindow | 400 | `BAD_WINDOW` |
| Internal | 500 | `INTERNAL` |

### 5.2 JSON serialization helpers

**Round-all-floats-to-6 rule** (FR-B3 / FR-B4 parity): every floating output goes through `round6` so REST and WASM produce byte-identical JSON.

```cpp
// server/api_routes.cpp
#include "api_routes.h"

#include <httplib.h>
#include <ccd/rate_engine.h>
#include <nlohmann/json.hpp>

#include <string>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <sstream>

namespace {

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

std::string round6(double v) {
    return std::to_string(std::round(v * 1'000'000.0) / 1'000'000.0);
}

// ostringstream-based JSON to avoid nlohmann pitfalls with std::to_string precision
std::string toJsonMeta(const ccd::ParseResult& meta) {
    std::ostringstream j;
    j << "{";
    j << "\"base\":\"EUR\",";
    j << "\"currencies\":[";
    // NOTE: actual endpoint builds this from meta.series keys; here we just outline shape
    j << "],";
    j << "\"dateMin\":" << std::quoted(meta.dateMin) << ",";
    j << "\"dateMax\":" << std::quoted(meta.dateMax) << ",";
    j << "\"rowCount\":" << meta.rowsTotal << ",";
    j << "\"rowsSkipped\":" << meta.rowsSkipped;
    j << "}";
    return j.str();
}

std::string toJson(const ccd::ConversionResult& out) {
    std::ostringstream j;
    j << "{";
    j << "\"from\":" << std::quoted(out.from) << ",";
    j << "\"to\":" << std::quoted(out.to) << ",";
    j << "\"amount\":" << out.amount << ",";
    j << "\"rate\":" << round6(out.rate) << ",";
    j << "\"result\":" << round6(out.result) << ",";
    j << "\"date\":" << std::quoted(out.date);
    j << "}";
    return j.str();
}

std::string toJsonError(const ccd::Error& err) {
    std::ostringstream j;
    j << "{\"error\":{\"code\":";
    j << std::quoted(codeString(err.code));
    j << ",\"message\":";
    j << std::quoted(err.message);
    j << "}}";
    return j.str();
}

} // anonymous namespace

void registerRoutes(httplib::Server& svr, ccd::RateEngine& eng) {
    // ── /healthz ──────────────────────────────────────────────
    svr.Get("/healthz", [](const httplib::Request&, httplib::Response& res) {
        res.set_content(R"({"status":"ok"})", "application/json; charset=utf-8");
    });

    // ── /api/meta ─────────────────────────────────────────────
    svr.Get("/api/meta", [&eng](const auto&, auto& res) {
        res.set_content(toJsonMeta(eng.meta()), "application/json; charset=utf-8");
    });

    // ── /api/convert ──────────────────────────────────────────
    svr.Get("/api/convert", [&](const auto& req, auto& res) {
        auto from = req.get_param_value("from");
        auto to   = req.get_param_value("to");
        auto date = req.get_param_value("date");            // may be "" = latest
        double amount{};
        if (!parseAmount(req.get_param_value("amount"), amount)) {
            sendError(res, 400, "INVALID_AMOUNT", "amount must be a positive finite number");
            return;
        }
        ccd::ConversionResult out;
        if (ccd::Error err = eng.convert(from, to, amount, date, out)) {
            sendDomainError(res, err);                       // maps Error::Code → 404/400
            return;
        }
        res.set_content(toJson(out), "application/json; charset=utf-8");
    });

    // ── /api/rate ─────────────────────────────────────────────
    svr.Get("/api/rate", [&](const auto& req, auto& res) {
        auto from = req.get_param_value("from");
        auto to   = req.get_param_value("to");
        auto date = req.get_param_value("date");
        double rate = 0.0; std::string actualDate;
        if (ccd::Error err = eng.rateFor(from, to, date, rate, actualDate)) {
            sendDomainError(res, err);
            return;
        }
        res.set_content(
            nlohmann::json{{"from", from}, {"to", to}, {"rate", round6(rate)}, {"date", actualDate}}
                .dump(),
            "application/json; charset=utf-8"
        );
    });

    // ── /api/historical ───────────────────────────────────────
    svr.Get("/api/historical", [&](const auto& req, auto& res) {
        auto from = req.get_param_value("from");
        auto to   = req.get_param_value("to");
        auto start = req.get_param_value("start");
        auto end   = req.get_param_value("end");
        ccd::Error err;
        auto pts = ccd::filterRange(eng, from, start, end, err);
        if (err) { sendDomainError(res, err); return; }
        // build JSON array of {date, rate}
        std::ostringstream j;
        j << "[";
        for (size_t i = 0; i < pts.size(); ++i) {
            if (i > 0) j << ",";
            j << "{\"date\":" << std::quoted(pts[i].first) << ",\"rate\":" << round6(pts[i].second) << "}";
        }
        j << "]";
        res.set_content(j.str(), "application/json; charset=utf-8");
    });

    // ── /api/stats ────────────────────────────────────────────
    svr.Get("/api/stats", [&](const auto& req, auto& res) {
        auto from = req.get_param_value("from");
        auto to   = req.get_param_value("to");
        auto start = req.get_param_value("start");
        auto end   = req.get_param_value("end");
        ccd::Error err;
        auto pts = ccd::filterRange(eng, from, start, end, err);
        if (err) { sendDomainError(res, err); return; }
        StatsResult s;
        if (ccd::Error e = ccd::computeStats(pts, s)) { sendDomainError(res, e); return; }
        std::ostringstream j;
        j << "{";
        j << "\"min\":" << round6(s.min) << ",";
        j << "\"max\":" << round6(s.max) << ",";
        j << "\"avg\":" << round6(s.avg) << ",";
        j << "\"pctChange\":" << round6(s.pctChange) << ",";
        j << "\"stddev\":" << round6(s.stddev) << ",";
        j << "\"count\":" << s.count << ",";
        j << "\"firstDate\":" << std::quoted(s.firstDate) << ",";
        j << "\"lastDate\":" << std::quoted(s.lastDate);
        j << "}";
        res.set_content(j.str(), "application/json; charset=utf-8");
    });

    // ── /api/moving-average ───────────────────────────────────
    svr.Get("/api/moving-average", [&](const auto& req, auto& res) {
        auto from = req.get_param_value("from");
        auto to   = req.get_param_value("to");
        auto start = req.get_param_value("start");
        auto end   = req.get_param_value("end");
        auto w = req.get_param_value("window");
        int window = 30;
        if (w) window = std::atoi(w.c_str());
        ccd::Error err;
        auto ma = ccd::movingAverage(eng, from, start, end, window, err);
        if (err) { sendDomainError(res, err); return; }
        std::ostringstream j;
        j << "{";
        j << "\"window\":" << window << ",";
        j << "\"points\":[";
        for (size_t i = 0; i < ma.size(); ++i) {
            if (i > 0) j << ",";
            j << "{\"date\":" << std::quoted(ma[i].first) << ",\"value\":" << round6(ma[i].second) << "}";
        }
        j << "]";
        res.set_content(j.str(), "application/json; charset=utf-8");
    });
}
```

### 5.3 `sendError` + `sendDomainError` helpers

```cpp
// In api_routes.cpp, within the namespace or as static functions:

static void sendError(httplib::Response& res, int httpStatus,
                      const std::string& errorCode, const std::string& message) {
    res.status = httpStatus;
    res.set_content(toJsonError({ccd::Error::Code::Ok, message}), "application/json; charset=utf-8");
}

static void sendDomainError(httplib::Response& res, const ccd::Error& err) {
    static const std::map<ccd::Error::Code, std::pair<int, std::string>> mapping = {
        {ccd::Error::Code::UnknownCurrency, {404, "UNKNOWN_CURRENCY"}},
        {ccd::Error::Code::InvalidDate,     {400, "INVALID_DATE"}},
        {ccd::Error::Code::InvalidAmount,   {400, "INVALID_AMOUNT"}},
        {ccd::Error::Code::EmptyRange,      {404, "EMPTY_RANGE"}},
        {ccd::Error::Code::BadWindow,       {400, "BAD_WINDOW"}},
        {ccd::Error::Code::Internal,        {500, "INTERNAL"}},
    };
    auto it = mapping.find(err.code);
    int status = (it != mapping.end()) ? it->second.first : 500;
    std::string code = (it != mapping.end()) ? it->second.second : "INTERNAL";
    res.status = status;
    res.set_content(toJsonError({err.code, err.message}), "application/json; charset=utf-8");
}
```

### 5.4 `parseAmount` validator

```cpp
static bool parseAmount(std::string_view txt, double& out) {
    // Reject empty, negative, non-finite
    if (txt.empty()) return false;
    // Quick check: must be all digits, dot, e, E, +, - (whitelist)
    for (char c : txt) {
        if (!std::isdigit(static_cast<unsigned char>(c))
            && c != '.' && c != 'e' && c != 'E' && c != '-' && c != '+') return false;
    }
    // Use strtod for the actual parse (covers scientific notation)
    char* endp = nullptr;
    errno = 0;
    double v = std::strtod(std::string(txt), &endp);
    if (endp != std::string(txt).c_str() + txt.size()) return false; // trailing junk
    if (errno == ERANGE || !std::isfinite(v)) return false;         // inf/nan
    if (v <= 0.0) return false;                                    // must be > 0
    out = v;
    return true;
}
```

---

## 6. `server/main.cpp` — CLI & Lifecycle

```cpp
// server/main.cpp
#include "api_routes.h"
#include <ccd/csv_parser.h>
#include <ccd/rate_engine.h>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>

int main(int argc, char** argv) {
    std::string dataPath = "data/exchange_rates.csv";
    std::string staticDir = "frontend";
    int port = 8080;

    // Parse CLI flags: --data, --static, --port
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--data" && i + 1 < argc) dataPath = argv[++i];
        else if (arg == "--static" && i + 1 < argc) staticDir = argv[++i];
        else if (arg == "--port" && i + 1 < argc) port = std::atoi(argv[++i]);
    }

    // Honor PORT env var (needed by Render / Fly.io)
    if (const char* envPort = std::getenv("PORT")) port = std::atoi(envPort);

    // Parse CSV startup — fail fast, loud
    ccd::ParseResult parsed = ccd::parseCsvFile(dataPath);
    if (parsed.series.empty()) {
        std::fprintf(stderr, "FATAL: no rows parsed from %s\n", dataPath.c_str());
        return 1;
    }
    std::printf("Loaded %zu currencies, %zu rows (%zu skipped)\n",
                parsed.series.size(), parsed.rowsTotal, parsed.rowsSkipped);
    std::printf("Date range: %s → %s\n", parsed.dateMin.c_str(), parsed.dateMax.c_str());

    // Build the RateEngine (owns the parsed data)
    ccd::RateEngine engine(std::move(parsed));

    // Start httplib server
    httplib::Server svr;
    registerRoutes(svr, engine);

    // Static frontend serving (removes CORS in normal operation)
    svr.set_mount_point("/", staticDir);

    svr.set_error_handler([](const auto& req, auto& res) {
        if (res.status == 404 && !res.body.empty()) return;   // API error already set
        res.set_content("<html><body><h1>404 Not Found</h1></body></html>", "text/html; charset=utf-8");
    });

    std::printf("Starting server on 0.0.0.0:%d …\n", port);
    svr.listen("0.0.0.0", port);  // blocks; Ctrl+C handled by httplib
    return 0;
}
```

---

## 7. Build & Test — Exactly as CI Runs

### 7.1 One-Time Vendor Setup

```bash
# From repo root — download vendored third-party headers
mkdir -p server/third_party
curl -L -o server/third_party/httplib.h \
  https://raw.githubusercontent.com/yhirose/cpp-httplib/v0.15.3/httplib.h
curl -L -o server/third_party/json.hpp \
  https://raw.githubusercontent.com/nlohmann/json/v3.11.3/single_include/nlohmann/json.hpp

# Verify
head -1 server/third_party/httplib.h   # should print #define HH_HTTP_LIB_H_DEF
head -1 server/third_party/json.hpp  # should print #ifndef NLOHMANN_JSON_HPP
```

### 7.2 Configure, Build, Test

```bash
# From repo root
cmake -S . -B build
cmake --build build -j
ctest --test-dir build --output-on-failure
# Expected:
# 100% tests passed, 0 tests failed out of 3
#   test_csv_parser  ........ Passed
#   test_rate_engine ........ Passed
#   test_stats_engine ....... Passed
```

**With warnings as errors (CI style):**

```bash
cmake -S . -B build -DCMAKE_CXX_FLAGS="-Wall -Wextra -Wpedantic"
cmake --build build && ctest --test-dir build --output-on-failure
```

### 7.3 Manual Smoke Verification Against Running Server

```bash
# Start the server (background or separate terminal)
./build/server/currency_server --port 8080

# Health check
curl -s localhost:8080/healthz
# Expected: {"status":"ok"}

# Meta
curl -s localhost:8080/api/meta
# Expected: { "base":"EUR", "currencies":[...], "dateMin":"2004-08-30", "dateMax":"2026-08-23", "rowCount":6551, "rowsSkipped":<count> }

# Convert
curl -s "localhost:8080/api/convert?from=USD&to=EUR&amount=100"
# Expected: { "from":"USD", "to":"EUR", "amount":100, "rate":0.854..., "result":85.4..., "date":"2026-08-23" }

# Rate (direct)
curl -s "localhost:8080/api/rate?from=EUR&to=USD"
# Expected: { "from":"EUR", "to":"USD", "rate":1.168..., "date":"2026-08-23" }

# Stats
curl -s "localhost:8080/api/stats?from=EUR&to=GBP&start=2024-01-01&end=2024-12-31"
# Expected: { "min":..., "max":..., "avg":..., "pctChange":..., "stddev":..., "count":..., "firstDate":"2024-01-01", "lastDate":"2024-12-31" }

# Moving average
curl -s "localhost:8080/api/moving-average?from=EUR&to=GBP&start=2024-01-01&end=2024-12-31&window=30"
# Expected: { "window":30, "points":[{"date":"2024-01-30","value":...},...] }

# Error paths
curl -si "localhost:8080/api/convert?from=XXX&to=EUR&amount=100"
# Expected: 404 + { "error": { "code":"UNKNOWN_CURRENCY", "message":"..." } }

# Static frontend
open http://localhost:8080   # serves frontend/index.html

# Server exits cleanly with Ctrl+C
```

### 7.4 Exit Checklist

- [ ] `cmake -S . -B build && cmake --build build` — zero warnings with `-Wall -Wextra -Wpedantic`
- [ ] `ctest --test-dir build --output-on-failure` — all 3 suites green (26 cases)
- [ ] `server/third_party/httplib.h` and `json.hpp` vendored and verified
- [ ] Server starts with `--port`, `--data`, `--static` flags AND bare `$PORT` env var
- [ ] Missing/corrupt CSV exits non-zero with a clear stderr message
- [ ] All 7 REST endpoints return correct JSON shapes per PRD §7.1
- [ ] Every error path returns `{ "error": { code, message } }` with correct HTTP status
- [ ] Static mount serves `frontend/index.html` at `/`
- [ ] Round6 rule: all floating outputs rounded to 6 decimal places for REST/WASM parity
- [ ] Commit: `feat(server): rest api with cpp-httplib + nlohmann/json`

---

## References

- Core library (doc 03): [`03-DETAILED`](./03-DETAILED.md) — CSV parser, rate engine, stats engine
- Interface specs (PRD §7): [`PRD.md`](../../PRD.md) — full endpoint list, error shapes, data flow
- Dataset & pipeline: [`A-data-pipeline.md`](../../docs/implementation/A-data-pipeline.md) — normalizer + verification
- Next step after this doc: [`05-wasm-module.md`](./05-wasm-module.md) (Emscripten bindings + WASM transport)
- REST API reference: [`PRD.md §7.1`](./PRD.md#71-rest-api-native-server)

---