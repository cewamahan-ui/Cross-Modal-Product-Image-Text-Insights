#!/usr/bin/env python3
"""vocab_gaps.py - what lab-bow-v1's word-matching cannot see, with numbers.

Writes vocab_gaps.json: token coverage between listing text and sidecar
tags, the actual out-of-vocabulary gaps on this slice, and the declared
model limitations (no synonyms, no stemming, Swahili loanwords). The point
of the file is coverage HONESTY: say what the encoder misses before a
marker finds it.

Run:  python vocab_gaps.py      (exit 0, writes vocab_gaps.json)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from mismatch import ROOT, load_catalog, load_sidecar, tokenize

GAPS_PATH = ROOT / "vocab_gaps.json"

DECLARED_LIMITS = [
    "lab-bow-v1 matches exact tokens only: 'trainers' vs 'sneakers' scores 0 "
    "even if CLIP would align them (no synonymy).",
    "no stemming: 'woven' vs 'weave' are different tokens; 'kiondos' vs "
    "'kiondo' would split.",
    "Swahili loanwords only work if both sides spell them the same way "
    "(kiondo, sufuria, kikoi appear in fixtures as-is).",
    "out-of-vocabulary words still inflate the vector NORM, which pushes "
    "agreement DOWN - gaps create false flags, not silent passes.",
    "mitigation: CLIP cross-check (subword + visual matching) recorded in "
    "mismatch_report.json as an informational column; humans review flags "
    "before any seller sees them.",
]


def build_gaps() -> dict:
    catalog = load_catalog()
    text_tokens: set[str] = set()
    tag_tokens: set[str] = set()
    per_sku = []

    for sku in catalog["skus"]:
        tags = load_sidecar(sku["tags_sidecar"])["tags"]
        t = set(tokenize(f"{sku['title']} {sku['description']}"))
        g = set(tokenize(" ".join(tags)))
        text_tokens |= t
        tag_tokens |= g
        per_sku.append({
            "sku": sku["sku"],
            "text_only": sorted(t - g),
            "tags_only": sorted(g - t),
            "shared": sorted(t & g),
        })

    union = text_tokens | tag_tokens
    shared = text_tokens & tag_tokens
    coverage_text = round(len(shared) / len(text_tokens), 4) if text_tokens else None
    coverage_tags = round(len(shared) / len(tag_tokens), 4) if tag_tokens else None

    return {
        "generated_by": "vocab_gaps.py",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "encoder": "lab-bow-v1 (exact-token bag of words)",
        "n_skus": len(catalog["skus"]),
        "vocab_union_size": len(union),
        "text_vocab_size": len(text_tokens),
        "tag_vocab_size": len(tag_tokens),
        "coverage": {
            "text_tokens_seen_in_tags": coverage_text,
            "tag_tokens_seen_in_text": coverage_tags,
            "caption": f"{len(shared)} shared tokens of {len(text_tokens)} text / "
                       f"{len(tag_tokens)} tag tokens (teaching slice)",
        },
        "per_sku": per_sku,
        "example_gaps": {
            "text_only": sorted(text_tokens - tag_tokens)[:20],
            "tags_only": sorted(tag_tokens - text_tokens)[:20],
        },
        "declared_limits": DECLARED_LIMITS,
        "honesty_note": "coverage over n=4 fixture SKUs; a bigger catalog would "
                        "widen the vocabulary, not fix the synonym gap.",
    }


def main() -> int:
    gaps = build_gaps()
    GAPS_PATH.write_text(json.dumps(gaps, indent=2) + "\n", encoding="utf-8")
    c = gaps["coverage"]
    print(f"vocab: union={gaps['vocab_union_size']}  "
          f"text_seen_in_tags={c['text_tokens_seen_in_tags']}  "
          f"tags_seen_in_text={c['tag_tokens_seen_in_text']}")
    print(f"example text-only gaps: {gaps['example_gaps']['text_only'][:8]}")
    print(f"vocab_gaps -> {GAPS_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
