# 03 — Core Library Implementation

Goal: implement the platform-independent C++17 static lib `currency_core` — CSV parsing, cross-rate conversion, statistics — fully covered by doctest suites. No HTTP, no JS, no OS-specific code here.

Covers PRD FR-C1–FR-C8 · Milestone M1 · Estimated Days 2–4.

## 3.0 Top-level CMake

```cmake
# CMakeLists.txt (repo root)
cmake_minimum_required(VERSION 3.16)
project(currency-converter-dashboard LANGUAGES C CXX)

option(BUILD_SERVER "Build the native HTTP server (cpp‑httplib)" ON)
option(BUILD_WASM   "Build the WebAssembly (Emscripten) target" OFF)
option(BUILD_TESTS  "Build unit tests" ON)

add_subdirectory(core)

if (BUILD_SERVER AND NOT BUILD_WASM)
    add_subdirectory(server)
endif()

if (BUILD_WASM)
    add_subdirectory(wasm)
endif()
```

> **CLion tip:** Create two CMake profiles:
> - **Native‑Release**: default toolchain, leave `BUILD_WASM=OFF` (or unset).
> - **WASM‑Release**: select the Emscripten toolchain (clear the C/C++ compiler fields, point to `<emsdk>/upstream/emscripten/cmake/Modules/Platform/Emscripten.cmake`), set `-DBUILD_WASM=ON`.
> Reload CMake after switching profiles and build (`Ctrl+F9`).

`core/CMakeLists.txt`:

`core/CMakeLists.txt`:

```cmake
add_library(currency_core STATIC
  src/csv_parser.cpp src/rate_engine.cpp src/stats_engine.cpp)
target_include_directories(currency_core PUBLIC include)
target_compile_options(currency_core PRIVATE
  $<$<CXX_COMPILER_ID:MSVC>:/W4>
  $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-Wall -Wextra -Wpedantic>)
```

## 3.1 models.h — shared value types

```cpp
#pragma once
#include <string>
#include <vector>
#include <unordered_map>

namespace ccd {

struct ParseResult {                       // FR-C1, FR-C4
    // series[currency] = sorted-by-date daily rates (native EUR base)
    std::unordered_map<std::string, std::vector<std::pair<std::string,double>>> series;
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

struct Error {                              // FR-B4 / FR-C8
    enum class Code {
        Ok, UnknownCurrency, InvalidAmount, InvalidDate, EmptyRange, BadWindow, Internal
    };
    Code code = Code::Ok;
    std::string message;
    explicit operator bool() const { return code != Code::Ok; }
};

} // namespace ccd
```

## 3.2 csv_parser — strict, forgiving-on-rows parsing

Behavior contract (FR-C1, FR-C4):
- Header row defines currency columns; column 1 must be `Date` (pivot column `EUR` = constant `1`).
- Rows with bad dates increment `rowsSkipped`; parsing never throws.
- **Blank cells are normal, not errors**: coverage ramps from ~2 currencies/day (2004) to ~172/day (2025), so most cells before ~2014 are empty. A blank cell simply means that currency gets no point for that date — never drop or skip the row because some columns are blank.
- Numeric tokens may use **scientific notation** (`1.5082909e-05`, BTC rates). Parse with `std::strtod`/`std::from_chars` — both handle exponents natively.
- Dates arrive ISO-8601 ascending from the pipeline; still verify ordering and `std::sort` defensively (ISO sorts lexicographically).
- Handles optional surrounding quotes and `\r\n` line endings (defensive; current dataset has neither).

Key implementation sketch (`src/csv_parser.cpp`):

```cpp
namespace ccd {
static std::string normalizeDate(std::string s);      // "2024/01/05" -> "2024-01-05"; "" if invalid
static bool parseDouble(std::string_view tok, double& out); // locale-safe '.', rejects NaN/inf

ParseResult parseCsv(std::istream& in);               // used by tests & tools
ParseResult parseCsvFile(const std::string& path);
ParseResult parseCsvText(const std::string& text);    // used by WASM loader (doc 05)
}
```

Implementation rules:
- Read whole file/text, split lines on `\n`, strip trailing `\r`.
- Split cells on commas **outside quotes** (simple state machine — financial CSVs rarely quote, but be safe).
- Trim spaces around tokens; blank numeric cell ⇒ store nothing for that currency/date (see blank-cells rule above); unparseable non-blank cell ⇒ count in `rowsSkipped` and continue.
- After loading each currency's vector, verify ascending dates (they arrive sorted; if not, `std::sort` by date string — ISO sorts lexicographically).

## 3.3 rate_engine — conversions via native base (EUR)

Contract (FR-C3): `rate(from→to, date)` = `value[to][date] / value[from][date]`. Missing exact date ⇒ use latest date ≤ requested ("last known rate"); missing everything before `dateMin` ⇒ error.

```cpp
namespace ccd {
class RateEngine {
public:
    explicit RateEngine(ParseResult data);
    const ParseResult& meta() const;

    Error rateFor(const std::string& from, const std::string& to,
                  const std::string& date /*"" = latest*/, double& outRate,
                  std::string& outActualDate) const;

    Error convert(const std::string& from, const std::string& to,
                  double amount, const std::string& date,
                  ConversionResult& out) const;             // validates amount > 0, finite
};
}
```

Validation order (FR-C8): unknown currency → `UnknownCurrency`; `!(amount > 0 && std::isfinite(amount))` → `InvalidAmount`; malformed/unreachable date → `InvalidDate`. Same-currency pairs (`from == to`) are legal: rate 1.0, no lookup needed.

Binary search helper: since each series is date-sorted, find "last ≤ date" with `std::upper_bound` on the date strings.

## 3.4 stats_engine — filtering + aggregates

Contract (FR-C5–FR-C7):

```cpp
namespace ccd {
std::vector<std::pair<std::string,double>>
filterRange(const RateEngine& eng, const std::string& cur,
            const std::string& start, const std::string& end, Error& err); // inclusive

Error computeStats(const std::vector<std::pair<std::string,double>>& pts,
                   StatsResult& out);                 // min/max/avg/pctChange/stddev/count

std::vector<std::pair<std::string,double>>
movingAverage(const std::vector<std::pair<std::string,double>>& pts,
              int window, Error& err);                // window >= 2; output length = N-window+1
}
```

Rules:
- `start > end` ⇒ `EmptyRange` (caller maps to HTTP 400); zero points after filter ⇒ `EmptyRange`.
- `% change = (last − first) / first × 100`; guard `first == 0`.
- stddev = population standard deviation.
- Moving average uses a running sum (O(N)), not nested loops.

## 3.5 Unit Tests (doctest)

`core/tests/CMakeLists.txt`: one test executable per file, registered with `add_test`, linked against `currency_core`.

Fixture strategy — two levels:
1. **Inline fixtures:** tiny CSV strings written directly in test files (fast, obvious).
2. **Golden fixture:** `data/sample_rates.csv` — generated by the data pipeline (last 40 trading days × 8 majors: EUR, USD, GBP, JPY, INR, AUD, CAD, CHF; 3.1 KB). Expected values are cross-checkable via `python3 scripts/verify_dataset.py`, which computes GBP→JPY and USD→INR independently from the raw source.

Required cases (each becomes one `TEST_CASE`):

| Suite | Cases |
|-------|-------|
| parser | happy path counts; skips malformed rows & increments counter; quoted cells; `\r\n`; date normalization; unsorted input gets sorted; header-only file ⇒ zero series |
| rate | direct pair; inverse pair symmetry (`a→b × b→a ≈ 1`); same currency = 1.0; last-known-rate fallback; unknown currency error; invalid amount (0, negative, NaN) errors |
| stats | known min/max/avg on fixture range; pct change sign; stddev vs hand-computed; empty range error; window=2 minimum; moving average length & first values |
| parity seeds | 20 `(from,to,amount,date)` tuples + expected outputs exported as JSON for doc 05's parity script |

Run locally:

```bash
cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure
```

## 3.6 Performance Sanity (FR targets)

Add one non-CI benchmark test (skipped by default, run manually):
parse `data/exchange_rates.csv`, assert wall time < 800 ms on dev machine (`std::chrono::steady_clock`). Log rows/sec to stdout. Tune only if exceeded: reserve vectors (`series.reserve(rowsTotal)`), avoid per-row string copies (`std::string_view` slicing into interned date storage).

## 3.7 Dataset Pipeline (already built — do not reimplement)

The long→wide normalizer exists at [`tools/normalize_dataset.py`](../../tools/normalize_dataset.py) with its verification gate at `scripts/verify_dataset.py`. Full procedure, dataset facts, and the EUR-base decision record live in [A-data-pipeline.md](A-data-pipeline.md). Core-team summary:

```bash
# regenerate canonical dataset + fixture from raw export (repo root):
python3 tools/normalize_dataset.py daily_forex_rates.csv data/exchange_rates.csv
python3 tools/normalize_dataset.py daily_forex_rates.csv data/sample_rates.csv \
    --last-dates 40 --currencies EUR,USD,GBP,JPY,INR,AUD,CAD,CHF
python3 scripts/verify_dataset.py        # must print ALL CHECKS PASSED
```

Parser-relevant properties of the output: wide schema (`Date,<code>,...`), ascending unique ISO dates, constant `EUR=1` pivot column, verbatim rate tokens (may be exponent notation), blank cells where a currency had no quote.

Smoke-test the C++ parser against both real files once during M1:

```bash
./build/core/tests/test_csv_parser data/exchange_rates.csv   # ad-hoc main arg support
./build/core/tests/test_csv_parser data/sample_rates.csv
```

## ✅ Exit Checklist

- [ ] `ctest --test-dir build` green: all parser/rate/stats cases
- [ ] Zero compiler warnings with `-Wall -Wextra -Wpedantic`
- [ ] Golden parity-seed JSON generated (`scripts/fixtures/parity_seeds.json`) for doc 05
- [ ] Real dataset parses < 800 ms; skipped-row count reasonable (< 1%)
- [ ] Committed as: `feat(core): csv parser`, `feat(core): rate engine`, `feat(core): stats engine`, `test(core): unit suites`
