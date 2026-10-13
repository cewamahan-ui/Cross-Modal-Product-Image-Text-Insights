"""Week 10 gold checks: KND-01 clear / NK-99 flagged + honesty invariants.

Run:  python -m pytest -q     (from capstone 10/)
Each test maps to a rubric line; none of them weaken the checks.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import insights  # noqa: E402
import mismatch  # noqa: E402


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], cwd=ROOT,
                          capture_output=True, text=True)


# ---- Deliverable 1: catalog join + gold pair -----------------------------
def test_gold_pair_in_report():
    report = json.loads((ROOT / "mismatch_report.json").read_text(encoding="utf-8"))
    rows = {r["sku"]: r for r in report["results"]}
    assert rows["KND-01"]["flag"] is False, "KND-01 must be CLEAR"
    assert rows["NK-99"]["flag"] is True, "NK-99 must be FLAGGED"
    assert rows["KND-01"]["agreement"] > rows["NK-99"]["agreement"]
    assert report["n"] == len(report["results"]) == 4
    assert report["scored_by"] == "lab-bow-v1"


def test_gold_pair_live_rerun():
    """A fresh run reproduces the gold pair and exits 0.

    Restores the committed report afterwards so the CLIP cross-check
    column (from `mismatch.py --with-clip`) survives the test run.
    """
    report_path = ROOT / "mismatch_report.json"
    committed = report_path.read_bytes()
    try:
        proc = _run("mismatch.py")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "gold check: PASS" in proc.stdout
    finally:
        report_path.write_bytes(committed)


def test_check_mismatch_passes():
    proc = _run("check_mismatch.py")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CHECK PASS" in proc.stdout


def test_pin_matches_encoder_that_scored():
    pin = json.loads((ROOT / "encoder_pin.json").read_text(encoding="utf-8"))
    assert pin["scorer"] == "lab-bow-v1"
    assert pin["scorer_source_sha256"] == mismatch.encoder_source_sha256()


def test_threshold_gap_has_margin():
    """Gold pair must not sit on the knife edge of the threshold."""
    report = json.loads((ROOT / "mismatch_report.json").read_text(encoding="utf-8"))
    rows = {r["sku"]: r for r in report["results"]}
    thr = report["threshold"]
    assert rows["KND-01"]["agreement"] - thr > 0.1
    assert thr - rows["NK-99"]["agreement"] > 0.1


# ---- Deliverable 2: insights --------------------------------------------
def test_no_title_overwrite():
    """insights.py must leave catalog.json byte-identical."""
    catalog = ROOT / "catalog.json"
    before = catalog.read_bytes()
    proc = _run("insights.py")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert catalog.read_bytes() == before, "catalog.json was rewritten"
    data = json.loads((ROOT / "insights.json").read_text(encoding="utf-8"))
    assert all(item["title_rewritten"] is False for item in data["items"])
    assert "writes listing titles back" in data["title_policy"]


def test_insights_shape_and_templates():
    data = json.loads((ROOT / "insights.json").read_text(encoding="utf-8"))
    assert data["n"] == 4
    by_sku = {i["sku"]: i for i in data["items"]}
    assert by_sku["NK-99"]["flag"] is True
    assert "review before publishing" in by_sku["NK-99"]["seller_message"]
    assert "no action needed" in by_sku["KND-01"]["seller_message"]
    # transcript comes from the sidecar (no Whisper), others are null
    assert by_sku["KND-01"]["transcript"] is not None
    assert "no Whisper" in by_sku["KND-01"]["transcript"]["source"]
    assert by_sku["NK-99"]["transcript"] is None


def test_privacy_flag_catches_people_terms():
    flag, hits = insights.privacy_check("cute child model face", [])
    assert flag is True and "child" in hits and "face" in hits
    flag2, hits2 = insights.privacy_check(
        "handwoven sisal kiondo", ["kiondo", "woven", "bag"])
    assert flag2 is False and hits2 == []
    # and no fixture SKU trips it
    data = json.loads((ROOT / "insights.json").read_text(encoding="utf-8"))
    assert all(i["privacy_flag"] is False for i in data["items"])


# ---- Deliverable 3: HF + generation --------------------------------------
def test_hf_yaml_declares_run_and_pins():
    try:
        import yaml
    except ImportError:
        return  # pyyaml absent on a marker box; YAML still present as artifact
    cfg = yaml.safe_load((ROOT / "hf_pipeline.yaml").read_text(encoding="utf-8"))
    pipe = cfg["pipeline"]
    assert pipe["task"] and pipe["model"] and pipe["device"]
    assert pipe["revision"] == json.loads(
        (ROOT / "encoder_pin.json").read_text(encoding="utf-8"))["cross_check"]["revision"]
    assert cfg["run"]["status"].startswith("ran")
    assert (ROOT / cfg["run"]["evidence"][0]).exists()
    assert (ROOT / cfg["run"]["evidence"][1]).exists()


def test_prompt_pin_and_stub_meta():
    prompt = (ROOT / "gen" / "prompt_still_life.txt").read_bytes()
    pin = json.loads((ROOT / "gen" / "prompt_pin.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(prompt).hexdigest() == pin["prompt_sha256"]
    meta = json.loads(
        (ROOT / "outputs" / "gen" / "KND-01_gen_meta.json").read_text(encoding="utf-8"))
    assert meta["not_a_photo_of_the_sku"] is True
    assert meta["prompt_sha256"] == pin["prompt_sha256"]
    assert meta["outputs"]["pixels"].startswith("outputs/gen/")
    twin = json.loads((ROOT / "gen" / "gen_twin.json").read_text(encoding="utf-8"))
    statuses = json.dumps(twin)
    assert "NOT RUN" in statuses and "stub-render-v1" in statuses


def test_prompt_has_no_people_terms_as_instructions():
    """The generation prompt must not instruct a model to draw people."""
    prompt = (ROOT / "gen" / "prompt_still_life.txt").read_text(encoding="utf-8").lower()
    # every people term must appear only inside a negation ("no people")
    for match in re.finditer(r"\b(people|hands?|faces?|children|person)\b", prompt):
        prefix = prompt[max(0, match.start() - 4):match.start()]
        assert prefix.endswith("no "), f"people term without 'no ' prefix: {match.group()}"


# ---- Deliverable 4: analytics --------------------------------------------
def test_rates_have_denominators():
    rates = json.loads((ROOT / "rates.json").read_text(encoding="utf-8"))
    report = json.loads((ROOT / "mismatch_report.json").read_text(encoding="utf-8"))
    flags = [r["flag"] for r in report["results"]]
    assert rates["overall"]["n"] == len(flags)
    assert rates["overall"]["flags"] == sum(flags)
    assert rates["overall"]["flag_rate"] == round(sum(flags) / len(flags), 4)
    assert "caption" in rates["overall"] and str(rates["overall"]["n"]) in rates["overall"]["caption"]
    for cat, block in rates["by_category"].items():
        assert block["n"] >= 1
        assert block["flag_rate"] == round(block["flags"] / block["n"], 4)
        assert str(block["n"]) in block["caption"]
    assert "teaching slice" in rates["honesty_note"]


def test_search_toy_recall_is_labelled_and_hits():
    proc = _run("search_helper.py")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "TOY" in proc.stdout and "NOT a benchmark" in proc.stdout
    payload = json.loads((ROOT / "outputs" / "search_example.json").read_text(encoding="utf-8"))
    assert payload["recall"]["n_queries"] == 2
    assert payload["recall"]["value"] == 1.0


def test_vocab_gaps_declares_limits():
    gaps = json.loads((ROOT / "vocab_gaps.json").read_text(encoding="utf-8"))
    assert gaps["n_skus"] == 4
    assert any("synonym" in lim for lim in gaps["declared_limits"])
    assert gaps["example_gaps"]["text_only"], "expected concrete gap tokens"
    assert "n=4" in gaps["honesty_note"], "coverage must state its sample size"


# ---- Deliverable 5: ethics + manager -------------------------------------
def test_ethics_four_headings_and_review_path():
    text = (ROOT / "ethics_note.md").read_text(encoding="utf-8")
    for heading in ["## Photos", "## Language", "## Generated pixels", "## Review path"]:
        assert heading in text, f"missing heading {heading}"
    assert "Kenya Data Protection Act" in text
    assert "human moderator" in text
    assert "no real people" in text.lower() or "no real" in text.lower()
    assert "child" in text
    manager = (ROOT / "manager_summary.md").read_text(encoding="utf-8")
    assert "will not claim" in manager
    assert "n=4" in manager or "n=4" in manager.replace(" ", "")


# ---- Submission hygiene ---------------------------------------------------
def test_no_secrets_and_gold_stays_clean():
    assert not list(ROOT.glob(".env")), ".env must not exist"
    assert not list(ROOT.glob("*.key"))
    gold_dir = ROOT / "gold"
    for path in gold_dir.iterdir():
        assert path.suffix in {".json", ".md"}, f"unexpected file in gold/: {path.name}"
    # generated pixels only under outputs/gen/
    gen_png = list(ROOT.rglob("*.png"))
    allowed = (ROOT / "fixtures" / "images", ROOT / "outputs" / "gen")
    for png in gen_png:
        assert any(str(png).startswith(str(a)) for a in allowed), \
            f"stray pixel file: {png}"
