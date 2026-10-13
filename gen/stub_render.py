#!/usr/bin/env python3
"""stub_render.py - the $0 generation path (declared fallback, honestly run).

No OpenAI image key and no Diffusers checkpoint exist in this lab, so the
"generation" step is a deterministic Pillow placeholder PLUS the same meta
JSON DALL-E would have written. The output is a LABELLED STUB - it is not a
photo of the SKU and says so, on the pixels and in the JSON.

Fail-closed: refuses to render if gen/prompt_still_life.txt no longer matches
the sha256 pinned in gen/prompt_pin.json.

Run:  python gen/stub_render.py          (exit 0 = pin ok + stub written)
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "gen"
OUT = ROOT / "outputs" / "gen"
PROMPT_PATH = GEN / "prompt_still_life.txt"
PIN_PATH = GEN / "prompt_pin.json"


def fail(msg: str, code: int = 1) -> int:
    print(f"STUB-RENDER FAIL: {msg}")
    return code


def verify_pin() -> dict:
    pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    digest = hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest()
    if digest != pin["prompt_sha256"]:
        raise RuntimeError(
            f"prompt pin mismatch: file={digest[:12]}… pin={pin['prompt_sha256'][:12]}…")
    return pin


def render_stub(path: Path) -> None:
    """Deliberately artificial placeholder: big label, plain colours."""
    img = Image.new("RGB", (512, 512), (32, 36, 48))
    d = ImageDraw.Draw(img)
    d.rectangle([(24, 24), (488, 488)], outline=(230, 170, 60), width=6)
    d.rectangle([(60, 200), (452, 312)], fill=(60, 66, 84))
    d.text((80, 224), "STUB RENDER", fill=(255, 210, 90))
    d.text((80, 256), "NOT A PHOTO OF THE SKU", fill=(255, 255, 255))
    d.text((80, 288), "dall-e-3 / SD did not run - see gen_twin.json", fill=(170, 178, 196))
    d.text((60, 440), "Week 10 SokoniHub - generated pixel, kept OUT of gold/", fill=(140, 148, 166))
    img.save(path)


def main() -> int:
    try:
        pin = verify_pin()
    except FileNotFoundError as exc:
        return fail(f"missing {exc.filename}", 2)
    except (RuntimeError, KeyError, json.JSONDecodeError) as exc:
        return fail(str(exc))

    sku = pin.get("sku_intended", "KND-01")
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / f"{sku}_stub_still_life.png"
    render_stub(png)

    meta = {
        "sku_intended": sku,
        "model": "stub-render-v1",
        "provider": "local Pillow placeholder (no API, no checkpoint)",
        "prompt_file": "gen/prompt_still_life.txt",
        "prompt_sha256": pin["prompt_sha256"],
        "prompt_pin": "gen/prompt_pin.json",
        "not_a_photo_of_the_sku": True,
        "label_on_image": "STUB RENDER / NOT A PHOTO OF THE SKU",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "outputs": {
            "pixels": str(png.relative_to(ROOT)).replace("\\", "/"),
            "kept_out_of": ["gold/", "fixtures/images/"],
        },
        "dalle_would_have_written": {
            "model": "dall-e-3",
            "size": "1024x1024",
            "quality": "standard",
            "note": "same JSON shape, same not_a_photo_of_the_sku=true key; "
                    "status would flip to 'live' and cost ~$0.04-0.08/image",
        },
        "people_terms_in_prompt": False,
    }
    meta_path = OUT / f"{sku}_gen_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    print(f"prompt pin OK ({pin['prompt_sha256'][:12]}…)")
    print(f"stub pixels -> {meta['outputs']['pixels']}")
    print(f"gen meta    -> {meta_path.relative_to(ROOT)}  "
          f"(not_a_photo_of_the_sku={meta['not_a_photo_of_the_sku']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
