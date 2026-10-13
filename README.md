# Week 10: Advanced Multimodal AI (SokoniHub)

## Overview

SokoniHub (Module 4 client) needs listing photos and listing text joined
into one insight: `mismatch.py` scores every SKU's **image side**
(sidecar tags standing in for a vision tagger) against its **text side**
(title + description) and flags disagreement above a declared threshold
(0.35). The encoder that actually produced the scores is **lab-bow-v1**, a
small offline bag-of-words dual-encoder pinned by source hash in
`encoder_pin.json` - a real local **CLIP** run
(`sentence-transformers/clip-ViT-B-32` @ `327ab67…`) cross-checks it and
is recorded as an informational column, never as the official score. Per
SKU the system writes a score, a flag and a drafted seller message
(`insights.json`, one optional voice-note transcript from a sidecar, no
Whisper), honest flag rates (`rates.json`), a toy text→image search with
Recall@1 (`search_helper.py`), coverage gaps (`vocab_gaps.json`), and a
labelled **stub** generation path (no DALL-E key, no SD checkpoint, $0
total). Ethics and a manager summary are in `ethics_note.md` /
`manager_summary.md`.

## Encoder honesty

- `encoder_pin.json`: scorer = **lab-bow-v1**
  (`mismatch.py::lab_bow_agreement`, source sha256 `5beac5be2f25…`);
  `check_mismatch.py` re-hashes the live source and fails closed if they
  drift, so "pin matches the encoder that scored" is machine-checked, not
  claimed. Cross-check pin: `sentence-transformers/clip-ViT-B-32`
  revision `327ab6726d33c0e22f920c83f2ff9e4bd38ca37f`, cpu, 0 API calls.
- Did transformers run? **Yes** - CLIP loaded and encoded locally from the
  cached snapshot (`evidence/clip_crosscheck.log`,
  `encode_cache/manifest.json`) as an informational cross-check
  (KND-01 0.2746 > NK-99 0.1573, same direction as lab-bow-v1). Official
  `agreement`/`flag` columns are lab-bow-v1. **If you used tags instead
  of CLIP, say so: tags scored, CLIP cross-checked.** If you only have
  four SKUs, say so: n=4, teaching slice.

## Join

```bash
python mismatch.py               # scores + gold check -> mismatch_report.json (exit 0 = gold PASS)
python mismatch.py --with-clip   # + live CLIP cross-check -> encode_cache/
python check_mismatch.py         # verifier: gold pair + pin + threshold + honest n (exit 0/1)
```

- Gold pair result (`evidence/gold_check.log`): **KND-01 = clear
  (agreement 0.5539), NK-99 = FLAGGED (agreement 0.1361)** vs threshold
  0.35; THD-02 0.7467 clear, KNG-04 0.7107 clear; n=4.

## Insights

- Path: `insights.json` (written by `python insights.py`). Per SKU:
  `score`, `flag`, `seller_message` (two templates), `privacy_flag`,
  `transcript` (`audio/KND-01.txt` sidecar for KND-01, others `null`).
  Titles are read-only: `tests/test_gold.py::test_no_title_overwrite`
  proves `catalog.json` is byte-identical after a run - no silent title
  overwrite anywhere in this repo.

## Tools

- `hf_pipeline.yaml`: task `feature-extraction`, model
  `sentence-transformers/clip-ViT-B-32`, revision `327ab67…`, device
  `cpu`. **This ran** (`python mismatch.py --with-clip`) - real-run
  evidence in `evidence/clip_crosscheck.log` + `encode_cache/`, not
  YAML-only.
- DALL-E / SD / **stub** (circled: stub) - `gen/stub_render.py` drew
  `outputs/gen/KND-01_stub_still_life.png` with
  `outputs/gen/KND-01_gen_meta.json` carrying
  `not_a_photo_of_the_sku: true`. DALL-E (no key) and SD (no
  checkpoint) are named as hosted/OSS twins in `gen/gen_twin.json`; no
  checkpoint is faked.
- Model card: read + declared for the pretrained encoder - CLIP's Hub card
  at pinned revision `327ab67…`; `lab-bow-v1`'s "card" is this README's
  Encoder honesty section (what it scores, what it misses:
  `vocab_gaps.json`).
- Provenance path: `gen/prompt_still_life.txt` (prompt, no people terms)
  → sha256 `7556f494…` pinned in `gen/prompt_pin.json` →
  `gen/stub_render.py` refuses to render on pin mismatch → meta JSON
  records prompt hash + generator + timestamp. Same shape DALL-E would
  have written.

## Analytics

- `rates.json` (**quote n**): overall flag_rate **0.25 (1 of 4, n=4)**;
  bags 0.5 (1 of 2); kitchen 0.0 (0 of 1); home 0.0 (0 of 1). Every rate
  carries `flags`, `n` and a caption - teaching slice, not market data.
- Search: `python search_helper.py` → query → top-k SKUs over the image
  side (tags), toy **Recall@1 = 1.0 (2/2 hand-picked queries, n=4
  SKUs)** with the smoke-test-not-a-benchmark comment inline;
  output in `outputs/search_example.json`.
- `vocab_gaps.json`: union vocab 61 tokens, 32% of text tokens seen in
  tags / 90% of tag tokens seen in text, per-SKU gap lists, plus the
  declared limits (no synonyms, no stemming, Swahili loanwords, OOV
  pushes scores *down*).

## Ethics

- Link: [`ethics_note.md`](ethics_note.md) - four headings (Photos,
  Language, Generated pixels, Review path); privacy flag for
  person/face/child tags (0 triggered on fixtures); no real people or
  child photos anywhere; Kenya DPA 2019 nod on photos-as-personal-data.
- Review path in one sentence: flagged SKUs go to a named human
  moderator as a draft before any seller-facing message - no automated
  edit, no automated takedown.
- Manager version: [`manager_summary.md`](manager_summary.md) (risks,
  mitigations, what we will not claim).

## Fallbacks declared

- [x] no GPU / no transformers → **partially taken**: official scores are
  lab-bow-v1 over sidecar tags (stdlib-only, offline); CLIP ran locally
  on CPU as cross-check only. Delete `--with-clip` and everything still
  works.
- [x] no OpenAI image key → **taken**: `gen/stub_render.py` stub with the
  same meta JSON DALL-E would have written (`not_a_photo_of_the_sku`).
- [x] no Diffusers / SD → **taken**: SD named as OSS twin in
  `gen/gen_twin.json`, checkpoint **not** faked.
- [x] no Whisper → **taken**: `audio/KND-01.txt` hand-written sidecar,
  labelled "no Whisper ran" in the file itself.
- [x] no production catalog → **taken**: three teaching SKUs (KND-01,
  NK-99, THD-02) plus one I added (KNG-04); no marketplace crawl.
- [x] n is a teaching slice (n=4) → stated in every rate and in
  `rates.json::honesty_note`.
- [x] no live face crawls → fixtures are Pillow drawings; `gold/` holds
  expectations only, never pixels.

## Weeks 5 / 7 / 8 / 9 reuse

- **Week 5 (CLIP idea):** the dual-encoder retrieval idea and the same
  `clip-ViT-B-32` family from the AfyaPlus intake index now join a retail
  catalog instead of clinic photos - cross-check encoder here, tags-first
  scoring here.
- **Week 7 (payday cost):** cost discipline carried over - this capstone
  ran at **$0 / 0 API calls** (local CLIP, stub renderer), and the cost
  table below is quoted the way Week 7 quoted it.
- **Week 8 (pins):** the fail-closed pin pattern (prompt pin file +
  sha256 + refuse-to-run on drift) is reused for `encoder_pin.json`
  (encoder source hash) and `gen/prompt_pin.json` (generation prompt).
- **Week 9 (DPA):** Kenya Data Protection Act 2019 handling carries over -
  people in photos are personal data, privacy flag + human review path
  in `ethics_note.md`; AfyaPlus triage fixtures are **not** mixed into
  this catalog (stated in `catalog.json::note` and the ethics transfer
  note; AfyaPlus posters/leaflets are a later transfer).

## Cost and tooling

| Step | API calls | Cost |
|---|---|---|
| Join + rates on fixtures (`mismatch.py`, `rates.py`) | 0 | $0 |
| CLIP cross-check (local, cached snapshot) | 0 | $0 |
| Stub generation (`gen/stub_render.py`) | 0 | $0 |
| DALL-E still-life | 0 (not run - no key) | $0 (would be $0-0.20 for ≤5 images) |
| **Typical total this week** | **0** | **~$0** |

## Checklist

- [x] NK-99 flagged, KND-01 clear (`evidence/gold_check.log`,
      `python check_mismatch.py` exits 0)
- [x] `outputs/` not mixed into gold images/ - `gold/` contains
      expectations only (`gold/expected.json`), generated pixels live in
      `outputs/gen/`, fixtures in `fixtures/images/`
- [x] no unhackable claims - thresholds quoted as teaching-slice values,
      recall quoted as a smoke test, no "detects counterfeits" claim
- [x] Weeks 5/7/8/9 reuse documented (section above)
- [x] no secrets (`.gitignore` covers `.env`/keys; none exist - CLIP and
      stub both ran without credentials)
- [x] single repository: catalog, scores, insights, pins, ethics, this
      README with fallbacks

## Certification mapping (NCA-GENL-style: apply pretrained multimodal models, not logo drops)

- **Deliverables 1-2** (join, insights, pin): evidence for *applying* a
  pretrained or honest lab encoder to a real task with a metric
  (agreement score + threshold + gold check + pin).
- **Deliverable 3** (HF YAML / generation artifacts): evidence for
  *multimodal applications with provenance* - real local CLIP run or
  README-declared fallback, prompt hash pin, `not_a_photo_of_the_sku`
  meta, DALL-E/SD twin mapping.
- **Deliverable 4** (rates, search, vocab gaps): evidence you can
  *measure and explain* cross-modal behaviour with honest n (flag_rate
  with denominators, toy Recall@1 labelled as smoke test, declared
  vocabulary limits).
- **Deliverable 5** (ethics + manager): *responsible deployment* language
  a reviewer can repeat - four headings, review path, privacy flag, DPA
  nod, no overclaim.

## Project map

```
catalog.json            4 SKUs (3 teaching + KNG-04 added), fixtures only
mismatch.py             lab-bow-v1 scorer, threshold, report, gold check
check_mismatch.py       fail-closed verifier (gold + pin + threshold + n)
mismatch_report.json    scores, flags, CLIP cross-check column, gold result
encoder_pin.json        scorer source hash + CLIP revision pin
insights.py/.json       score/flag/seller_message/transcript/privacy_flag
rates.py / rates.json   per-category + overall flag_rate with honest n
search_helper.py        text query -> top-k, toy Recall@1 comment
vocab_gaps.py/.json     coverage stats + declared encoder limits
hf_pipeline.yaml        task/model/revision/device + real-run evidence
gen/                    prompt, sha pin, stub renderer, DALL-E/SD twin map
fixtures/               sidecar tags + synthetic drawings (regenerate: make_fixture_images.py)
audio/KND-01.txt        voice-note transcript sidecar (no Whisper)
ethics_note.md          four headings: photos, language, generated pixels, review path
manager_summary.md      risks / mitigations / what we will not claim
tests/test_gold.py      pytest gold + pin + overwrite + privacy + pin checks
evidence/               run logs (mismatch, clip, gold, insights, rates, search, pytest)
```
