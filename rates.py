#!/usr/bin/env python3
"""rates.py - honest flag rates for the Week 10 join.

Reads mismatch_report.json and writes rates.json with per-category AND
overall flag_rate. Every rate carries its denominator (n) and raw count -
"a rate without a denominator" is a No Marks error in the rubric, so n is
part of the shape of the file, not a comment.

Run:  python rates.py       (exit 0, writes rates.json)
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "mismatch_report.json"
RATES_PATH = ROOT / "rates.json"

HONESTY = (
    "n is a teaching slice: the three teaching SKUs plus one I added (n=4), "
    "fixtures only. Quote the denominator with every rate. Do not present "
    "these as SokoniHub market rates - there is no traffic sample here."
)


def rate(flags: int, n: int) -> dict:
    return {
        "flag_rate": round(flags / n, 4) if n else None,
        "flags": flags,
        "n": n,
        "caption": f"{flags} of {n} listings flagged",
    }


def build_rates() -> dict:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    rows = report["results"]
    by_cat: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        by_cat[row["category"]].append(row["flag"])

    flags_total = sum(1 for r in rows if r["flag"])
    return {
        "generated_by": "rates.py",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "mismatch_report.json",
        "scored_by": report.get("scored_by"),
        "threshold": report.get("threshold"),
        "n_total": len(rows),
        "flags_total": flags_total,
        "overall": rate(flags_total, len(rows)),
        "by_category": {
            cat: rate(sum(1 for f in flags if f), len(flags))
            for cat, flags in sorted(by_cat.items())
        },
        "honesty_note": HONESTY,
    }


def main() -> int:
    if not REPORT_PATH.exists():
        print("INPUT ERROR: run `python mismatch.py` first")
        return 2
    rates = build_rates()
    RATES_PATH.write_text(json.dumps(rates, indent=2) + "\n", encoding="utf-8")
    o = rates["overall"]
    print(f"overall flag_rate = {o['flag_rate']} ({o['caption']})")
    for cat, r in rates["by_category"].items():
        print(f"  {cat:<8} flag_rate = {r['flag_rate']} ({r['caption']})")
    print(f"rates -> {RATES_PATH.name}  [{rates['honesty_note'][:60]}...]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
