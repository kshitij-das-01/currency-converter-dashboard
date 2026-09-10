# 02 — Repository & Project Structure

Goal: initialize Git, create the canonical directory tree, protect `main`, and make an empty-but-buildable skeleton pass CI.

## 2.1 Initialize the Repository

```bash
mkdir currency-converter-dashboard && cd currency-converter-dashboard
git init -b main
```

Create the GitHub remote (choose **Public** — required for free-account Pages hosting):

```bash
gh repo create currency-converter-dashboard --public --source=. --remote=origin
# …or create it on github.com and: git remote add origin git@github.com:<user>/currency-converter-dashboard.git
```

Configure identity if not already global:

```bash
git config user.name  "Your Name"
git config user.email "you@example.com"
```

Add community files now (MIT recommended for portfolio work): `LICENSE` (MIT), `.gitignore`, `README.md` (skeleton below), then first commit:

```bash
git add LICENSE .gitignore README.md docs/
git commit -m "chore: initial repository scaffold with PRD and implementation guides"
git push -u origin main
```

## 2.2 Canonical Directory Tree

This exact tree is assumed by every later document:

```
currency-converter-dashboard/
├── CMakeLists.txt                    # TOP-LEVEL build entry (doc 03 §3.0) — add_subdirectory() hub
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                    # build + test native target (doc 09)
│   │   └── deploy-pages.yml          # build WASM → deploy Pages    (doc 09)
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── dependabot.yml                # weekly Actions pin bumps      (doc 08)
├── core/                             # platform-independent C++17 library (doc 03)
│   ├── CMakeLists.txt
│   ├── include/ccd/
│   │   ├── models.h                  # RateSeries, ConversionResult, StatsResult…
│   │   ├── csv_parser.h
│   │   ├── rate_engine.h
│   │   └── stats_engine.h
│   ├── src/
│   │   ├── csv_parser.cpp
│   │   ├── rate_engine.cpp
│   │   └── stats_engine.cpp
│   └── tests/
│       ├── third_party/doctest.h
│       ├── test_csv_parser.cpp
│       ├── test_rate_engine.cpp
│       └── test_stats_engine.cpp
├── server/                           # native HTTP transport (doc 04)
│   ├── CMakeLists.txt
│   ├── third_party/httplib.h
│   ├── third_party/json.hpp
│   ├── main.cpp
│   └── api_routes.{h,cpp}
├── wasm/                             # Emscripten transport (doc 05)
│   ├── CMakeLists.txt
│   └── bindings.cpp
├── frontend/                         # static site (doc 06)
│   ├── index.html
│   ├── css/style.css
│   ├── js/{config.js, api.js, app.js, chart_panel.js, utils.js}
│   ├── vendor/chart.umd.min.js       # Chart.js v4, vendored (no CDN dependency)
│   └── wasm/                         # build output copied here (gitignored)
├── data/
│   ├── exchange_rates.csv            # full dataset ≤ 10 MB (or self-download)
│   ├── sample_rates.csv              # tiny fixture, always committed
│   └── CREDITS.md                    # dataset source + license attribution
├── tools/
│   └── normalize_dataset.py          # stdlib-only Kaggle → canonical converter
├── scripts/
│   ├── smoke_api.sh                  # curl suite                     (doc 07)
│   └── parity_test.mjs               # WASM vs REST golden comparison (doc 05)
├── docs/
│   ├── PRD.md
│   └── implementation/               # this folder
├── .gitignore
├── .gitattributes
├── LICENSE
└── README.md
```

## 2.3 `.gitignore` (complete)

```gitignore
# Build outputs
build/
build-wasm/
dist/
out/

# WASM artifacts are generated into frontend/wasm by deploy workflow
frontend/wasm/

# IDE / OS
.vscode/
.idea/
.DS_Store
Thumbs.db

# Large raw downloads kept locally only (commit normalized + sample, not this).
# Regenerate canonical data via tools/normalize_dataset.py — see data/CREDITS.md
/daily_forex_rates.csv
data/*.zip
data/raw_*

# Logs / temp
*.log
tmp/
```

`.gitattributes`:

```gitattributes
* text=auto
*.csv text eol=lf
*.sh text eol=lf
*.png binary
```

## 2.4 README Skeleton

Write this now; expand at release time (doc 10):

```markdown
# Currency Converter & Economic Dashboard

Convert between world currencies and analyze historical rate trends.
C++17 engine (native REST server + WebAssembly), vanilla HTML/CSS/JS frontend,
zero databases, zero servers to pay for.

[![CI](https://github.com/<user>/currency-converter-dashboard/actions/workflows/ci.yml/badge.svg)](…)

## Live demo
https://<user>.github.io/currency-converter-dashboard/

## Quick start (native server)
…filled in doc 04…

## Data
Dataset placed manually at data/exchange_rates.csv — see data/CREDITS.md.
```

## 2.5 Branch Protection (GitHub UI)

Repo → **Settings → Branches → Add rule** for `main`:

- ✅ Require a pull request before merging *(solo mode: set "required approvals" to 0 but keep PR requirement)*
- ✅ Require status checks: `build-test` (the CI job name from doc 09)
- ✅ Require linear history
- ❌ Do **not** allow force pushes / deletions

Also **Settings → General → Pull Requests**: enable "Automatically delete head branches".

## 2.6 First Skeleton Commit Sequence

Small, conventional commits from the very start (see [08](08-git-workflow.md)):

```
chore: initial repository scaffold with PRD and implementation guides
docs: add MIT license and repository README skeleton
chore: add gitignore/gitattributes and empty module directories
ci: bootstrap build-and-test workflow on ubuntu-latest
```

## ✅ Exit Checklist

- [ ] Repo exists on GitHub, public, remote wired up
- [ ] Tree from §2.2 created (empty dirs get placeholder files as they're built)
- [ ] `.gitignore`/`.gitattributes`/LICENSE/README committed
- [ ] Branch protection active; `main` is the only long-lived branch
- [ ] Skeleton pushed and visible on GitHub
