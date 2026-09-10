# Implementation Guide — Read Me First

This folder contains the **complete, ordered build plan** for the Currency Converter & Economic Dashboard — from an empty directory to a live public URL on GitHub Pages, plus long-term Git/GitHub maintenance practices.

**Requirements source:** [`../PRD.md`](../PRD.md) · **Architecture rationale:** [`../../RECONFIGURATION_PLAN.md`](../../RECONFIGURATION_PLAN.md)

## Reading Order

| # | Document | Covers | Milestone |
|---|----------|--------|-----------|
| 01 | [Setup & Prerequisites](01-setup-and-prerequisites.md) | Compilers, CMake, Emscripten SDK, editor, verification | M0 |
| A  | [Data Pipeline](A-data-pipeline.md) | `daily_forex_rates.csv` → canonical `data/exchange_rates.csv`; regeneration & verification gate | M0 |
| 02 | [Repository & Project Structure](02-repository-and-project-structure.md) | Git init, full tree, .gitignore, README, branch protection | M0 |
| 03 | [Core Library Implementation](03-core-library-implementation.md) | CSV parser, rate engine, stats engine, unit tests | M1 |
| 04 | [HTTP Server](04-http-server.md) | cpp-httplib REST API, JSON serialization, static file serving | M2 |
| 05 | [WebAssembly Module](05-wasm-module.md) | Emscripten bindings, JS loader, parity testing | M3 |
| 06 | [Frontend Implementation](06-frontend-implementation.md) | HTML/CSS/JS, Chart.js, api adapter, localStorage, export | M4 |
| 07 | [Testing & Quality](07-testing-and-quality.md) | Test strategy, curl suite, QA checklists, benchmarks | M5 |
| 08 | [Git Workflow](08-git-workflow.md) | Branching, conventional commits, PRs, tags, Dependabot | all |
| 09 | [Deployment to GitHub Pages](09-deployment-github-pages.md) | CI workflows, Pages deploy, Docker alternative path | M6 |
| 10 | [Maintenance & Roadmap](10-maintenance-and-roadmap.md) | Releases, changelog, backlog, repo upkeep | post-v1.0 |

## The Golden Thread (keep these consistent everywhere)

Every doc assumes these decisions. If you change one, change it everywhere:

| Decision | Value |
|----------|-------|
| Core namespace / lib target | `ccd` / `currency_core` |
| Canonical dataset path | `data/exchange_rates.csv` (app reads ONLY this) |
| Dataset schema | Wide format, native EUR base, ISO dates; blanks allowed (`Date,AED,...,EUR,...,USD,...`) |
| Raw source (gitignored) | `daily_forex_rates.csv` — long format Kaggle export; refresh via [A-data-pipeline](A-data-pipeline.md) §A.4 |
| Server binary | `currency_server`, default port `8080` |
| REST prefix | `/api`, JSON camelCase, errors `{ "error": { code, message } }` |
| WASM artifacts | `currency_core.js` / `currency_core.wasm`, global `CurrencyCore` |
| localStorage keys | `ccd.history.v1`, `ccd.favorites.v1`, `ccd.settings.v1` |
| Versioning | SemVer; first release tag `v1.0.0` |

## Build Modes at a Glance

```bash
# Native server (dev/API):        # WASM for GitHub Pages:
cmake -S . -B build               emcmake cmake -S . -B build-wasm \
cmake --build build                 -DCMAKE_BUILD_TYPE=Release
./build/server/currency_server    cmake --build build-wasm
```

Each document ends with a **✅ Exit checklist** — do not move on until every box passes.
