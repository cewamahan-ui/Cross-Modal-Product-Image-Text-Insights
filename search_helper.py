#!/usr/bin/env python3
"""search_helper.py - text query -> top-k SKUs (the "query to images" helper).

Query text is scored against each SKU's SIDECAR TAGS (the image side of the
join), so this is a text-query-to-images search with tags standing in for
image embeddings. Reuses lab-bow-v1 - same encoder, same honesty.

TOY RECALL COMMENT (read before quoting any number):
    The recall check below runs 2 hand-picked queries on the 4-SKU teaching
    slice and prints Recall@1. n_queries=2 and n_skus=4 make this a SMOKE
    TEST that the ranking path works, not a benchmark. Never quote it as
    retrieval performance - Week 10 has no traffic sample to measure on.

Quirk worth knowing (and saying out loud): a query for "kiondo" legitimately
ranks NK-99 high, because NK-99's PHOTO is a kiondo - that is the whole
teaching mismatch. The gold pair is about title-vs-photo, not about search.

Run:  python search_helper.py [query] [-k N]
      (no args -> runs the toy recall set, writes outputs/search_example.json)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mismatch import ROOT, lab_bow_agreement, load_catalog, load_sidecar

OUT_PATH = ROOT / "outputs" / "search_example.json"

# query -> SKU that must rank first for the toy recall check
TOY_QUERIES = {
    "blue enamel pot": "THD-02",
    "sisal tote bag": "KND-01",
}


def search(query: str, k: int = 3) -> list[dict]:
    """Rank SKUs by agreement(query, sidecar tags); image side = tags proxy."""
    catalog = load_catalog()
    scored = []
    for sku in catalog["skus"]:
        tags = load_sidecar(sku["tags_sidecar"])["tags"]
        scored.append({
            "sku": sku["sku"],
            "title": sku["title"],
            "score": round(lab_bow_agreement(query, tags), 4),
        })
    scored.sort(key=lambda r: (-r["score"], r["sku"]))
    return scored[:k]


def toy_recall(k: int = 1) -> dict:
    """Recall@k over the toy query set. SMOKE TEST ONLY - see module docstring."""
    hits, detail = 0, {}
    for query, expected in TOY_QUERIES.items():
        ranked = search(query, k=10)
        rank = next(i for i, r in enumerate(ranked, start=1) if r["sku"] == expected)
        hit = rank <= k
        hits += int(hit)
        detail[query] = {
            "expected": expected, "rank": rank, f"hit@{k}": hit,
            "top": ranked[:3],
        }
    return {
        "metric": f"Recall@{k}",
        "value": round(hits / len(TOY_QUERIES), 4),
        "hits": hits,
        "n_queries": len(TOY_QUERIES),
        "n_skus": len(load_catalog()["skus"]),  # teaching slice
        "comment": "TOY: 2 hand-picked queries over 4 fixture SKUs - a smoke "
                   "test of the ranking path, NOT a benchmark. Do not quote "
                   "this as Recall@k performance.",
        "detail": detail,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="text query -> top-k SKUs")
    parser.add_argument("query", nargs="?", help="free-text query")
    parser.add_argument("-k", type=int, default=3, help="top-k (default 3)")
    args = parser.parse_args()

    if args.query:
        for i, row in enumerate(search(args.query, args.k), start=1):
            print(f"{i}. {row['sku']:<8} score={row['score']:.4f}  {row['title']}")
        return 0

    recall = toy_recall(k=1)
    payload = {
        "generated_by": "search_helper.py",
        "mode": "toy recall set",
        "recall": recall,
    }
    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"{recall['metric']} = {recall['value']} "
          f"({recall['hits']}/{recall['n_queries']} queries over "
          f"{recall['n_skus']} SKUs) -- {recall['comment']}")
    for query, d in recall["detail"].items():
        print(f"  {query!r}: expected {d['expected']} @rank {d['rank']} -> "
              f"{'HIT' if d[f'hit@1'] else 'MISS'}")
    print(f"search example -> {OUT_PATH.relative_to(ROOT)}")
    return 0 if recall["hits"] == recall["n_queries"] else 1


if __name__ == "__main__":
    sys.exit(main())
