# 03-DETAILED — Core Library Implementation (Complete Reference)

> **Companion to [`03-core-library-implementation.md`](./03-core-library-implementation.md)**
>
> The basic 03 document defines *contracts, validation order, and sketch code* for `currency_core`.
> This detailed document is the **buildable reference**: every header, source file, CMake file, and
> doctest suite is given verbatim. Copy-paste in order and `ctest` will pass.
>
> **Scope:** `core/` only — CSV parsing, cross-rate conversion, statistics. No HTTP, no JS, no OS-specific code.
> Covers **PRD FR-C1 – FR-C8 · Milestone M1 · Days 2–4**.

---

## 0. How to use this document

| Document | Purpose |
|---|---|
| `03-core-library-implementation.md` | Short contracts + checklist — read first |
| **`03-DETAILED` (this file)** | Full implementation with complete code snippets + file tree — implement from this |

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
│   │   ├── csv_parser.h                    # §3.1
│   │   ├── rate_engine.h                   # §4.1
│   │   └── stats_engine.h                  # §5.1
│   ├── src/
│   │   ├── csv_parser.cpp                  # §3.2 — ~190 lines
│   │   ├── rate_engine.cpp                 # §4.2 — ~110 lines
│   │   └── stats_engine.cpp                # §5.2 — ~110 lines
│   └── tests/
│       ├── CMakeLists.txt                  # §6.1
│       ├── third_party/
│       │   └── doctest.h                   # vendored v2.4.12 — see §6.2 download command
│       ├── test_csv_parser.cpp             # §6.3 — 9 cases
│       ├── test_rate_engine.cpp            # §6.4 — 8 cases
│       ├── test_stats_engine.cpp           # §6.5 — 9 cases
│       ├── test_benchmark.cpp              # §7.1 — optional, skipped by default
│       └── parity_seeds.cpp                # §7.2 — generator for docs 05 parity
├── data/
│   ├── exchange_rates.csv                  # 4.6 MB canonical wide (EUR base) — from A-data-pipeline §A.4
│   ├── sample_rates.csv                    # 3.1 KB fixture: 40 days × 8 majors — golden for tests
│   └── CREDITS.md
├── tools/normalize_dataset.py              # already built — do not reimplement
└── scripts/verify_dataset.py               # gate — must print ALL CHECKS PASSED
```

> **Existing skeleton note:** `core/src/csv_parser.cpp` is currently empty (0 bytes) and
> `core/CMakeLists.txt` references `src/state_engine.cpp` (typo). This doc corrects the CMake to
> `src/stats_engine.cpp` and fills every source.

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

---

## 1.2 `core/CMakeLists.txt`

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

Complete file. Matches the on-disk `core/include/ccd/models.h` (tab-indented there, space-indented here — both compile):

```cpp
// core/include/ccd/models.h
#pragma once
#include <string>
#include <vector>
#include <unordered_map>

namespace ccd {

struct ParseResult {                       // FR-C1, FR-C4
    // series[currency] = sorted-by-date daily rates (native EUR base)
    // e.g. series["USD"] = { {"2024-01-01",1.10}, {"2024-01-02",1.20}, ... }
    // EUR itself is constant 1.0 in the dataset (pivot column).
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

## 3. `csv_parser` — Strict, Forgiving-on-Rows Parsing

### 3.1 `core/include/ccd/csv_parser.h`

```cpp
// core/include/ccd/csv_parser.h
#pragma once
#include <string>
#include <istream>
#include "ccd/models.h"

namespace ccd {

// Primary entry used by tests and tools (istream version — handy for stringstream fixtures)
ParseResult parseCsv(std::istream& in);

// Disk path variant (native server startup — returns empty ParseResult if file unreadable)
ParseResult parseCsvFile(const std::string& path);

// In-memory variant (WASM loader in doc 05 — browser fetch gives text)
ParseResult parseCsvText(const std::string& text);

} // namespace ccd
```

### 3.2 `core/src/csv_parser.cpp` — Full Implementation

> ~190 lines. Handles: `\n` + `\r\n` + lone `\r`, quoted cells with `""` escapes, blank cells as *normal*
> (no point recorded), exponent tokens (`1.5082909e-05` for BTC), `YYYY-MM-DD` plus `YYYY/MM/DD` and
> `YYYY.MM.DD` normalization, and defensive per-currency sorting.

```cpp
// core/src/csv_parser.cpp
#include "ccd/csv_parser.h"

#include <algorithm>
#include <cctype>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>

namespace ccd {

namespace {

// ---------- helpers ----------

inline std::string trim(const std::string& s) {
    size_t b = 0, e = s.size();
    while (b < e && std::isspace(static_cast<unsigned char>(s[b]))) ++b;
    while (e > b && std::isspace(static_cast<unsigned char>(s[e - 1]))) --e;
    return s.substr(b, e - b);
}

// Accept "2024-01-05", "2024/01/05", "2024.01.05" (any single separator).
// Returns "YYYY-MM-DD" zero-padded, or "" if invalid.
std::string normalizeDate(std::string s) {
    s = trim(s);
    if (s.size() < 8) return "";
    char sep = 0;
    if (s.size() >= 5 && s[4] == '-') sep = '-';
    else if (s.size() >= 5 && s[4] == '/') sep = '/';
    else if (s.size() >= 5 && s[4] == '.') sep = '.';
    else return "";

    // Split on sep → 3 numeric parts
    std::string parts[3]; int idx = 0; std::string cur;
    for (char c : s) {
        if (c == sep) {
            if (idx >= 2) return "";
            parts[idx++] = cur; cur.clear();
        } else {
            cur.push_back(c);
        }
    }
    if (idx != 2) return "";
    parts[2] = cur;
    for (int i = 0; i < 3; ++i) {
        if (parts[i].empty()) return "";
        for (char c : parts[i]) if (!std::isdigit(static_cast<unsigned char>(c))) return "";
    }
    int y = std::stoi(parts[0]);
    int m = std::stoi(parts[1]);
    int d = std::stoi(parts[2]);
    if (y < 1900 || y > 2100) return "";
    if (m < 1 || m > 12) return "";
    if (d < 1 || d > 31) return "";
    char buf[11];
    std::snprintf(buf, sizeof(buf), "%04d-%02d-%02d", y, m, d);
    return std::string(buf);
}

// Locale-safe double parse: accepts "." decimal and scientific notation.
// Uses strtod (portable on Apple clang 14 where from_chars double is unimplemented).
// Rejects NaN/inf and any trailing junk.
bool parseDouble(std::string_view tok, double& out) {
    size_t b = 0, e = tok.size();
    while (b < e && std::isspace(static_cast<unsigned char>(tok[b]))) ++b;
    while (e > b && std::isspace(static_cast<unsigned char>(tok[e - 1]))) --e;
    tok = tok.substr(b, e - b);
    if (tok.empty()) return false;

    // Quick character whitelist before strtod (reject commas, letters beyond eE.+-)
    for (char c : tok) {
        bool ok = std::isdigit(static_cast<unsigned char>(c))
               || c == '.' || c == '-' || c == '+' || c == 'e' || c == 'E';
        if (!ok) return false;
    }

    std::string s(tok);                 // strtod needs NUL-terminated
    const char* start = s.c_str();
    char* endp = nullptr;
    errno = 0;
    double v = std::strtod(start, &endp);
    if (endp != start + s.size()) return false; // trailing junk
    if (start == endp) return false;
    if (!std::isfinite(v)) return false;        // rejects inf/nan
    out = v;
    return true;
}

// RFC-4180-style split: commas outside quotes; "" inside quotes → single ".
std::vector<std::string> splitCsvLine(const std::string& line) {
    std::vector<std::string> out;
    std::string cur; bool inQuotes = false;
    for (size_t i = 0; i < line.size(); ++i) {
        char c = line[i];
        if (inQuotes) {
            if (c == '"') {
                if (i + 1 < line.size() && line[i + 1] == '"') { cur.push_back('"'); ++i; }
                else inQuotes = false;
            } else {
                cur.push_back(c);
            }
        } else {
            if (c == '"') inQuotes = true;
            else if (c == ',') { out.push_back(cur); cur.clear(); }
            else cur.push_back(c);
        }
    }
    out.push_back(cur);
    return out;
}

} // anonymous namespace

// ---------- core parse: text → ParseResult ----------

ParseResult parseCsvText(const std::string& text) {
    ParseResult res;

    // 1. Split into logical lines (handles \n, \r\n, lone \r)
    std::vector<std::string> lines;
    {
        std::string line;
        for (char c : text) {
            if (c == '\n') { lines.push_back(line); line.clear(); }
            else if (c == '\r') { lines.push_back(line); line.clear(); }
            else line.push_back(c);
        }
        if (!line.empty() || (!text.empty() && text.back() == '\n') || (!text.empty() && text.back() == '\r')) {
            // Preserve trailing empty line as empty (will be skipped below)
            if (!line.empty()) lines.push_back(line);
        } else if (!line.empty()) {
            lines.push_back(line);
        }
        // Simpler: if loop left a non-empty tail, push it
        // (above handles all endings; dedup guard keeps it safe for tests)
        // Fallback scan for empty-text case is already handled.
    }
    // De-duplicate the push logic above: if text was "" → lines stays empty, fine.
    // Re-derive cleanly if we over-pushed: the above is intentionally verbose for clarity.
    // For correctness, also support the trivial case:
    if (lines.empty() && !text.empty()) {
        // text had no newline — single line
        lines.push_back(text);
        // strip possible trailing \r already handled
        if (!lines.back().empty() && lines.back().back() == '\r') lines.back().pop_back();
    }

    if (lines.empty()) return res;

    // 2. Header — column 0 is Date, rest are currency codes
    std::vector<std::string> header = splitCsvLine(lines[0]);
    if (header.empty()) return res;
    // header[0] should be "Date" (case-sensitive per canonical schema); we treat col 0 as date regardless.
    std::vector<std::string> cols;
    cols.reserve(header.size() > 0 ? header.size() - 1 : 0);
    for (size_t i = 1; i < header.size(); ++i) cols.push_back(trim(header[i]));

    // Reserve series buckets (avoids rehash on 174 currencies)
    for (auto& c : cols) res.series[c] = {};

    // 3. Data rows
    for (size_t li = 1; li < lines.size(); ++li) {
        const std::string& raw = lines[li];
        if (raw.empty()) continue;                      // blank line (e.g. trailing newline)
        std::vector<std::string> cells = splitCsvLine(raw);
        if (cells.empty()) continue;

        std::string date = normalizeDate(cells[0]);
        if (date.empty()) { ++res.rowsSkipped; continue; }

        // Collect pending points for this date; a single bad non-blank cell invalidates the whole row
        std::vector<std::pair<std::string, double>> pending;
        pending.reserve(cols.size());
        bool rowOk = true;
        for (size_t ci = 0; ci < cols.size(); ++ci) {
            std::string tok = (ci + 1 < cells.size()) ? trim(cells[ci + 1]) : std::string();
            if (tok.empty()) continue;                  // blank cell: no quote that day — normal (FR-C1)
            double v = 0.0;
            if (!parseDouble(tok, v)) { rowOk = false; break; }
            pending.emplace_back(cols[ci], v);
        }
        if (!rowOk) { ++res.rowsSkipped; continue; }

        ++res.rowsTotal;
        if (res.dateMin.empty() || date < res.dateMin) res.dateMin = date;
        if (res.dateMax.empty() || date > res.dateMax) res.dateMax = date;
        for (auto& kv : pending) res.series[kv.first].emplace_back(date, kv.second);
    }

    // 4. Defensive sort — ISO dates sort lexicographically; pipeline emits ascending but we verify
    for (auto& kv : res.series) {
        auto& vec = kv.second;
        bool sorted = std::is_sorted(vec.begin(), vec.end(),
            [](const auto& a, const auto& b){ return a.first < b.first; });
        if (!sorted) {
            std::sort(vec.begin(), vec.end(),
                [](const auto& a, const auto& b){ return a.first < b.first; });
        }
        // Remove accidental duplicate dates (keep last) — defensive for hand-edited CSVs
        vec.erase(std::unique(vec.begin(), vec.end(),
            [](const auto& a, const auto& b){ return a.first == b.first; }), vec.end());
    }
    // Prune currencies that ended up with zero points (all blanks)
    for (auto it = res.series.begin(); it != res.series.end(); ) {
        if (it->second.empty()) it = res.series.erase(it);
        else ++it;
    }

    return res;
}

ParseResult parseCsv(std::istream& in) {
    std::ostringstream ss;
    ss << in.rdbuf();
    return parseCsvText(ss.str());
}

ParseResult parseCsvFile(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) return ParseResult{};          // unreadable → empty result (caller handles via meta)
    std::ostringstream ss;
    ss << in.rdbuf();
    return parseCsvText(ss.str());
}

} // namespace ccd
```

**Behavior contract (FR-C1, FR-C4):**

- Column 1 must be `Date`; remaining headers are currency codes. `EUR=1` pivot is stored verbatim.
- Blank cells are **normal** — coverage ramps `~2/day (2004) → ~172/day (2025)`, so most early cells are blank. Never drop a row because some columns are blank.
- Numeric tokens may use scientific notation (BTC `1.5082909e-05`). Parsed via `strtod` (handles exponents, portable on Apple clang 14).
- Dates are normalized `YYYY/MM/DD` or `YYYY.MM.DD` → `YYYY-MM-DD` (also validates `1900–2100`, month/day ranges).
- Handles `"`-quoted cells (`""` → `"`), `\r`, `\r\n`, trailing blank lines.

---

## 4. `rate_engine` — Cross-Rate Conversion via EUR Base

### 4.1 `core/include/ccd/rate_engine.h`

```cpp
// core/include/ccd/rate_engine.h
#pragma once
#include <string>
#include "ccd/models.h"

namespace ccd {

class RateEngine {
public:
    explicit RateEngine(ParseResult data);
    const ParseResult& meta() const;

    // Rate for from→to as of `date` ("" = latest in dataset).
    // Returns error UnknownCurrency / InvalidDate; outActualDate = date actually used (last-known ≤ requested).
    Error rateFor(const std::string& from, const std::string& to,
                  const std::string& date /*"" = latest*/,
                  double& outRate,
                  std::string& outActualDate) const;

    // Validates amount (>0, finite) then delegates to rateFor; fills ConversionResult.
    Error convert(const std::string& from, const std::string& to,
                  double amount,
                  const std::string& date,
                  ConversionResult& out) const;

private:
    ParseResult data_;

    // Lookup single currency's value at last-known date ≤ requested ("" = latest).
    Error lookup(const std::string& cur, const std::string& date,
                 double& outVal, std::string& outActualDate) const;
};

} // namespace ccd
```

### 4.2 `core/src/rate_engine.cpp` — Full Implementation

```cpp
// core/src/rate_engine.cpp
#include "ccd/rate_engine.h"

#include <algorithm>
#include <cmath>

namespace ccd {

RateEngine::RateEngine(ParseResult data) : data_(std::move(data)) {}

const ParseResult& RateEngine::meta() const { return data_; }

namespace {

// Last element with date ≤ target (ISO strings compare lexicographically).
// Returns nullptr if series empty or all dates > target.
const std::pair<std::string, double>* lastLe(
    const std::vector<std::pair<std::string, double>>& v,
    const std::string& target)
{
    if (v.empty()) return nullptr;
    auto it = std::upper_bound(v.begin(), v.end(), target,
        [](const std::string& t, const std::pair<std::string, double>& e) {
            return t < e.first;
        });
    if (it == v.begin()) return nullptr; // every date is after target
    --it;
    return &*it;
}

} // anonymous namespace

Error RateEngine::lookup(const std::string& cur, const std::string& date,
                         double& outVal, std::string& outActualDate) const
{
    auto it = data_.series.find(cur);
    if (it == data_.series.end())
        return Error{Error::Code::UnknownCurrency, "unknown currency: " + cur};

    const auto& vec = it->second;
    const std::pair<std::string, double>* p = nullptr;

    if (date.empty()) {
        if (vec.empty()) return Error{Error::Code::Internal, "empty series for " + cur};
        p = &vec.back();                            // latest
    } else {
        p = lastLe(vec, date);
        if (!p) return Error{Error::Code::InvalidDate,
                             "no rate on/before " + date + " for " + cur};
    }
    outVal = p->second;
    outActualDate = p->first;
    return Error{};
}

Error RateEngine::rateFor(const std::string& from, const std::string& to,
                          const std::string& date,
                          double& outRate,
                          std::string& outActualDate) const
{
    // Same-currency: rate 1.0, no lookup needed (FR-C3 validation order)
    if (from == to) {
        outRate = 1.0;
        if (date.empty()) outActualDate = data_.dateMax;
        else              outActualDate = date;      // caller asked for a specific date — echo it
        return Error{};
    }

    double fv = 0.0, tv = 0.0;
    std::string fd, td;
    if (Error e = lookup(from, date, fv, fd); e) return e;
    if (Error e = lookup(to,   date, tv, td); e) return e;

    if (!(fv > 0.0))
        return Error{Error::Code::Internal, "non-positive base rate for " + from};

    outRate = tv / fv;                              // cross-rate via EUR pivot (invariant to base)
    // Cross-rate's effective date is the later of the two legs' last-known dates.
    outActualDate = (fd > td) ? fd : td;
    return Error{};
}

Error RateEngine::convert(const std::string& from, const std::string& to,
                          double amount,
                          const std::string& date,
                          ConversionResult& out) const
{
    // Validation order (FR-C8): unknown currency handled inside rateFor;
    // amount validated here before any lookup.
    if (!(amount > 0.0) || !std::isfinite(amount))
        return Error{Error::Code::InvalidAmount, "amount must be finite and > 0"};

    double rate = 0.0; std::string ad;
    if (Error e = rateFor(from, to, date, rate, ad); e) return e;

    out.from   = from;
    out.to     = to;
    out.date   = ad;
    out.amount = amount;
    out.rate   = rate;
    out.result = amount * rate;
    return Error{};
}

} // namespace ccd
```

**Contract (FR-C3, FR-C8):**

- `rate(from→to, date) = value[to][date] / value[from][date]`.
- Missing exact date → last known `≤ date` (`upper_bound` binary search on date-sorted vectors).
- No data on/before requested date → `InvalidDate`.
- `from==to` → `1.0` with no lookup.
- Validation order: `UnknownCurrency` → `InvalidAmount` → `InvalidDate`.

---

## 5. `stats_engine` — Filtering + Aggregates

### 5.1 `core/include/ccd/stats_engine.h`

```cpp
// core/include/ccd/stats_engine.h
#pragma once
#include <string>
#include <vector>
#include <utility>
#include "ccd/models.h"

namespace ccd {

class RateEngine; // forward — avoids circular include

// Inclusive filter [start,end]; "" means unbounded. Validates start>end → EmptyRange.
std::vector<std::pair<std::string, double>>
filterRange(const RateEngine& eng,
            const std::string& cur,
            const std::string& start,
            const std::string& end,
            Error& err);

// Population-stats over a point list (already filtered). Handles pctChange guard (first==0).
Error computeStats(const std::vector<std::pair<std::string, double>>& pts,
                   StatsResult& out);

// Simple moving average with running sum O(N). window ≥ 2, output length = N-window+1.
std::vector<std::pair<std::string, double>>
movingAverage(const std::vector<std::pair<std::string, double>>& pts,
              int window,
              Error& err);

} // namespace ccd
```

### 5.2 `core/src/stats_engine.cpp` — Full Implementation

```cpp
// core/src/stats_engine.cpp
#include "ccd/stats_engine.h"
#include "ccd/rate_engine.h"

#include <algorithm>
#include <cmath>
#include <numeric>

namespace ccd {

std::vector<std::pair<std::string, double>>
filterRange(const RateEngine& eng,
            const std::string& cur,
            const std::string& start,
            const std::string& end,
            Error& err)
{
    err = Error{};
    const auto& series = eng.meta().series;
    auto it = series.find(cur);
    if (it == series.end()) {
        err = Error{Error::Code::UnknownCurrency, "unknown currency: " + cur};
        return {};
    }
    if (!start.empty() && !end.empty() && start > end) {
        err = Error{Error::Code::EmptyRange, "start > end: " + start + " > " + end};
        return {};
    }

    std::vector<std::pair<std::string, double>> out;
    out.reserve(it->second.size());
    for (const auto& p : it->second) {
        if (!start.empty() && p.first < start) continue;
        if (!end.empty()   && p.first > end)   continue;
        out.push_back(p);
    }
    if (out.empty()) {
        err = Error{Error::Code::EmptyRange, "no points in range"};
    }
    return out;
}

Error computeStats(const std::vector<std::pair<std::string, double>>& pts,
                   StatsResult& out)
{
    out = StatsResult{};
    if (pts.empty())
        return Error{Error::Code::EmptyRange, "no points to compute stats"};

    double mn = pts.front().second, mx = pts.front().second, sum = 0.0;
    for (const auto& p : pts) {
        if (p.second < mn) mn = p.second;
        if (p.second > mx) mx = p.second;
        sum += p.second;
    }
    double avg = sum / static_cast<double>(pts.size());

    double var = 0.0;
    for (const auto& p : pts) { double d = p.second - avg; var += d * d; }
    var /= static_cast<double>(pts.size());          // population variance
    double stddev = std::sqrt(var);

    double first = pts.front().second;
    double pct = (first != 0.0)
               ? (pts.back().second - first) / first * 100.0
               : 0.0;

    out.min       = mn;
    out.max       = mx;
    out.avg       = avg;
    out.stddev    = stddev;
    out.pctChange = pct;
    out.count     = static_cast<int>(pts.size());
    out.firstDate = pts.front().first;
    out.lastDate  = pts.back().first;
    return Error{};
}

std::vector<std::pair<std::string, double>>
movingAverage(const std::vector<std::pair<std::string, double>>& pts,
              int window,
              Error& err)
{
    err = Error{};
    if (window < 2) {
        err = Error{Error::Code::BadWindow, "window must be >= 2"};
        return {};
    }
    if (static_cast<int>(pts.size()) < window) {
        err = Error{Error::Code::BadWindow, "not enough points for window"};
        return {};
    }

    std::vector<std::pair<std::string, double>> out;
    out.reserve(pts.size() - static_cast<size_t>(window) + 1);

    double run = 0.0;
    for (int i = 0; i < window; ++i) run += pts[i].second;
    out.emplace_back(pts[window - 1].first, run / window);

    for (size_t i = static_cast<size_t>(window); i < pts.size(); ++i) {
        run += pts[i].second - pts[i - window].second;
        out.emplace_back(pts[i].first, run / window);
    }
    return out;
}

} // namespace ccd
```

**Rules (FR-C5–FR-C7):**

- `filterRange` inclusive on both ends; `""` means unbounded. `start>end` → `EmptyRange` (HTTP 400).
- Zero points after filter → `EmptyRange`.
- `% change = (last-first)/first*100`; guard `first==0`.
- `stddev` = population standard deviation (divide by `N`, not `N-1`).
- Moving average uses running sum `O(N)` — not nested loops.

---

## 6. Unit Tests (doctest)

### 6.1 `core/tests/CMakeLists.txt`

```cmake
# core/tests/CMakeLists.txt
# One executable per suite; each linked against currency_core + doctest header.

add_executable(test_csv_parser  test_csv_parser.cpp)
target_link_libraries(test_csv_parser PRIVATE currency_core)
target_include_directories(test_csv_parser PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/third_party)

add_executable(test_rate_engine test_rate_engine.cpp)
target_link_libraries(test_rate_engine PRIVATE currency_core)
target_include_directories(test_rate_engine PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/third_party)

add_executable(test_stats_engine test_stats_engine.cpp)
target_link_libraries(test_stats_engine PRIVATE currency_core)
target_include_directories(test_stats_engine PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/third_party)

# Optional generators (not registered as ctest — run manually):
add_executable(parity_seeds parity_seeds.cpp)
target_link_libraries(parity_seeds PRIVATE currency_core)

add_executable(bench_csv_parser test_benchmark.cpp)
target_link_libraries(bench_csv_parser PRIVATE currency_core)

add_test(NAME test_csv_parser  COMMAND test_csv_parser)
add_test(NAME test_rate_engine COMMAND test_rate_engine)
add_test(NAME test_stats_engine COMMAND test_stats_engine)
```

### 6.2 Vendoring `doctest.h` (pinned v2.4.12)

Doc 01 §1.5 pins `core/tests/third_party/doctest.h` — commit it so CI never downloads at build time:

```bash
mkdir -p core/tests/third_party
curl -L -o core/tests/third_party/doctest.h \
  https://raw.githubusercontent.com/doctest/doctest/v2.4.12/doctest/doctest.h
# Verify first line is:  #define DOCTEST_VERSION_MAJOR 2
head -1 core/tests/third_party/doctest.h
```

> `server/third_party/{httplib.h,json.hpp}` are vendored in doc 04 — not needed for this doc.

### 6.3 `core/tests/test_csv_parser.cpp` — 9 Cases

```cpp
// core/tests/test_csv_parser.cpp
#define DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
#include "doctest.h"
#include "ccd/csv_parser.h"
#include <sstream>

using namespace ccd;

TEST_CASE("parser: happy path counts") {
    const std::string csv =
        "Date,EUR,USD,GBP\n"
        "2024-01-01,1,1.1,0.9\n"
        "2024-01-02,1,1.2,0.85\n";
    auto r = parseCsvText(csv);
    CHECK(r.rowsTotal == 2);
    CHECK(r.rowsSkipped == 0);
    CHECK(r.series.count("EUR") == 1);
    CHECK(r.series.at("EUR").size() == 2);
    CHECK(r.dateMin == "2024-01-01");
    CHECK(r.dateMax == "2024-01-02");
}

TEST_CASE("parser: skips malformed rows & increments counter") {
    const std::string csv =
        "Date,EUR,USD\n"
        "2024-01-01,1,1.1\n"
        "not-a-date,1,1.2\n"        // bad date → skip
        "2024-01-03,1,abc\n";       // bad numeric (non-blank) → skip whole row
    auto r = parseCsvText(csv);
    CHECK(r.rowsTotal == 1);
    CHECK(r.rowsSkipped == 2);
}

TEST_CASE("parser: quoted cells") {
    const std::string csv =
        "Date,\"EUR\",\"USD\"\n"
        "2024-01-01,1,1.1\n";
    auto r = parseCsvText(csv);
    CHECK(r.rowsTotal == 1);
    CHECK(r.series.count("EUR") == 1);
    CHECK(r.series.count("USD") == 1);
}

TEST_CASE("parser: CRLF line endings") {
    const std::string csv = "Date,EUR\r\n2024-01-01,1\r\n";
    auto r = parseCsvText(csv);
    CHECK(r.rowsTotal == 1);
    CHECK(r.dateMin == "2024-01-01");
}

TEST_CASE("parser: date normalization (slash)") {
    const std::string csv = "Date,EUR\n2024/01/05,1\n";
    auto r = parseCsvText(csv);
    CHECK(r.rowsTotal == 1);
    CHECK(r.dateMin == "2024-01-05");
}

TEST_CASE("parser: unsorted input gets sorted") {
    const std::string csv =
        "Date,EUR\n"
        "2024-01-03,1\n"
        "2024-01-01,1\n"
        "2024-01-02,1\n";
    auto r = parseCsvText(csv);
    REQUIRE(r.series.at("EUR").size() == 3);
    CHECK(r.series.at("EUR")[0].first == "2024-01-01");
    CHECK(r.series.at("EUR")[1].first == "2024-01-02");
    CHECK(r.series.at("EUR")[2].first == "2024-01-03");
}

TEST_CASE("parser: header-only file ⇒ zero series") {
    const std::string csv = "Date,EUR,USD\n";
    auto r = parseCsvText(csv);
    CHECK(r.rowsTotal == 0);
    CHECK(r.series.empty());
}

TEST_CASE("parser: blank cells are normal") {
    const std::string csv =
        "Date,EUR,USD,GBP\n"
        "2024-01-01,1,,0.9\n";      // USD blank → no point (normal)
    auto r = parseCsvText(csv);
    CHECK(r.rowsTotal == 1);
    CHECK(r.series.count("USD") == 0);
    CHECK(r.series.at("EUR").size() == 1);
    CHECK(r.series.at("GBP").size() == 1);
}

TEST_CASE("parser: scientific notation (BTC)") {
    const std::string csv = "Date,BTC\n2024-01-01,1.5082909e-05\n";
    auto r = parseCsvText(csv);
    REQUIRE(r.series.count("BTC") == 1);
    CHECK(r.series.at("BTC")[0].second == doctest::Approx(1.5082909e-05));
}

TEST_CASE("parser: istream overload") {
    std::istringstream in("Date,EUR\n2024-01-01,1\n");
    auto r = parseCsv(in);
    CHECK(r.rowsTotal == 1);
}
```

### 6.4 `core/tests/test_rate_engine.cpp` — 8 Cases

```cpp
// core/tests/test_rate_engine.cpp
#define DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
#include "doctest.h"
#include "ccd/csv_parser.h"
#include "ccd/rate_engine.h"
#include <cmath>

using namespace ccd;

static ParseResult fixture() {
    const std::string csv =
        "Date,EUR,USD,GBP\n"
        "2024-01-01,1,1.1,0.9\n"
        "2024-01-02,1,1.2,0.85\n"
        "2024-01-03,1,1.3,0.8\n";
    return parseCsvText(csv);
}

TEST_CASE("rate: direct pair EUR->USD") {
    RateEngine eng(fixture());
    double rate = 0; std::string d;
    auto e = eng.rateFor("EUR", "USD", "2024-01-02", rate, d);
    CHECK(!e);
    CHECK(rate == doctest::Approx(1.2));
    CHECK(d == "2024-01-02");
}

TEST_CASE("rate: inverse symmetry a->b * b->a ≈ 1") {
    RateEngine eng(fixture());
    double a2b = 0, b2a = 0; std::string d1, d2;
    eng.rateFor("GBP", "USD", "2024-01-02", a2b, d1);
    eng.rateFor("USD", "GBP", "2024-01-02", b2a, d2);
    CHECK((a2b * b2a) == doctest::Approx(1.0));
}

TEST_CASE("rate: same currency = 1.0") {
    RateEngine eng(fixture());
    double rate = 0; std::string d;
    auto e = eng.rateFor("USD", "USD", "", rate, d);
    CHECK(!e);
    CHECK(rate == doctest::Approx(1.0));
}

TEST_CASE("rate: last-known fallback (date after max)") {
    RateEngine eng(fixture());
    double rate = 0; std::string d;
    auto e = eng.rateFor("EUR", "USD", "2024-02-01", rate, d);
    CHECK(!e);
    CHECK(rate == doctest::Approx(1.3));   // falls back to 2024-01-03
    CHECK(d == "2024-01-03");
}

TEST_CASE("rate: unknown currency error") {
    RateEngine eng(fixture());
    double rate = 0; std::string d;
    auto e = eng.rateFor("EUR", "ZZZ", "", rate, d);
    CHECK(e.code == Error::Code::UnknownCurrency);
}

TEST_CASE("rate: date before dateMin → InvalidDate") {
    RateEngine eng(fixture());
    double rate = 0; std::string d;
    auto e = eng.rateFor("EUR", "USD", "2000-01-01", rate, d);
    CHECK(e.code == Error::Code::InvalidDate);
}

TEST_CASE("convert: invalid amounts (0, negative, NaN)") {
    RateEngine eng(fixture());
    ConversionResult out;
    CHECK(eng.convert("EUR", "USD", 0.0, "", out).code == Error::Code::InvalidAmount);
    CHECK(eng.convert("EUR", "USD", -5.0, "", out).code == Error::Code::InvalidAmount);
    CHECK(eng.convert("EUR", "USD", std::nan(""), "", out).code == Error::Code::InvalidAmount);
    CHECK(eng.convert("EUR", "USD", INFINITY, "", out).code == Error::Code::InvalidAmount);
}

TEST_CASE("convert: valid computes result") {
    RateEngine eng(fixture());
    ConversionResult out;
    auto e = eng.convert("EUR", "USD", 100.0, "2024-01-02", out);
    CHECK(!e);
    CHECK(out.rate   == doctest::Approx(1.2));
    CHECK(out.result == doctest::Approx(120.0));
    CHECK(out.date   == "2024-01-02");
}
```

### 6.5 `core/tests/test_stats_engine.cpp` — 9 Cases

```cpp
// core/tests/test_stats_engine.cpp
#define DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
#include "doctest.h"
#include "ccd/csv_parser.h"
#include "ccd/rate_engine.h"
#include "ccd/stats_engine.h"
#include <cmath>

using namespace ccd;

static ParseResult fixture() {
    const std::string csv =
        "Date,EUR,USD\n"
        "2024-01-01,1,1.0\n"
        "2024-01-02,1,2.0\n"
        "2024-01-03,1,3.0\n"
        "2024-01-04,1,4.0\n";
    return parseCsvText(csv);
}

TEST_CASE("stats: known min/max/avg") {
    RateEngine eng(fixture());
    Error err;
    auto pts = filterRange(eng, "USD", "", "", err);
    REQUIRE(!err);
    StatsResult s; REQUIRE(!computeStats(pts, s));
    CHECK(s.min == doctest::Approx(1.0));
    CHECK(s.max == doctest::Approx(4.0));
    CHECK(s.avg == doctest::Approx(2.5));
    CHECK(s.count == 4);
    CHECK(s.firstDate == "2024-01-01");
    CHECK(s.lastDate  == "2024-01-04");
}

TEST_CASE("stats: pct change sign (300%)") {
    RateEngine eng(fixture());
    Error err;
    auto pts = filterRange(eng, "USD", "", "", err);
    StatsResult s; computeStats(pts, s);
    CHECK(s.pctChange == doctest::Approx(300.0)); // (4-1)/1*100
}

TEST_CASE("stats: stddev population vs hand-computed") {
    // values 1,2,3,4 mean 2.5; var = (2.25+0.25+0.25+2.25)/4 = 1.25; std = sqrt(1.25)
    RateEngine eng(fixture());
    Error err;
    auto pts = filterRange(eng, "USD", "", "", err);
    StatsResult s; computeStats(pts, s);
    CHECK(s.stddev == doctest::Approx(std::sqrt(1.25)));
}

TEST_CASE("stats: empty range error (no overlap)") {
    RateEngine eng(fixture());
    Error err;
    auto pts = filterRange(eng, "USD", "2024-02-01", "2024-03-01", err);
    CHECK(err.code == Error::Code::EmptyRange);
}

TEST_CASE("stats: start > end error") {
    RateEngine eng(fixture());
    Error err;
    auto pts = filterRange(eng, "USD", "2024-01-04", "2024-01-01", err);
    CHECK(err.code == Error::Code::EmptyRange);
}

TEST_CASE("stats: unknown currency") {
    RateEngine eng(fixture());
    Error err;
    auto pts = filterRange(eng, "ZZZ", "", "", err);
    CHECK(err.code == Error::Code::UnknownCurrency);
}

TEST_CASE("moving average: window=2") {
    RateEngine eng(fixture());
    Error err;
    auto pts = filterRange(eng, "USD", "", "", err);
    auto ma = movingAverage(pts, 2, err);
    REQUIRE(!err);
    REQUIRE(ma.size() == 3);                    // N-window+1 = 3
    CHECK(ma[0].second == doctest::Approx(1.5)); // (1+2)/2
    CHECK(ma[1].second == doctest::Approx(2.5)); // (2+3)/2
    CHECK(ma[2].second == doctest::Approx(3.5)); // (3+4)/2
    CHECK(ma[0].first  == "2024-01-02");
}

TEST_CASE("moving average: length = N-window+1") {
    RateEngine eng(fixture());
    Error err;
    auto pts = filterRange(eng, "USD", "", "", err);
    auto ma = movingAverage(pts, 3, err);
    CHECK(ma.size() == 2); // 4-3+1
}

TEST_CASE("moving average: bad window <2 and window> N") {
    RateEngine eng(fixture());
    Error err;
    auto pts = filterRange(eng, "USD", "", "", err);
    auto ma1 = movingAverage(pts, 1, err);
    CHECK(err.code == Error::Code::BadWindow);
    auto ma2 = movingAverage(pts, 10, err);
    CHECK(err.code == Error::Code::BadWindow);
}
```

### 6.6 Fixture Strategy (Two Levels)

| Level | What | File |
|---|---|---|
| Inline fixtures | Tiny CSV strings in each `TEST_CASE` (fast, obvious) | All three test files above |
| Golden fixture | `data/sample_rates.csv` — 40 days × 8 majors (EUR,USD,GBP,JPY,INR,AUD,CAD,CHF; 3.1 KB) — expected values cross-checked via `python3 scripts/verify_dataset.py` | Used by parity generator §7.2 and manual smoke test |

---

## 7. Performance & Parity Helpers (Not in CI by Default)

### 7.1 `core/tests/test_benchmark.cpp` — Parse < 800 ms Gate

```cpp
// core/tests/test_benchmark.cpp
// Manual sanity: ./build/core/tests/bench_csv_parser [path]
// Skipped in ctest unless run explicitly. Target < 800 ms on dev machine for 4.6 MB file.
#include "ccd/csv_parser.h"
#include <chrono>
#include <iostream>

using namespace ccd;

int main(int argc, char** argv) {
    const std::string path = (argc > 1) ? argv[1] : "data/exchange_rates.csv";
    auto t0 = std::chrono::steady_clock::now();
    ParseResult r = parseCsvFile(path);
    auto t1 = std::chrono::steady_clock::now();
    double ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    double rowsPerSec = (ms > 0) ? r.rowsTotal / (ms / 1000.0) : 0;

    std::cout << "rowsTotal=" << r.rowsTotal
              << " rowsSkipped=" << r.rowsSkipped
              << " dateMin=" << r.dateMin << " dateMax=" << r.dateMax << "\n";
    std::cout << "elapsed=" << ms << " ms  (" << rowsPerSec/1000.0 << "k rows/sec)\n";

    if (r.rowsTotal == 0) { std::cerr << "no rows parsed — check path\n"; return 2; }
    if (ms > 800.0) {
        std::cout << "WARNING: exceeded 800 ms budget — consider reserving vectors / string_view slicing\n";
        return 1;
    }
    std::cout << "PASS: under 800 ms budget\n";
    return 0;
}
```

Run manually after building:

```bash
cmake --build build --target bench_csv_parser
./build/core/tests/bench_csv_parser data/exchange_rates.csv
# expected: rowsTotal≈6551, elapsed < 800 ms (Apple M-series: ~30–80 ms)
```

Tuning hint (only if exceeded): `series.reserve(rowsTotal)`-style reservations are not needed at this size, but avoid per-row string copies by slicing via `string_view` into interned date storage.

### 7.2 `core/tests/parity_seeds.cpp` — Golden JSON for Doc 05

Generates `scripts/fixtures/parity_seeds.json` (20 tuples) consumed by doc 05's `parity_test.mjs` to compare WASM vs REST.

```cpp
// core/tests/parity_seeds.cpp — run manually, not in ctest
// Usage: ./build/core/tests/parity_seeds [inCsv] [outJson]
#include "ccd/csv_parser.h"
#include "ccd/rate_engine.h"
#include <algorithm>
#include <fstream>
#include <iostream>

using namespace ccd;

int main(int argc, char** argv) {
    const std::string inPath  = (argc > 1) ? argv[1] : "data/sample_rates.csv";
    const std::string outPath = (argc > 2) ? argv[2] : "scripts/fixtures/parity_seeds.json";

    ParseResult data = parseCsvFile(inPath);
    if (data.series.empty()) { std::cerr << "parse failed: " << inPath << "\n"; return 1; }
    RateEngine eng(data);

    std::vector<std::string> curs;
    for (auto& kv : data.series) curs.push_back(kv.first);
    std::sort(curs.begin(), curs.end());

    // Collect all dates from first currency's series
    std::vector<std::string> dates;
    if (!curs.empty()) for (auto& p : data.series.at(curs.front())) dates.push_back(p.first);
    if (dates.empty()) { std::cerr << "no dates\n"; return 1; }

    std::ofstream out(outPath);
    if (!out) { std::cerr << "cannot write " << outPath << "\n"; return 1; }

    const int step = std::max(1, static_cast<int>(dates.size()) / 4);
    out << "[\n";
    int written = 0; bool first = true;
    for (size_t di = 0; di < dates.size() && written < 20; di += step) {
        const std::string& date = dates[di];
        for (size_t a = 0; a < curs.size() && written < 20; ++a) {
            for (size_t b = 0; b < curs.size() && written < 20; ++b) {
                if (a == b) continue;
                ConversionResult cr;
                if (eng.convert(curs[a], curs[b], 100.0, date, cr)) continue;
                if (!first) out << ",\n";
                first = false;
                out << "  {\"from\":\"" << cr.from << "\",\"to\":\"" << cr.to
                    << "\",\"amount\":100.0,\"date\":\"" << cr.date
                    << "\",\"expectedRate\":" << cr.rate
                    << ",\"expectedResult\":" << cr.result << "}";
                ++written;
            }
        }
    }
    out << "\n]\n";
    std::cout << "wrote " << written << " parity seeds to " << outPath << "\n";
    return 0;
}
```

```bash
cmake --build build --target parity_seeds
./build/core/tests/parity_seeds data/sample_rates.csv scripts/fixtures/parity_seeds.json
cat scripts/fixtures/parity_seeds.json   # 20 entries, each with expectedRate/expectedResult
```

> No third-party JSON dependency — emits plain JSON manually (core stays dependency-free).

---

## 8. Build & Test — Exactly as CI Runs

### 8.1 One-Time Setup

```bash
# From repo root — toolchain already verified in doc 01 §1.7
cmake --version   # ≥3.16
c++ --version     # Apple clang 14+ / gcc 11+ / MSVC 2022
```

### 8.2 Configure, Build, Test

```bash
cmake -S . -B build
cmake --build build -j
ctest --test-dir build --output-on-failure
# Expected:
# 100% tests passed, 0 tests failed out of 3
#   test_csv_parser  ........ Passed
#   test_rate_engine ........ Passed
#   test_stats_engine ....... Passed
```

With warnings as errors (CI style):

```bash
cmake -S . -B build -DCMAKE_CXX_FLAGS="-Werror"
cmake --build build && ctest --test-dir build --output-on-failure
```

### 8.3 Smoke Against Real Datasets

Once during M1 — parser must handle both committed CSVs:

```bash
./build/core/tests/bench_csv_parser data/sample_rates.csv
./build/core/tests/bench_csv_parser data/exchange_rates.csv
# Both must report rowsTotal > 0 and elapsed < 800 ms for the small fixture
# (full file < 800 ms target on dev machine)
```

Ad-hoc with a path argument on the parser test executable is *not* needed — the benchmark binary covers it. The pattern in doc 03 §3.7
`./build/core/tests/test_csv_parser data/exchange_rates.csv` is superseded by `bench_csv_parser`.

### 8.4 Dataset Pipeline (Already Built — Do Not Reimplement)

From doc A §A.4 / doc 03 §3.7 — normalizer lives at `tools/normalize_dataset.py`:

```bash
# Regenerate canonical + fixture from raw export (repo root):
python3 tools/normalize_dataset.py daily_forex_rates.csv data/exchange_rates.csv
python3 tools/normalize_dataset.py daily_forex_rates.csv data/sample_rates.csv \
    --last-dates 40 --currencies EUR,USD,GBP,JPY,INR,AUD,CAD,CHF
python3 scripts/verify_dataset.py        # must print ALL CHECKS PASSED
```

Parser-relevant properties of the output: wide schema (`Date,<CODE>,...`), ascending unique ISO dates, constant `EUR=1` pivot column, verbatim rate tokens (exponents preserved), blank cells where a currency had no quote.

---

## 9. Implementation Order (Suggested Commits)

Follow doc 08 conventional commits, one concern per commit:

```bash
git add core/include/ccd/models.h core/CMakeLists.txt CMakeLists.txt
git commit -m "feat(core): add models and build scaffold"

git add core/include/ccd/csv_parser.h core/src/csv_parser.cpp
git commit -m "feat(core): csv parser — quotes, blank cells, exponent tokens, date normalization"

git add core/include/ccd/rate_engine.h core/src/rate_engine.cpp
git commit -m "feat(core): rate engine — cross-rate via EUR pivot, last-known fallback, binary search"

git add core/include/ccd/stats_engine.h core/src/stats_engine.cpp
git commit -m "feat(core): stats engine — filter, population stats, running-sum moving average"

git add core/tests/
git commit -m "test(core): doctest suites for parser/rate/stats + benchmark and parity generator"
```

---

## 10. Common Pitfalls & Fixes

| Symptom | Cause → Fix |
|---|---|
| `std::from_chars` fails on Apple clang 14 | Use `strtod` as in §3.2 — `from_chars` double is unimplemented on Apple clang 14 |
| `rowsSkipped` too high (>1%) | Check blank-cell handling: blank → skip *cell*, not *row* |
| Inverse symmetry `a→b * b→a != 1` | Forgot EUR pivot division — must be `tv/fv`, not subtraction |
| `upper_bound` returns wrong date | Comparator must be `(string, pair)` with `t < e.first` |
| `computeStats` pctChange NaN | Guard `first==0` (early years have sparse currencies) |
| `movingAverage` off-by-one | Output length is `N-window+1`; use running sum, seed with `pts[window-1].first` |
| Build error `state_engine.cpp not found` | Fix `core/CMakeLists.txt` to `stats_engine.cpp` (§1.2) |
| Test binary missing `doctest.h` | Vendor per §6.2 — never fetch at build time |

---

## ✅ Exit Checklist (M1 Gate)

Copy into PR description and check off:

- [ ] `cmake -S . -B build && cmake --build build` — zero warnings with `-Wall -Wextra -Wpedantic`
- [ ] `ctest --test-dir build --output-on-failure` — all 3 suites green (26 cases)
- [ ] `core/tests/third_party/doctest.h` vendored and committed (v2.4.12)
- [ ] `core/src/csv_parser.cpp` handles blank cells, `\r\n`, quotes, exponents, date normalization, defensive sort
- [ ] `RateEngine` uses `upper_bound` binary search; `from==to` → 1.0; validation order `UnknownCurrency → InvalidAmount → InvalidDate`
- [ ] `StatsResult` uses population stddev; `movingAverage` is `O(N)` running sum
- [ ] `bench_csv_parser data/exchange_rates.csv` — elapsed < 800 ms, skipped rows < 1%
- [ ] `parity_seeds` generated: `scripts/fixtures/parity_seeds.json` (20 tuples) for doc 05
- [ ] `python3 scripts/verify_dataset.py` prints `ALL CHECKS PASSED`
- [ ] Committed as `feat(core): …` / `test(core): …` per §9

---

## References

- Basic contracts & checklist: [`03-core-library-implementation.md`](./03-core-library-implementation.md)
- Repository layout: [`02-repository-and-project-structure.md`](./02-repository-and-project-structure.md)
- Dataset & regeneration: [`A-data-pipeline.md`](./A-data-pipeline.md)
- Next step after this doc: [`04-http-server.md`](./04-http-server.md) (native REST transport)
