#!/usr/bin/env python3
"""mismatch.py - SokoniHub cross-modal catalog join (Week 10 capstone).

Joins each SKU's listing TEXT (title + description) against the IMAGE side
(sidecar tags standing in for a vision tagger) and scores agreement.

Official encoder: **lab-bow-v1** - a bag-of-words encoder over the joined
vocabulary. Pure Python, offline, deterministic. It is the encoder that
produces every score in mismatch_report.json, and encoder_pin.json pins its
source hash so the pin can be checked against reality.

Optional cross-check: **CLIP** (sentence-transformers/clip-ViT-B-32 at the
revision pinned in encoder_pin.json) encodes the fixture PNG vs the listing
text. `--with-clip` records those scores as an INFORMATIONAL column plus
embeddings in encode_cache/. CLIP never writes the official score column.

Usage:
    python mismatch.py               # official scores -> mismatch_report.json
    python mismatch.py --with-clip   # + live CLIP cross-check -> encode_cache/

Exit codes:
    0  gold pair passes (KND-01 clear, NK-99 flagged)
    1  gold pair fails or the encoder pin is stale
    2  input error (missing catalog / sidecar)
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "catalog.json"
REPORT_PATH = ROOT / "mismatch_report.json"
PIN_PATH = ROOT / "encoder_pin.json"
GOLD_PATH = ROOT / "gold" / "expected.json"
ENCODE_CACHE = ROOT / "encode_cache"

# Threshold chosen on the teaching slice only (n=4). The gap in the gold pair
# is wide (NK-99 = 0.136, KND-01 = 0.554) so 0.35 sits mid-gap. Do NOT quote
# this threshold as tuned for production traffic - there is none here.
THRESHOLD = 0.35

TOKEN_RE = re.compile(r"[a-z0-9]+")


# --------------------------------------------------------------------------
# lab-bow-v1  (the official scorer - keep this function stable, it is pinned)
# --------------------------------------------------------------------------
def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens. No stemming, no synonyms (see vocab_gaps)."""
    return TOKEN_RE.findall(text.lower())


def lab_bow_agreement(title_desc: str, tags: list[str]) -> float:
    """lab-bow-v1: cosine(BoW(title+description), BoW(sidecar tags)) in [0, 1].

    1.0 = the words agree completely, 0.0 = no shared words. Flagging is
    `agreement < THRESHOLD` - a low score means the photo tags and the
    listing text are talking about different things.
    """
    a = Counter(tokenize(title_desc))
    b = Counter(tokenize(" ".join(tags)))
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def encoder_source_sha256() -> str:
    """sha256 of this file's lab_bow_agreement source (CRLF normalised).

    This is what encoder_pin.json pins: change the encoder, the pin check
    fails closed. That is what "pin matches the encoder that scored" means.
    """
    src = inspect.getsource(lab_bow_agreement).replace("\r\n", "\n")
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# catalog loading
# --------------------------------------------------------------------------
def load_catalog() -> dict:
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(f"missing {CATALOG_PATH}")
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def load_sidecar(rel_path: str) -> dict:
    path = ROOT / rel_path
    if not path.exists():
        raise FileNotFoundError(f"missing sidecar {rel_path}")
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# optional live CLIP cross-check
# --------------------------------------------------------------------------
def clip_cross_check(skus: list[dict], pin: dict) -> dict:
    """Encode fixture image vs listing text with the pinned CLIP revision.

    Real local run (0 API calls). Failures are recorded, never hidden - the
    official lab-bow-v1 scores do not depend on this block.
    """
    cross = pin.get("cross_check", {})
    model_id = cross.get("hub_id", "sentence-transformers/clip-ViT-B-32")
    revision = cross.get("revision")
    try:
        from PIL import Image
        from sentence_transformers import SentenceTransformer
    except Exception as exc:  # pragma: no cover - depends on local env
        return {"ran": False, "model": model_id, "revision": revision,
                "error": f"{type(exc).__name__}: {exc}"}
    try:
        model = SentenceTransformer(model_id, revision=revision, device="cpu")
    except Exception as exc:  # pragma: no cover - network/cache dependent
        return {"ran": False, "model": model_id, "revision": revision,
                "error": f"{type(exc).__name__}: {exc}"}

    cross_threshold = cross.get("informational_threshold", 0.22)
    scores: dict[str, float] = {}
    embeddings: dict[str, dict] = {}
    for sku in skus:
        text = f"{sku['title']}. {sku['description']}"
        image = Image.open(ROOT / sku["image"]).convert("RGB")
        img_vec = model.encode([image], normalize_embeddings=True)[0]
        txt_vec = model.encode([text], normalize_embeddings=True)[0]
        scores[sku["sku"]] = round(float(img_vec @ txt_vec), 4)
        embeddings[sku["sku"]] = {
            "image_embedding": [round(float(x), 6) for x in img_vec],
            "text_embedding": [round(float(x), 6) for x in txt_vec],
            "image_sha256": file_sha256(ROOT / sku["image"]),
        }

    ENCODE_CACHE.mkdir(exist_ok=True)
    (ENCODE_CACHE / "clip_embeddings.json").write_text(
        json.dumps(embeddings, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "model": model_id,
        "revision": revision,
        "device": "cpu",
        "api_calls": 0,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cache_files": ["encode_cache/clip_embeddings.json"],
        "note": "CLIP cross-check only; mismatch_report.json official scores "
                "come from lab-bow-v1 (encoder_pin.json).",
    }
    (ENCODE_CACHE / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {
        "ran": True,
        "model": model_id,
        "revision": revision,
        "device": "cpu",
        "informational_threshold": cross_threshold,
        "scores": scores,
        "flagged_at_informational_threshold": {
            sku: score < cross_threshold for sku, score in scores.items()},
        "cache": "encode_cache/clip_embeddings.json",
        "disclaimer": "informational column only - not the official score",
    }


# --------------------------------------------------------------------------
# scoring + report
# --------------------------------------------------------------------------
def score_catalog(with_clip: bool = False) -> dict:
    catalog = load_catalog()
    pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))

    rows = []
    for sku in catalog["skus"]:
        sidecar = load_sidecar(sku["tags_sidecar"])
        tags = sidecar["tags"]
        agreement = lab_bow_agreement(
            f"{sku['title']} {sku['description']}", tags)
        rows.append({
            "sku": sku["sku"],
            "category": sku["category"],
            "agreement": round(agreement, 4),
            "flag": agreement < THRESHOLD,
            "tags": tags,
            "tag_sha256": file_sha256(ROOT / sku["tags_sidecar"]),
            "image": sku["image"],
        })

    report = {
        "generated_by": "mismatch.py",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "client": catalog.get("client"),
        "scored_by": pin.get("scorer", "lab-bow-v1"),
        "encoder_pin_sha256": file_sha256(PIN_PATH),
        "encoder_source_sha256": encoder_source_sha256(),
        "score_semantics": "agreement = cosine(BoW(title+description), "
                           "BoW(sidecar tags)); flag = agreement < threshold",
        "threshold": THRESHOLD,
        "n": len(rows),
        "catalog_sha256": file_sha256(CATALOG_PATH),
        "results": rows,
    }

    if with_clip:
        report["clip_cross_check"] = clip_cross_check(catalog["skus"], pin)
    else:
        report["clip_cross_check"] = {
            "ran": False,
            "error": "not requested (run: python mismatch.py --with-clip)",
        }

    report["gold_check"] = gold_check(rows)
    return report


def gold_check(rows: list[dict]) -> dict:
    expected = json.loads(GOLD_PATH.read_text(encoding="utf-8"))["expected"]
    by_sku = {r["sku"]: r for r in rows}
    detail, ok = {}, True
    for sku, exp in expected.items():
        if sku not in by_sku:
            detail[sku] = {"result": "MISSING", "expected": exp["flag"], "ok": False}
            ok = False
            continue
        got_flag = by_sku[sku]["flag"]
        row_ok = got_flag == exp["flag"]
        detail[sku] = {"result": "flagged" if got_flag else "clear",
                       "expected": "flagged" if exp["flag"] else "clear",
                       "agreement": by_sku[sku]["agreement"], "ok": row_ok}
        ok = ok and row_ok
    return {"pass": ok, "detail": detail}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SokoniHub catalog join")
    parser.add_argument("--with-clip", action="store_true",
                        help="also run the live CLIP cross-check (local, $0)")
    args = parser.parse_args(argv)

    try:
        report = score_catalog(with_clip=args.with_clip)
    except FileNotFoundError as exc:
        print(f"INPUT ERROR: {exc}")
        return 2

    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    pin_ok = report["encoder_source_sha256"] == pin.get("scorer_source_sha256")

    print(f"mismatch.py: n={report['n']}  threshold={THRESHOLD}  "
          f"scorer={report['scored_by']}  pin_ok={pin_ok}")
    for row in report["results"]:
        state = "FLAGGED" if row["flag"] else "clear"
        print(f"  {row['sku']:<8} agreement={row['agreement']:.3f}  {state}")
    if report["clip_cross_check"].get("ran"):
        cc = report["clip_cross_check"]
        print(f"  CLIP cross-check ran ({cc['model']} @ {cc['revision'][:12]}…):")
        for sku, score in cc["scores"].items():
            print(f"    {sku:<8} clip_agreement={score:.3f}")
    else:
        print(f"  CLIP cross-check: not run ({report['clip_cross_check'].get('error')})")

    gc = report["gold_check"]
    print("gold check:", "PASS" if gc["pass"] else "FAIL")
    for sku, d in gc["detail"].items():
        print(f"  {sku}: expected {d['expected']}, got {d['result']} "
              f"(agreement={d.get('agreement')}) -> {'OK' if d['ok'] else 'WRONG'}")
    print(f"report -> {REPORT_PATH.relative_to(ROOT)}")
    if not gc["pass"]:
        return 1
    return 0 if pin_ok else 1


if __name__ == "__main__":
    sys.exit(main())
