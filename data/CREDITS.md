# Dataset Credits & Provenance

## Files

| File | What | Committed to git? |
|------|------|-------------------|
| `data/exchange_rates.csv` (4.6 MB) | Canonical wide-format dataset consumed by the app. Pivoted from the raw source with `tools/normalize_dataset.py`. **Base currency: EUR (native).** | ✅ yes |
| `data/sample_rates.csv` (3.1 KB) | Test/demo fixture: last 40 trading days × 8 major currencies (EUR, USD, GBP, JPY, INR, AUD, CAD, CHF). Generated from the same source. | ✅ yes |
| `daily_forex_rates.csv` (21.8 MB, repo root) | Raw Kaggle export — long format (`currency,base_currency,currency_name,exchange_rate,date`), EUR base, 497,430 rows. | ✅ yes | 

## Source

- **Kaggle dataset:** Forex Exchange Rates Since 2004 (Updated Daily)
- **URL:** <https://www.kaggle.com/datasets/asaniczka/forex-exchange-rate-since-2004-updated-daily>
- **License:** *ODC Attribution License (ODC-By)*
- **Retrieved:** 2026-08-25

## Regeneration

```bash
python3 tools/normalize_dataset.py daily_forex_rates.csv data/exchange_rates.csv
python3 tools/normalize_dataset.py daily_forex_rates.csv data/sample_rates.csv \
    --last-dates 40 --currencies EUR,USD,GBP,JPY,INR,AUD,CAD,CHF
python3 scripts/verify_dataset.py     # must print PASS on all checks
```

## Documented Decisions

1. **Base currency stays EUR (no rebasing to USD).**
   Cross-rate math `rate(A→B) = col[B] / col[A]` is invariant to the base, but rebasing
   would require a USD quote on every date — and 542 dates (mostly **Sundays**, when FX
   markets are closed) have no USD rows. Rebasing would delete ~8% of all dates and punch
   weekly holes into every chart, for zero functional benefit. Keeping the native base
   also lets rate tokens be copied verbatim (no float round-trip), preserving values like
   BTC's `1.5082909e-05` exactly.
2. **Sparse early years are kept, blanks allowed.** Coverage ramps from ~2 currencies/day
   (2004) to ~172/day (2025). Blank cells mean "currency had no quote that day," not
   "drop the whole date."
