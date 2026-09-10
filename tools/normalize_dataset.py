#!/usr/bin/env python3
"""normalize_dataset.py — convert a long-format forex CSV into the canonical
wide schema consumed by the ccd C++ core parser.

Input (long format, one row per currency per day):
    currency,base_currency,currency_name,exchange_rate,date
    ZWL,EUR,Zimbabwean Dollar,376.341805,2026-08-23

Output (wide format, ascending ISO dates):
    Date,EUR,USD,JPY,...
    2026-08-23,1,0.8472,128.41,...

Design notes
------------
* The native base of the source file is PRESERVED by default (no rebasing).
  Cross-rate math rate(A->B) = col[B]/col[A] is invariant to the base, and
  keeping the native base avoids dropping dates where the would-be pivot
  currency has no quote (e.g. USD on Sundays).
* Rate tokens are copied verbatim (no float round-trip) unless --base forces
  arithmetic, so scientific notation like 1.5082909e-05 survives untouched.
* A constant "1" column is emitted for the base currency itself so the C++
  engine can treat every listed currency uniformly.

Usage
-----
    python3 tools/normalize_dataset.py daily_forex_rates.csv data/exchange_rates.csv
    python3 tools/normalize_dataset.py daily_forex_rates.csv data/sample_rates.csv \
        --last-dates 40 --currencies EUR,USD,GBP,JPY,INR,AUD,CAD,CHF
"""

import argparse
import csv
import sys
import time
from collections import defaultdict
from typing import NoReturn

EXPECTED_HEADER = ["currency", "base_currency", "currency_name", "exchange_rate", "date"]
DESCRIPTION = "Convert long-format forex CSV into the canonical wide schema for the ccd core."


def fail(msg: str) -> NoReturn:
    sys.exit(f"ERROR: {msg}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=DESCRIPTION)
    p.add_argument("input", help="long-format source CSV")
    p.add_argument("output", help="canonical wide CSV to write")
    p.add_argument("--base", default=None, metavar="CODE",
                   help="rebase all rates to this currency (default: keep native base)")
    p.add_argument("--currencies", default=None, metavar="C1,C2,..",
                   help="keep only these currency codes (comma separated)")
    p.add_argument("--last-dates", type=int, default=None, metavar="N",
                   help="keep only the N most recent distinct dates")
    p.add_argument("--start-date", default=None, metavar="YYYY-MM-DD",
                   help="keep only dates >= this")
    p.add_argument("--max-date", default=None, metavar="YYYY-MM-DD",
                   help="keep only dates <= this")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    t0 = time.time()

    # ---- pass 1: stream input into date -> {currency: token} -------------
    table: dict[str, dict[str, str]] = defaultdict(dict)   # token = verbatim string
    bases: set[str] = set()
    duplicates = 0
    bad_rows = 0
    cells_in = 0

    try:
        fh = open(args.input, newline="", encoding="utf-8-sig")
    except OSError as e:
        fail(f"cannot open input: {e}")
        raise AssertionError("unreachable")  # narrow Optional for type checkers

    with fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header != EXPECTED_HEADER:
            fail(f"unexpected header {header}; expected {EXPECTED_HEADER}")

        for lineno, row in enumerate(reader, start=2):
            if len(row) != 5:
                bad_rows += 1
                continue
            cur, base, _name, rate_tok, date = (c.strip() for c in row)
            if not cur or not rate_tok or len(date) != 10 or date[4] != "-" or date[7] != "-":
                bad_rows += 1
                continue
            bases.add(base)
            slot = table[date]
            if cur in slot:
                duplicates += 1
                continue          # keep first occurrence, count the clash
            slot[cur] = rate_tok
            cells_in += 1

    if len(bases) > 1:
        fail(f"multiple base currencies found {sorted(bases)}; "
             f"this script expects one native base per file")

    native_base = next(iter(bases)) if bases else fail("no data rows found")
    pivot = args.base.upper() if args.base else native_base

    keep = None
    if args.currencies:
        keep = {c.strip().upper() for c in args.currencies.split(",") if c.strip()}
        keep.add(pivot)

    # ---- optional rebase arithmetic (only pass that converts floats) -----
    def maybe_rebase(date: str, cell: dict[str, str]) -> dict[str, str]:
        if pivot == native_base:
            return cell
        p_tok = cell.get(pivot)
        if not p_tok:
            return {}                       # whole date unusable without pivot
        p_val = float(p_tok)
        out = {}
        for cur, tok in cell.items():
            try:
                out[cur] = repr(float(tok) / p_val)
            except ValueError:
                pass                        # silently drop unparseable cell
        return out

    # ---- apply date/currency filters -------------------------------------
    dates = sorted(table.keys())
    if args.start_date:
        dates = [d for d in dates if d >= args.start_date]
    if args.max_date:
        dates = [d for d in dates if d <= args.max_date]
    if args.last_dates:
        dates = dates[-args.last_dates:]

    rows_out = 0
    cells_out = 0
    skipped_dates = 0
    coverage_by_year: dict[str, list[int]] = defaultdict(list)

    with open(args.output, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out, lineterminator="\n")

        codes = sorted({c for d in dates for c in table[d] if not keep or c in keep})
        if pivot not in codes:
            codes.insert(0, pivot)
        header_out = ["Date"] + codes
        w.writerow(header_out)

        for d in dates:
            cell = maybe_rebase(d, table[d])
            vals = []
            populated = 0
            for code in codes:
                if code == pivot:
                    vals.append("1")
                    populated += 1
                    continue
                tok = cell.get(code)
                if tok is None:
                    vals.append("")
                else:
                    vals.append(tok)
                    populated += 1
            if populated <= 1:              # only the pivot column -> dead row
                skipped_dates += 1
                continue
            w.writerow([d] + vals)
            rows_out += 1
            cells_out += populated
            coverage_by_year[d[:4]].append(populated)

    # ---- report -----------------------------------------------------------
    span = f"{dates[0]} .. {dates[-1]}" if dates else "n/a"
    print(f"source           : {args.input}")
    print(f"written          : {args.output}")
    print(f"native/pivot base: {native_base}/{pivot} ({'rebased' if pivot != native_base else 'kept'})")
    print(f"currencies       : {len(codes)} columns")
    print(f"dates            : {rows_out} rows, {span}"
          + (f" ({skipped_dates} dead dates skipped)" if skipped_dates else ""))
    print(f"cells            : {cells_out} populated (of {len(codes) * max(rows_out, 1)} possible)")
    if coverage_by_year:
        thinnest = min(coverage_by_year.items(), key=lambda kv: min(kv[1]))
        densest = max(coverage_by_year.items(), key=lambda kv: max(kv[1]))
        print(f"sparsest year    : {thinnest[0]} (min {min(thinnest[1])} currencies/day)"
              f"   densest year: {densest[0]} (max {max(densest[1])}/day)")
    if duplicates or bad_rows:
        print(f"data quality     : {duplicates} duplicate pairs kept-first, {bad_rows} malformed rows dropped")
    print(f"elapsed          : {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()
