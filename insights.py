#!/usr/bin/env python3
"""insights.py - turn the join score into per-SKU seller insights.

Reads mismatch_report.json (scores are NEVER recomputed here - the pin owns
them), catalog.json (read-only) and optional audio/*.txt voice sidecars,
then writes insights.json:

    per sku: score, flag, seller_message (template), transcript (or null),
             privacy_flag (+matched terms), title copied READ-ONLY.

Title policy: this script never writes catalog.json. Seller copy lives in
its own field; a listing title can only be changed by a human in the
SokoniHub dashboard. tests/test_gold.py proves catalog.json is byte-identical
after a run - no silent title overwrite, ever.

Run:  python insights.py          (exit 0, writes insights.json)
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "catalog.json"
REPORT_PATH = ROOT / "mismatch_report.json"
INSIGHTS_PATH = ROOT / "insights.json"
AUDIO_DIR = ROOT / "audio"

# Privacy terms: if these appear in tags/title, a human must look before the
# insight is used - and no person/child imagery is ever generated for them.
PRIVACY_TERMS = {
    "person", "people", "face", "faces", "child", "children", "kid", "kids",
    "baby", "boy", "girl", "man", "woman", "men", "women", "selfie",
    "portrait", "human", "model", "personface",
}

CLEAR_TEMPLATE = (
    "Photo tags ({tags}) match your listing text - no action needed. "
    "Score {score} against threshold {threshold} (lab-bow-v1)."
)
FLAG_TEMPLATE = (
    "Please review before publishing: the photo tags ({tags}) do not agree "
    "with your title \"{title}\" (score {score} < threshold {threshold}). "
    "Either correct the title or re-shoot the photo. A human moderator sees "
    "this draft before the seller does."
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def privacy_check(text: str, tags: list[str]) -> tuple[bool, list[str]]:
    """Flag person/face/child content in tags or title. Case-insensitive."""
    haystack = set()
    for source in [text, " ".join(tags)]:
        for token in source.lower().replace("-", " ").split():
            haystack.add(token.strip(".,!?()\"'"))
    hits = sorted(haystack & PRIVACY_TERMS)
    return bool(hits), hits


def load_transcript(sku: str) -> dict | None:
    """Read a voice-note sidecar (declared fallback: no Whisper ran)."""
    path = AUDIO_DIR / f"{sku}.txt"
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    meta = {"sidecar": f"audio/{sku}.txt", "source": "hand-written sidecar (no Whisper run)"}
    for line in lines:
        if line.startswith("transcript:"):
            meta["text"] = line.split(":", 1)[1].strip()
        elif line.startswith("seller:"):
            meta["seller"] = line.split(":", 1)[1].strip()
    return meta


def build_insights() -> dict:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    scores = {r["sku"]: r for r in report["results"]}

    items = []
    for sku in catalog["skus"]:
        row = scores[sku["sku"]]
        sidecar = json.loads((ROOT / sku["tags_sidecar"]).read_text(encoding="utf-8"))
        tags = sidecar["tags"]
        title = sku["title"]
        flagged = row["flag"]
        score = row["agreement"]

        if flagged:
            message = FLAG_TEMPLATE.format(
                tags=", ".join(tags), title=title, score=score,
                threshold=report["threshold"])
        else:
            message = CLEAR_TEMPLATE.format(
                tags=", ".join(tags), score=score, threshold=report["threshold"])

        privacy_flag, hits = privacy_check(f"{title} {sku['description']}", tags)
        items.append({
            "sku": sku["sku"],
            "category": sku["category"],
            "score": score,
            "flag": flagged,
            "seller_message": message,
            "privacy_flag": privacy_flag,
            "privacy_terms_matched": hits,
            "transcript": load_transcript(sku["sku"]),
            "title": title,                       # copied read-only
            "title_source": "catalog.json (read-only)",
            "title_rewritten": False,             # this tool never edits titles
            "tags": tags,
        })

    return {
        "generated_by": "insights.py",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "client": catalog.get("client"),
        "n": len(items),
        "scored_by": report.get("scored_by"),
        "threshold": report.get("threshold"),
        "source_report": "mismatch_report.json",
        "source_report_sha256": sha256_file(REPORT_PATH),
        "title_policy": "scores and copy only; no script in this repo writes "
                        "listing titles back to catalog.json",
        "items": items,
    }


def main() -> int:
    if not REPORT_PATH.exists():
        print("INPUT ERROR: run `python mismatch.py` first (missing mismatch_report.json)")
        return 2
    catalog_bytes = CATALOG_PATH.read_bytes()
    insights = build_insights()
    INSIGHTS_PATH.write_text(json.dumps(insights, indent=2) + "\n", encoding="utf-8")
    assert CATALOG_PATH.read_bytes() == catalog_bytes, "catalog.json changed - overwrite bug"

    flagged = sum(1 for i in insights["items"] if i["flag"])
    with_transcript = sum(1 for i in insights["items"] if i["transcript"])
    print(f"insights.py: n={insights['n']}  flagged={flagged}  "
          f"transcripts={with_transcript}  privacy_flags="
          f"{sum(1 for i in insights['items'] if i['privacy_flag'])}")
    for item in insights["items"]:
        state = "FLAG" if item["flag"] else "ok  "
        print(f"  {item['sku']:<8} {state} score={item['score']:.3f}  "
              f"msg_chars={len(item['seller_message'])}")
    print(f"catalog.json unchanged (sha256 {sha256_file(CATALOG_PATH)[:12]}...)")
    print(f"insights -> {INSIGHTS_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
