# Currency Converter & Economic Dashboard — Reconfiguration Plan

## Original Project

A **JavaFX + C++ (JNI)** desktop application for currency conversion and economic trend visualization. Java handled the UI; C++ handled CSV parsing, rate computation, and statistics via JNI.

## New Architecture

**Web-based frontend (HTML/CSS/JS) + C++ backend (HTTP server) — No database, CSV dataset from Kaggle.**

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Browser (Frontend)                                │
│                                                                     │
│   HTML/CSS/JS — SPA (Single Page Application)                       │
│   • Currency selection dropdowns                                     │
│   • Amount input + Convert button                                    │
│   • Historical rate line chart (Chart.js or lightweight chart lib)  │
│   • Statistics panel (min/max/avg/% change)                          │
│   • Date range picker                                                │
│   • Favorites / export functionality                                 │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  HTTP REST API (JSON)
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    C++ Backend (HTTP Server)                         │
│                                                                     │
│   • Lightweight HTTP server (e.g., cpp-httplib, Crow, or raw       │
│     socket implementation)                                           │
│   • CSV parser (reads Kaggle dataset on startup)                    │
│   • Rate computation engine                                          │
│   • Statistical analysis (min, max, avg, moving avg, % change)     │
│   • Date range filtering                                             │
│   • Serves static frontend files (HTML/CSS/JS)                      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Data Layer                                        │
│                                                                     │
│   • Kaggle CSV dataset (e.g., exchange rates historical data)       │
│   • Parsed into in-memory std::vector on server startup             │
│   • No database required                                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Tech Stack

| Layer         | Technology                                         | Notes                                              |
|---------------|----------------------------------------------------|----------------------------------------------------|
| Frontend      | HTML5, CSS3, Vanilla JavaScript (ES6+)             | No framework dependency — keeps it simple          |
| Charting      | Chart.js (CDN) or custom SVG rendering             | Lightweight, no build step needed                  |
| HTTP Server   | C++ with `cpp-httplib` (single header) or `Crow`   | Header-only libraries — easy CMake integration     |
| CSV Parsing   | C++ `std::ifstream` + custom parser (or `fast-csv`)| Parse once on startup, cache in memory             |
| Build System  | CMake                                              | Cross-platform, industry standard                  |
| Data Source   | Kaggle CSV (exchange rates historical data)        | No database — file-based only                      |

---

## 3. Kaggle Dataset Strategy

### Recommended Dataset
Search Kaggle for: **"Exchange Rates Historical Data"** or **"Currency Exchange Rates"**

Expected CSV structure (varies by dataset — adapt parser accordingly):
```csv
Date,EUR/USD,GBP/USD,USD/JPY,AUD/USD,USD/CAD,...
2024-01-01,1.1045,1.2712,141.56,0.6812,1.3245,...
2024-01-02,1.1023,1.2698,142.01,0.6798,1.3267,...
```

### Data Loading Flow
1. User downloads CSV from Kaggle and places it in `data/` directory
2. C++ backend reads and parses the CSV on startup
3. Data is cached in an in-memory index structure for fast queries
4. No database — all queries are in-memory vector scans

---

## 4. Backend (C++) — Detailed Design

### 4.1 HTTP Server
```
server/
├── main.cpp              # Entry point: starts HTTP server, loads CSV
├── csv_parser.h/.cpp     # Parses Kaggle CSV into structured data
├── rate_engine.h/.cpp    # Currency conversion logic
├── stats_engine.h/.cpp   # Statistical computations
├── api_routes.h/.cpp     # HTTP route handlers
├── models.h              # Data structures (CurrencyRate, Stats, etc.)
└── CMakeLists.txt        # Build configuration
```

### 4.2 API Endpoints

| Method | Endpoint                          | Description                                      |
|--------|-----------------------------------|--------------------------------------------------|
| GET    | `/api/currencies`                 | Returns list of available currency codes          |
| GET    | `/api/convert?from=X&to=Y&amt=Z` | Converts amount from currency X to Y              |
| GET    | `/api/historical?pair=X_Y&from=DATE&to=DATE` | Returns daily rates for date range |
| GET    | `/api/stats?pair=X_Y&from=DATE&to=DATE`     | Returns min/max/avg/%change stats    |
| GET    | `/api/moving-average?pair=X_Y&window=N`     | Returns N-day moving average data   |
| GET    | `/*` (static)                     | Serves frontend files (HTML/CSS/JS)               |

### 4.3 Core Data Structures (C++)
```cpp
struct DailyRate {
    std::string date;       // ISO 8601: "2024-01-15"
    double rate;            // Exchange rate for that day
};

struct CurrencyPair {
    std::string from;       // e.g., "EUR"
    std::string to;         // e.g., "USD"
    std::vector<DailyRate> rates;
};

struct ConversionResult {
    double original_amount;
    double converted_amount;
    std::string from_currency;
    std::string to_currency;
    double rate_used;
};

struct StatsResult {
    double min_rate;
    double max_rate;
    double avg_rate;
    double percent_change;
    int data_points;
};
```

### 4.4 Key C++ Implementation Details

- **CSV Parsing:** Read header row to discover currency pair columns. Parse each subsequent row as date + rate values. Store as `std::unordered_map<std::string, CurrencyPair>` keyed by pair code (e.g., "EUR_USD").
- **Caching:** Parse CSV once at startup. All subsequent API queries hit the in-memory cache. For 10 years of data (~2500 rows × 10 pairs), memory usage is negligible (~200KB).
- **Date Filtering:** Binary search or linear scan on sorted date vectors for O(log n) or O(n) range queries.
- **Statistics:** `std::min_element`, `std::max_element`, `std::accumulate` for min/max/avg. Manual computation for percent change and moving averages.

---

## 5. Frontend (HTML/CSS/JS) — Detailed Design

### 5.1 File Structure
```
frontend/
├── index.html            # Main page
├── css/
│   ├── style.css         # Main styles
│   └── responsive.css    # Mobile/tablet breakpoints
├── js/
│   ├── app.js            # Main application logic, API calls
│   ├── chart.js          # Chart rendering (wraps Chart.js or custom)
│   └── utils.js          # Formatters, date helpers, DOM utilities
└── assets/
    └── (icons, fonts if needed)
```

### 5.2 Page Layout (Single Page)

```
┌──────────────────────────────────────────────────────────────────┐
│  🌐 Currency Converter & Economic Dashboard                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  FROM: [USD ▼]   AMOUNT: [______]   TO: [EUR ▼]         │   │
│  │                                              [Convert]    │   │
│  │  Result: 100.00 USD = 92.35 EUR  (Rate: 0.9235)          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────┐  ┌────────────────────────────────┐  │
│  │  Historical Rates    │  │  Statistics                    │  │
│  │                      │  │                                │  │
│  │  [Date Range Picker] │  │  Min:     0.8912               │  │
│  │  Pair: [EUR/USD ▼]   │  │  Max:     0.9456               │  │
│  │                      │  │  Average: 0.9234               │  │
│  │  ┌────────────────┐  │  │  % Change: +2.15%             │  │
│  │  │                │  │  │  Data Points: 365             │  │
│  │  │   LINE CHART   │  │  │                                │  │
│  │  │                │  │  │  7-Day MA: 0.9221              │  │
│  │  └────────────────┘  │  │  30-Day MA: 0.9198             │  │
│  │                      │  │                                │  │
│  └──────────────────────┘  └────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Conversion History (last 10)          [Export CSV]       │   │
│  │  100 USD → EUR (0.9235) — Aug 25, 2026 10:30 AM         │   │
│  │  50 GBP → JPY (189.42) — Aug 25, 2026 10:28 AM         │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 JavaScript API Interaction
```javascript
// Example: Fetch conversion
const response = await fetch('/api/convert?from=USD&to=EUR&amt=100');
const data = await response.json();
// data = { from: "USD", to: "EUR", original: 100, converted: 92.35, rate: 0.9235 }

// Example: Fetch historical rates
const histResponse = await fetch('/api/historical?pair=EUR_USD&from=2024-01-01&to=2024-12-31');
const histData = await histResponse.json();
// histData = { pair: "EUR_USD", rates: [{date: "2024-01-01", rate: 0.905}, ...] }

// Example: Fetch stats
const statsResponse = await fetch('/api/stats?pair=EUR_USD&from=2024-01-01&to=2024-12-31');
const statsData = await statsResponse.json();
// statsData = { min: 0.89, max: 0.95, avg: 0.92, percentChange: 2.15, points: 365 }
```

### 5.4 Frontend Features
1. **Currency Converter** — Select from/to currencies, enter amount, get instant conversion
2. **Historical Line Chart** — Interactive chart with zoom/pan (Chart.js plugins)
3. **Statistics Panel** — Min, max, average, percent change, moving averages
4. **Date Range Picker** — Native HTML5 `<input type="date">` (no library needed)
5. **Conversion History** — Stored in `localStorage`, displayed as a list, exportable to CSV
6. **Favorites** — Star button to save preferred currency pairs (localStorage)
7. **Responsive Design** — Works on desktop, tablet, and mobile

---

## 6. Project Directory Structure

```
currency-converter-dashboard/
├── CMakeLists.txt                  # Top-level CMake config
├── README.md                       # Setup instructions
├── data/
│   └── exchange_rates.csv          # Kaggle dataset (user downloads)
├── server/
│   ├── CMakeLists.txt
│   ├── main.cpp                    # Entry point
│   ├── csv_parser.h
│   ├── csv_parser.cpp
│   ├── rate_engine.h
│   ├── rate_engine.cpp
│   ├── stats_engine.h
│   ├── stats_engine.cpp
│   ├── api_routes.h
│   ├── api_routes.cpp
│   └── models.h
├── frontend/
│   ├── index.html
│   ├── css/
│   │   ├── style.css
│   │   └── responsive.css
│   └── js/
│       ├── app.js
│       ├── chart.js
│       └── utils.js
├── build/                          # CMake build output (gitignored)
└── docs/
    └── reconfiguration_plan.md     # This file
```

---

## 7. Build & Run Instructions

```bash
# 1. Place Kaggle CSV in data/exchange_rates.csv

# 2. Build the C++ backend
mkdir build && cd build
cmake ..
make

# 3. Run the server
./currency_dashboard
# Server starts on http://localhost:8080
# Serves frontend from ../frontend/ directory

# 4. Open browser
# Navigate to http://localhost:8080
```

---

## 8. Implementation Phases

### Phase 1: C++ Backend Foundation (Days 1-3)
- [ ] Set up CMake project structure
- [ ] Implement CSV parser (read header, parse rows, build in-memory index)
- [ ] Implement rate engine (conversion formula, rate lookup)
- [ ] Set up HTTP server (cpp-httplib or Crow)
- [ ] Create `/api/currencies` endpoint
- [ ] Create `/api/convert` endpoint
- [ ] Test with curl: `curl "http://localhost:8080/api/convert?from=USD&to=EUR&amt=100"`

### Phase 2: Statistics & Historical Data (Days 4-5)
- [ ] Implement date range filtering
- [ ] Implement stats engine (min, max, avg, % change)
- [ ] Implement moving average computation
- [ ] Create `/api/historical` endpoint
- [ ] Create `/api/stats` endpoint
- [ ] Create `/api/moving-average` endpoint
- [ ] Test all endpoints with curl

### Phase 3: Frontend — HTML/CSS (Days 6-7)
- [ ] Build `index.html` with semantic structure
- [ ] Style with CSS (grid/flexbox layout, responsive design)
- [ ] Create currency selection dropdowns
- [ ] Create amount input + convert button
- [ ] Create chart container
- [ ] Create statistics panel
- [ ] Create conversion history list

### Phase 4: Frontend — JavaScript (Days 8-9)
- [ ] Implement `app.js` — fetch currencies on load, populate dropdowns
- [ ] Implement conversion flow (form submit → API call → display result)
- [ ] Implement Chart.js integration (historical line chart)
- [ ] Implement stats display (fetch + render)
- [ ] Implement date range picker interaction
- [ ] Implement localStorage for history and favorites
- [ ] Implement CSV export functionality

### Phase 5: Polish & Testing (Day 10)
- [ ] Error handling (missing CSV, empty date ranges, network errors)
- [ ] Loading states and UI feedback
- [ ] Responsive testing (mobile/tablet/desktop)
- [ ] Cross-browser testing (Chrome, Firefox, Safari)
- [ ] Performance testing (large CSV files)
- [ ] Write setup documentation

---

## 9. C++ Library Choices (Pick One)

| Library        | Type              | Pros                                      | Cons                          |
|----------------|-------------------|-------------------------------------------|-------------------------------|
| `cpp-httplib`  | Single-header HTTP | Zero dependencies, easy to integrate      | Newer, less battle-tested     |
| `Crow`         | Full HTTP framework | Flask-like API, well-documented           | Requires Boost (or standalone)|
| `Boost.Beast`  | Low-level HTTP    | Battle-tested, high performance           | Verbose, steep learning curve |
| **Recommendation** | `cpp-httplib` | Simplest setup, single `#include`, MIT license | —                    |

---

## 10. Key Differences from Original Java+C++ Design

| Aspect              | Original (Java+C++)               | New (HTML/CSS/JS+C++)               |
|---------------------|------------------------------------|--------------------------------------|
| UI Framework        | JavaFX (desktop)                   | HTML/CSS/JS (browser)                |
| Communication       | JNI (in-process)                   | HTTP REST API (JSON)                 |
| Deployment          | Requires JVM + native lib          | Browser + single binary server       |
| Charting            | JavaFX LineChart                   | Chart.js or custom SVG               |
| Persistence         | Java Preferences                   | localStorage (browser) + no DB       |
| Data Loading        | JNI calls from Java                | HTTP GET requests from JS            |
| Build               | Maven + CMake                      | CMake only                           |
| Portability         | JVM-dependent                      | Any modern browser                   |

---

## 11. Risks & Mitigations

| Risk                                      | Mitigation                                              |
|-------------------------------------------|---------------------------------------------------------|
| Kaggle CSV format varies widely           | Build a flexible CSV parser; document expected format    |
| C++ HTTP server complexity                | Use header-only `cpp-httplib` — minimal boilerplate     |
| Chart.js CDN unavailable offline          | Bundle Chart.js locally in `frontend/js/vendor/`        |
| Large CSV files (>100MB) slow startup     | Stream-parse on startup; consider mmap for very large    |
| CORS issues during development            | Server serves both API and frontend — no CORS needed     |
| Date format inconsistencies in dataset    | Normalize to ISO 8601 during CSV parsing                |

---

## 12. Success Criteria

- [ ] C++ backend serves all API endpoints correctly
- [ ] Frontend displays currency converter with real results from CSV data
- [ ] Historical line chart renders accurately for any date range
- [ ] Statistics panel shows correct min/max/avg/%change
- [ ] Moving averages compute correctly (7-day, 30-day)
- [ ] Conversion history persists across page reloads (localStorage)
- [ ] Export to CSV works correctly
- [ ] Application runs on macOS, Linux, and Windows
- [ ] No database required — all data from CSV file
- [ ] Clean, responsive UI on all screen sizes
