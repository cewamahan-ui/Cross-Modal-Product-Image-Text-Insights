#!/usr/bin/env python3
"""check_mismatch.py - fail-closed verifier for the Week 10 join.

Reads mismatch_report.json + gold/expected.json + encoder_pin.json and
checks, WITHOUT rescoring:
  1. gold pair   : KND-01 clear, NK-99 flagged (as the report says)
  2. pin honesty : encoder_pin.json's scorer_source_sha256 still matches
                   the lab_bow_agreement source in mismatch.py
  3. consistency : threshold in report == threshold in mismatch.py
  4. structure   : honest n, per-row agreement + flag, CLIP column
                   (if present) labelled as cross-check with pinned revision

Exit codes: 0 all checks pass, 1 any check fails, 2 missing input file.

Run:  python check_mismatch.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import mismatch

ROOT = Path(__file__).resolve().parent


def _load(path: Path) -> dict:
    if not path.exists():
        print(f"MISSING: {path.name}")
        raise SystemExit(2)
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    report = _load(ROOT / "mismatch_report.json")
    expected = _load(ROOT / "gold" / "expected.json")["expected"]
    pin = _load(ROOT / "encoder_pin.json")
    failures: list[str] = []

    # 1. gold pair -------------------------------------------------------
    by_sku = {r["sku"]: r for r in report.get("results", [])}
    for sku, exp in expected.items():
        row = by_sku.get(sku)
        if row is None:
            failures.append(f"gold: {sku} missing from report")
            continue
        want = "flagged" if exp["flag"] else "clear"
        got = "flagged" if row["flag"] else "clear"
        status = "OK" if want == got else "WRONG"
        print(f"[gold] {sku}: expected {want}, report says {got} -> {status}")
        if want != got:
            failures.append(f"gold: {sku} expected {want}, got {got}")

    # 2. pin honesty -----------------------------------------------------
    live_hash = mismatch.encoder_source_sha256()
    pinned = pin.get("scorer_source_sha256")
    pin_ok = pinned == live_hash
    print(f"[pin ] lab_bow_agreement source hash matches encoder_pin.json "
          f"({live_hash[:12]}…) -> {'OK' if pin_ok else 'STALE'}")
    if not pin_ok:
        failures.append("pin: scorer_source_sha256 does not match mismatch.py")
    if pin.get("scorer") != report.get("scored_by"):
        failures.append(f"pin: scorer {pin.get('scorer')!r} != report scored_by "
                        f"{report.get('scored_by')!r}")
        print(f"[pin ] scorer named in pin matches report scored_by -> WRONG")
    else:
        print(f"[pin ] scorer named in pin matches report scored_by -> OK")

    # 3. threshold consistency -------------------------------------------
    thr_ok = report.get("threshold") == mismatch.THRESHOLD
    print(f"[thr ] report threshold {report.get('threshold')} == "
          f"mismatch.py THRESHOLD {mismatch.THRESHOLD} -> {'OK' if thr_ok else 'DRIFT'}")
    if not thr_ok:
        failures.append("threshold drift between report and code")

    # 4. structure / honesty ---------------------------------------------
    n = report.get("n")
    rows = report.get("results", [])
    n_ok = isinstance(n, int) and n == len(rows) and n > 0
    print(f"[n   ] report n={n} matches {len(rows)} result rows -> {'OK' if n_ok else 'WRONG'}")
    if not n_ok:
        failures.append("n does not match result rows")
    for row in rows:
        if not isinstance(row.get("agreement"), (int, float)) or not isinstance(row.get("flag"), bool):
            failures.append(f"row {row.get('sku')} missing agreement/flag")

    cc = report.get("clip_cross_check", {})
    if cc.get("ran"):
        want_rev = pin.get("cross_check", {}).get("revision")
        rev_ok = cc.get("revision") == want_rev
        print(f"[clip] cross-check ran at pinned revision "
              f"{str(cc.get('revision'))[:12]}… -> {'OK' if rev_ok else 'WRONG'}")
        if not rev_ok:
            failures.append("clip cross-check revision does not match pin")
    else:
        print(f"[clip] not run ({cc.get('error', 'declared fallback')}) -> OK (declared)")

    if failures:
        print("\nCHECK FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nCHECK PASS: gold pair correct, pin honest, report consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
