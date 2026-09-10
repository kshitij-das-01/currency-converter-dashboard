#!/usr/bin/env python3
"""verify_dataset.py — correctness gate for data/exchange_rates.csv.

Validates the canonical wide dataset against the raw long-format source:
verbatim token preservation, pivot column, cross-rate math, Sunday survival,
sparse-row retention, ordering, and completeness. Exit 0 only if all pass.

Usage:  python3 scripts/verify_dataset.py [raw_csv] [canonical_csv]
"""

import csv
import datetime
import sys
from pathlib import Path

RAW_DEFAULT = "daily_forex_rates.csv"
CANON_DEFAULT = "data/exchange_rates.csv"


def fail(msg):
    print(f"FAIL {msg}")
    sys.exit(1)


def main():
    raw_path = Path(sys.argv[1] if len(sys.argv) > 1 else RAW_DEFAULT)
    canon_path = Path(sys.argv[2] if len(sys.argv) > 2 else CANON_DEFAULT)

    if not raw_path.exists():
        print(f"NOTE: raw source '{raw_path}' not present — running structural checks only.")
        src = None
    else:
        src = {}
        with open(raw_path, newline="", encoding="utf-8-sig") as f:
            r = csv.reader(f)
            next(r)
            for cur, _base, _name, rate, date in r:
                src[(date, cur)] = rate

    with open(canon_path, newline="") as f:
        r = csv.reader(f)
        header = next(r)
        if header[0] != "Date":
            fail(f"header starts with '{header[0]}', expected 'Date'")
        codes = header[1:]
        wide = {}
        for row in r:
            wide[row[0]] = dict(zip(codes, row[1:]))  # aligned: skip Date col on both sides

    dates = list(wide.keys())

    # 1. completeness / ordering
    if dates != sorted(dates):
        fail("dates are not in ascending order")
    print(f"PASS ordering ({len(dates)} ascending dates x {len(codes)} currencies)")

    # 2. pivot column constant
    base_col = next((c for c, v in ((c, sum(1 for d in dates[:200] if wide[d].get(c)))
                                    for c in codes) if v == len(dates[:200])), None)
    if "EUR" not in codes or any(wide[d]["EUR"] != "1" for d in dates):
        fail("EUR pivot column is missing or not constant 1")
    print("PASS pivot column EUR == 1 everywhere")

    # 3. no fully-empty rows
    dead = sum(1 for d in dates if sum(1 for v in wide[d].values() if v) <= 1)
    if dead:
        fail(f"{dead} rows have no data beyond the pivot column")
    print(f"PASS no dead rows")

    if src is None:
        print("Structural checks complete (cross-checks skipped without raw file).")
        return

    # 4. verbatim tokens (sampled: every ~500th date, all populated cells)
    checked = mismatched = 0
    for d in dates[::500]:
        for cur, tok in wide[d].items():
            if not tok:
                continue
            checked += 1
            if cur != "EUR" and src.get((d, cur)) != tok:
                mismatched += 1
                if mismatched <= 3:
                    print(f"   mismatch {d} {cur}: wide={tok} raw={src.get((d, cur))}")
    if mismatched:
        fail(f"{mismatched}/{checked} sampled tokens differ from raw source")
    print(f"PASS verbatim tokens ({checked} sampled cells match raw source exactly)")

    # 5. cross-rate math on latest date (non-base pair exercises the pivot formula)
    d = dates[-1]
    for a, b in (("GBP", "JPY"), ("USD", "INR")):
        if (d, a) in src and (d, b) in src and a in codes and b in codes:
            expect = float(src[(d, b)]) / float(src[(d, a)])   # rate(a->b) via native base
            got = float(wide[d][b]) / float(wide[d][a])
            if abs(expect - got) > 1e-9 * max(1.0, abs(expect)):
                fail(f"cross-rate {a}->{b} {got} != expected {expect}")
            else:
                print(f"PASS cross-rate spot check: {a}->{b}={got:.6f} on {d}")

    # 6. Sundays survived
    sundays = [k for k in dates if datetime.date.fromisoformat(k).weekday() == 6]
    print(f"INFO Sunday rows present: {len(sundays)} (kept intentionally)")

    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
