# 07 — Testing & Quality

Goal: one coherent quality system across C++ core, REST API, WASM parity, and frontend UX. Covers PRD §8 NFRs, §10 acceptance · Milestone M5 · Day 10.

## 7.1 Test Pyramid

```
        ┌────────────────────┐
        │  Manual QA (7.5)   │            once per release
      ┌─┴────────────────────┴─┐
      │ Parity + API smoke     │           every push (CI)
    ┌─┴────────────────────────┴─┐
    │  Core unit tests (ctest)   │         every push (CI)
    └────────────────────────────┘
```

## 7.2 Unit Tests (already built in doc 03)

Gate for CI: `ctest --test-dir build --output-on-failure` green on ubuntu-latest + macos-latest.

Additional suites to add during M5 if not yet present:
- **Parser fuzz-ish loop:** feed truncated CSV lines (cut mid-cell) — must never crash, only increment `rowsSkipped`.
- **Date boundary tests:** query exactly at `dateMin`, exactly at `dateMax`, one day before/after.
- **Large-input perf test:** tagged, run manually per doc 03 §3.6.

## 7.3 API Smoke Suite (`scripts/smoke_api.sh`)

Bash + curl + `python3 -m json.tool` for assertions-free readability; exit non-zero on any failure:

```bash
#!/usr/bin/env bash
set -euo pipefail
BASE="${1:-http://localhost:8080}"
fail() { echo "FAIL: $1" >&2; exit 1; }

# healthz
curl -fsS "$BASE/healthz" | grep -q '"ok"' || fail "healthz"

# convert happy path → expect numeric result
RES=$(curl -fsS "$BASE/api/convert?from=USD&to=EUR&amount=100")
echo "$RES" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert abs(d["result"] - d["amount"]*d["rate"]) < 1e-4' || fail "convert math"

# error paths → expect exact codes
curl -fsS "$BASE/api/convert?from=XXX&to=EUR&amount=100" | grep -q UNKNOWN_CURRENCY || fail "unknown currency"
curl -fsS "$BASE/api/convert?from=USD&to=EUR&amount=-5"  | grep -q INVALID_AMOUNT   || fail "negative amount"
curl -fsS "$BASE/api/stats?from=EUR&to=GBP&start=2030-01-01&end=2040-01-01" | grep -q EMPTY_RANGE || fail "empty range"

echo "smoke suite passed"
```

Extend with: `/api/rate` last-known-date case, `/api/historical` point count vs expected days, `/api/moving-average` window validation (`window=1` → `BAD_WINDOW`).

CI runs it after starting the freshly-built server in the background.

## 7.4 WASM Parity Harness

Built in doc 05 §5.4 (`scripts/parity_test.mjs`). CI variant: build native server, start it, build WASM, run Node harness — all three steps in the deploy workflow before publishing (see doc 09). Minimum 20 seed cases covering happy paths + every error code on both transports.

## 7.5 Frontend QA Checklist (manual, per release)

Functional:
- [ ] Convert: USD→EUR, EUR→JPY, same-currency (rate 1.0), amount 0 rejected client-side, huge number formats cleanly
- [ ] Swap button flips pair without refetch errors
- [ ] Trends: full range, single-day range (chart shows 1 point), inverted dates blocked by input clamping
- [ ] MA toggle draws/removes overlay without axis glitches
- [ ] History caps at 50; export matches displayed rows; reload persistence works
- [ ] Favorites star toggles; chips reorder dropdowns after reload

States & robustness:
- [ ] Kill the REST server mid-session (MODE=rest) → panels show retry messages, no white screen
- [ ] Corrupt `data/sample_rates.csv` in wasm mode → parse error surfaced in header badge
- [ ] Private-browsing mode (localStorage throws) → app still functions, warns once

Accessibility & performance:
- [ ] Keyboard-only full walkthrough (tab order logical, Enter submits forms)
- [ ] Screen-reader announces result via `aria-live`
- [ ] Lighthouse ≥ 90 perf/a11y (Chrome, mobile profile)
- [ ] Layout spot-check at 360/768/1280 px

## 7.6 Performance Benchmarks (PRD §8 targets)

| Check | Target | Method |
|-------|--------|--------|
| Native CSV parse (10 MB) | < 800 ms | chrono benchmark binary |
| Native API p95 post-warmup | < 10 ms | `hey -z 5s -c 10 localhost:8080/api/stats…` or curl timing loop |
| WASM parse (10 MB) | < 3 s | `performance.now()` around `loadDataset`, logged in console (dev builds only) |
| FCP on Pages | < 1.5 s | Lighthouse |

Record results in the release PR description (doc 08 template).

## 7.7 CI Quality Gates Summary

| Gate | Runs when | Blocking? |
|------|-----------|-----------|
| ctest matrix (ubuntu+macos) | every push/PR | yes |
| smoke_api.sh | every push/PR (after server build) | yes |
| parity_test.mjs | every push/PR + pre-deploy | yes (deploy) |
| Lighthouse (optional job) | main pushes | report-only v1 |

## ✅ Exit Checklist

- [ ] All automated gates green locally AND in CI
- [ ] Manual QA checklist fully checked on the production-mode build (wasm)
- [ ] Benchmark numbers recorded; regressions > 20% investigated
