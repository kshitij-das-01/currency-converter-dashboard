# A — Data Pipeline (raw Kaggle export → canonical dataset)

This document is the single source of truth for **which CSV the project uses**, **how it's produced**, and **how to regenerate it when a newer dataset arrives**.

Requirements source: [`../PRD.md`](../PRD.md) §5 · Tool: [`tools/normalize_dataset.py`](../../tools/normalize_dataset.py) · Gate: [`scripts/verify_dataset.py`](../../scripts/verify_dataset.py)

---

## A.1 Which CSV does the project use?

> ### ✅ The app reads exactly ONE file: `data/exchange_rates.csv`
> Wide format · native EUR base · 174 currencies · 6,551 dates (2004-08-30 → 2026-08-23) · 4.6 MB

| File | Role | Who consumes it | In git? |
|------|------|-----------------|---------|
| `daily_forex_rates.csv` (repo root, 21.8 MB) | **Raw** Kaggle export — long format (`currency,base_currency,currency_name,exchange_rate,date`) | Only `tools/normalize_dataset.py` | ❌ gitignored |
| **`data/exchange_rates.csv`** (4.6 MB) | **Canonical** wide-format dataset — *the* project dataset | C++ core everywhere: `currency_server --data` locally, browser `fetch("data/exchange_rates.csv")` on GitHub Pages | ✅ |
| `data/sample_rates.csv` (3.1 KB) | Test/demo fixture — last 40 trading days × 8 majors (EUR, USD, GBP, JPY, INR, AUD, CAD, CHF) | Unit tests (doc 03), CI smoke suite (docs 07/09) | ✅ |

Never point the server or frontend at the raw file — it is long-format and 5× larger; the core parser expects only the canonical schema.

## A.2 Audited Dataset Facts

| Property | Value |
|----------|-------|
| Raw rows | 497,430 |
| Distinct currency codes | 174 (incl. BTC, XAU gold, XDR — kept intentionally) |
| Native base currency | **EUR** — single base, verified across all rows |
| Dates | 6,551 trading days, `2004-08-30` → `2026-08-23`, all unique |
| Duplicates / empty cells | 0 / 0 |
| Scientific notation | Present (BTC: `1.5082909e-05`) — tokens copied verbatim through the pipeline |
| Coverage shape | Sparse ramp: ~2 currencies/day (2004) → ~172/day (2025); blank cells are normal |
| Sunday quirk | USD has no quote on Sundays (~542 dates) — other currencies do |

## A.3 Decision Record — why the data is NOT rebased to USD

The PRD originally sketched a USD-base canonical schema. After auditing the real file, that was rejected:

| Consideration | Rebase to USD | Keep native EUR base ✅ |
|---|---|---|
| Conversion math | `rate(A→B) = col[B]/col[A]` | **Identical formula** — base is an internal pivot; UI/API never expose it |
| Date coverage | Loses all 542 dates without a USD quote (**mostly Sundays**) → weekly chart holes | Keeps all 6,551 dates |
| Precision | One extra float division per value | Rate tokens copied **verbatim** (no float round-trip; BTC exponents survive intact) |
| Pipeline complexity | Pivot + arithmetic + pivot-missing logic | Pure pivot |

If rebasing is ever wanted anyway: `python3 tools/normalize_dataset.py daily_forex_rates.csv out.csv --base USD` — expect the Sunday dates to disappear by design.

---

## A.4 Regeneration Procedure (updated/new dataset of the same type)

Run this whenever Kaggle publishes an updated export, or you download a fresh file of the same long format.

### Step 0 — Prerequisites
Python 3.8+ with stdlib only. Working directory = repo root.

### Step 1 — Replace the raw file
Overwrite the raw export at the repo root, keeping the exact name:

```bash
mv ~/Downloads/daily_forex_rates.csv daily_forex_rates.csv   # or cp
head -2 daily_forex_rates.csv   # header must be:
# currency,base_currency,currency_name,exchange_rate,date
```

The normalizer hard-fails if the header differs or multiple base currencies appear — that failure is your guard against silently ingesting a different schema.

### Step 2 — Regenerate the canonical dataset

```bash
python3 tools/normalize_dataset.py daily_forex_rates.csv data/exchange_rates.csv
```

Expected output shape:

```
native/pivot base: EUR/EUR (kept)
currencies       : 174 columns
dates            : 6551 rows, 2004-08-30 .. 2026-08-23
cells            : 502951 populated ...
elapsed          : <1s
```

Useful trims (all combinable):

```bash
--currencies EUR,USD,GBP,JPY,...   # keep listed codes (+pivot) only
--start-date 2015-01-01            # drop sparse early years entirely
--max-date 2026-08-23              # freeze the timeline at a date
--base USD                         # rebase (see A.3 trade-off)
```

### Step 3 — Regenerate the test fixture

```bash
python3 tools/normalize_dataset.py daily_forex_rates.csv data/sample_rates.csv \
    --last-dates 40 --currencies EUR,USD,GBP,JPY,INR,AUD,CAD,CHF
```

Keep the fixture tiny (≤ 50 KB) — unit tests and CI depend on it being stable and fast.

### Step 4 — Verify (mandatory gate)

```bash
python3 scripts/verify_dataset.py
```

Must print **ALL CHECKS PASSED**. The gate covers: ascending unique dates, constant EUR pivot column, no dead rows, verbatim token match against the raw source (sampled), cross-rate spot checks (`GBP→JPY`, `USD→INR`) computed independently from raw tokens, and reports Sunday-row count. Without the raw file present it still runs structural checks.

### Step 5 — Size & sanity budget

```bash
ls -lh data/*.csv        # exchange_rates.csv must stay ≤ 10 MB
```

Current actual: 4.6 MB (≈ 1–1.5 MB gzipped in transit via Pages CDN). If a future update blows past 10 MB, trim with `--start-date` / `--currencies` from Step 2 rather than shipping bloat.

### Step 6 — Commit & document

```bash
git add data/exchange_rates.csv data/sample_rates.csv data/CREDITS.md
git commit -m "chore(data): refresh dataset to <new-date-range>"
```

Update `data/CREDITS.md`: new "Retrieved" date, row/date counts if changed, and confirm the license note still holds. Pushing to `main` redeploys Pages automatically with the new data (doc 09).

### Troubleshooting

| Symptom | Cause → Fix |
|---|---|
| `unexpected header …` | New export changed column names/order → adapt `EXPECTED_HEADER` in the script + this doc together |
| `multiple base currencies found` | Export now mixes bases → split per base or pre-filter before running |
| Output > 10 MB | Trim scope (Step 2 flags) — never ship untrimmed |
| `verify_dataset.py` token mismatch | Normalizer edited or wrong input file → rerun Steps 2–3 fresh, check for manual edits to `data/` |
| Fewer currencies than expected | Check the script's "sparsest year" line; new exports may drop dead codes (e.g. VEF) — acceptable, note in CREDITS |

## A.5 How this feeds the rest of the build

| Consumer | Dependency on this pipeline |
|----------|------------------------------|
| Doc 03 — Core library | Golden fixture = `data/sample_rates.csv`; parser must accept blank cells + exponent tokens (§3.2 rules updated accordingly) |
| Doc 05 — WASM | Browser fetches `data/exchange_rates.csv` relative-path; 4.6 MB parse ≈ well inside the 3 s WASM budget |
| Doc 09 — Deployment | Deploy workflow copies `data/exchange_rates.csv` into the site; CI smoke suite runs against `data/sample_rates.csv` |
| Doc 10 — Maintenance | Monthly cadence includes optional dataset refresh via this procedure |

## ✅ Exit Checklist

- [ ] `data/exchange_rates.csv` exists, ≤ 10 MB, produced by the normalizer (never hand-edited)
- [ ] `data/sample_rates.csv` regenerated alongside any full refresh
- [ ] `python3 scripts/verify_dataset.py` prints ALL CHECKS PASSED
- [ ] `data/CREDITS.md` filled in: Kaggle URL + license + retrieval date
- [ ] Raw file stays untracked (`git status` clean of `daily_forex_rates.csv`)
