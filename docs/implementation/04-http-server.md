# 04 — HTTP Server (Native Transport)

Goal: expose `currency_core` as a REST API using cpp-httplib + nlohmann/json, serving the frontend statically. Covers PRD FR-B1, FR-B5, §7.1 · Milestone M2 · Day 5.

## 4.1 Vendor Headers

```bash
curl -L -o server/third_party/httplib.h \
  https://raw.githubusercontent.com/yhirose/cpp-httplib/v0.15.3/httplib.h
curl -L -o server/third_party/json.hpp \
  https://raw.githubusercontent.com/nlohmann/json/v3.11.3/single_include/nlohmann/json.hpp
```

`server/CMakeLists.txt`:

```cmake
add_executable(currency_server main.cpp api_routes.cpp)
target_include_directories(currency_server PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/third_party)
target_link_libraries(currency_server PRIVATE currency_core)
if(WIN32)
  target_link_libraries(currency_server PRIVATE ws2_32)   # httplib requirement
endif()
```

## 4.2 Route Wiring (`api_routes.{h,cpp}`)

One handler per PRD §7.1 endpoint. Shared pattern:

```cpp
void registerRoutes(httplib::Server& svr, ccd::RateEngine& eng) {
    svr.Get("/healthz", [](const httplib::Request&, httplib::Response& res) {
        res.set_content(R"({"status":"ok"})", "application/json; charset=utf-8");
    });

    svr.Get("/api/meta", [&eng](const auto&, auto& res) {
        res.set_content(toJsonMeta(eng.meta()), jsonMime);        // FR-C2
    });

    svr.Get("/api/convert", [&](const auto& req, auto& res) {
        handleConvert(req, res, eng);                              // FR-C3
    });
    // /api/rate, /api/historical, /api/stats, /api/moving-average …
}
```

`handleConvert` reference shape — every endpoint follows it:

```cpp
static void handleConvert(const httplib::Request& req, httplib::Response& res,
                          const ccd::RateEngine& eng) {
    auto from = req.get_param_value("from");
    auto to   = req.get_param_value("to");
    auto date = req.get_param_value("date");            // may be ""
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
    res.set_content(toJson(out), jsonMime);
}
```

**Error mapping table (FR-B4)** — implement once in `sendDomainError`:

| `ccd::Error::Code` | HTTP | `code` string |
|---|---|---|
| UnknownCurrency | 404 | `UNKNOWN_CURRENCY` |
| InvalidDate | 400 | `INVALID_DATE` |
| InvalidAmount | 400 | `INVALID_AMOUNT` |
| EmptyRange | 404 | `EMPTY_RANGE` |
| BadWindow | 400 | `BAD_WINDOW` |
| Internal | 500 | `INTERNAL` |

JSON serialization with nlohmann/json — camelCase keys exactly as PRD §7.1:

```cpp
nlohmann::json j;
j["from"] = out.from; j["to"] = out.to; j["amount"] = out.amount;
j["rate"] = round6(out.rate); j["result"] = round6(out.result);
j["date"] = out.date;
res.set_content(j.dump(), jsonMime);
```

Round all floating outputs to 6 decimal places (`std::round(v*1e6)/1e6`) so REST and WASM produce byte-identical JSON for parity tests.

## 4.3 Static Frontend Serving

Same-origin serving removes CORS from normal operation:

```cpp
const std::string frontendDir = /* --static arg or "./frontend" */;
svr.set_mount_point("/", frontendDir);

svr.set_error_handler([](const auto&, auto& res) {
    if (res.status == 404 && !res.body.empty()) return;         // API error already set
    res.set_content(notFoundHtml(), "text/html; charset=utf-8");
});
```

## 4.4 CLI & Lifecycle (`main.cpp`)

Flags per FR-B5, plus `PORT` env support (needed by Render later):

```cpp
int main(int argc, char** argv) {
    std::string dataPath = "data/exchange_rates.csv";
    std::string staticDir = "frontend";
    int port = 8080;                       // parse --data/--static/--port, then
    if (const char* envPort = std::getenv("PORT")) port = std::atoi(envPort);

    ccd::ParseResult parsed = ccd::parseCsvFile(dataPath);
    if (parsed.series.empty()) {           // fail fast, loud
        std::fprintf(stderr, "FATAL: no rows parsed from %s\n", dataPath.c_str());
        return 1;
    }
    std::printf("Loaded %zu currencies, %zu rows (%s skipped)\n",
                parsed.series.size(), parsed.rowsTotal, …);

    httplib::Server svr;
    registerRoutes(svr, engine);
    svr.listen("0.0.0.0", port);           // blocks; Ctrl+C handled by httplib
}
```

Log one startup line with dataset range and every registered route — cheap debuggability.

## 4.5 Local Run & Manual Verification

```bash
cmake -S . -B build && cmake --build build
./build/server/currency_server --port 8080
```

```bash
curl -s localhost:8080/healthz
curl -s "localhost:8080/api/meta"
curl -s "localhost:8080/api/convert?from=USD&to=EUR&amt=100"     # wrong param name → 400
curl -s "localhost:8080/api/convert?from=USD&to=EUR&amount=100"
curl -s "localhost:8080/api/stats?from=EUR&to=GBP&start=2024-01-01&end=2024-12-31"
curl -si "localhost:8080/api/convert?from=XXX&to=EUR&amount=100" # expect 404 UNKNOWN_CURRENCY
open http://localhost:8080                                       # serves frontend (doc 06)
```

The full scripted suite lives in `scripts/smoke_api.sh` (built in doc 07).

## ✅ Exit Checklist

- [ ] All 7 endpoints return correct shapes per PRD §7.1
- [ ] Every error path returns `{ "error": { code, message } }` with correct HTTP status
- [ ] Static mount serves `frontend/index.html` at `/`
- [ ] Server starts with `--port`, `--data`, `--static` flags AND bare `$PORT`
- [ ] Missing/corrupt CSV exits non-zero with a clear message
- [ ] Commit: `feat(server): rest api with cpp-httplib`
