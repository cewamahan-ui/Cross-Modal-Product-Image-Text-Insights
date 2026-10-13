#!/usr/bin/env python3
"""make_fixture_images.py - regenerate the four SYNTHETIC fixture drawings.

These are hand-drawn Pillow shapes, not marketplace photos and not model
output. They exist so the cross-modal join has pixels to look at without
crawling a live marketplace (and without any faces). Run:

    python fixtures/make_fixture_images.py

Writes fixtures/images/{KND-01,NK-99,THD-02,KNG-04}.png (224x224, CLIP-sized).

Honesty note: NK-99's drawing is deliberately another kiondo - the teaching
mismatch is "photo shows a kiondo, title claims Nike".
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "images"
SIZE = 224


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (SIZE, SIZE), (245, 245, 240))
    return img, ImageDraw.Draw(img)


def draw_kiondo(path: Path) -> None:
    """Tan woven tote (kiondo) with leather straps."""
    img, d = _canvas()
    body = [(56, 96), (168, 96), (152, 200), (72, 200)]
    d.polygon(body, fill=(196, 158, 96), outline=(120, 92, 50), width=4)
    # weave lines
    for y in range(112, 196, 14):
        d.line([(62 + (200 - y) // 8, y), (162 - (200 - y) // 8, y)],
               fill=(150, 118, 66), width=2)
    for x in range(80, 150, 16):
        d.line([(x, 100), (x - 6, 196)], fill=(150, 118, 66), width=1)
    # handles
    d.arc([(78, 40), (146, 116)], start=180, end=360, fill=(110, 74, 40), width=8)
    # leather strap accents
    d.line([(56, 120), (168, 120)], fill=(110, 74, 40), width=5)
    img.save(path)


def draw_sufuria(path: Path) -> None:
    """Blue speckled enamel cooking pot."""
    img, d = _canvas()
    d.ellipse([(46, 74), (178, 190)], fill=(38, 92, 168), outline=(18, 46, 90), width=5)
    d.ellipse([(46, 58), (178, 96)], fill=(70, 130, 205), outline=(18, 46, 90), width=5)
    # speckles
    for i, (x, y) in enumerate([(80, 120), (110, 145), (140, 110), (95, 165),
                                (132, 170), (66, 150), (155, 140), (120, 100)]):
        r = 4 if i % 2 else 3
        d.ellipse([(x - r, y - r), (x + r, y + r)], fill=(230, 236, 245))
    # handles
    d.arc([(30, 100), (70, 150)], start=90, end=270, fill=(18, 46, 90), width=7)
    d.arc([(154, 100), (194, 150)], start=270, end=450, fill=(18, 46, 90), width=7)
    img.save(path)


def draw_kanga(path: Path) -> None:
    """Red-and-white kanga cloth wrap with printed border."""
    img, d = _canvas()
    d.rectangle([(28, 40), (196, 204)], fill=(192, 57, 43), outline=(120, 30, 24), width=4)
    d.rectangle([(44, 56), (180, 188)], outline=(245, 240, 230), width=4)
    # pindo (border dots)
    for x in range(52, 180, 16):
        d.ellipse([(x - 3, 46), (x + 3, 52)], fill=(245, 240, 230))
        d.ellipse([(x - 3, 192), (x + 3, 198)], fill=(245, 240, 230))
    # central print motif
    d.ellipse([(92, 96), (132, 136)], outline=(245, 240, 230), width=4)
    d.line([(76, 152), (148, 152)], fill=(245, 240, 230), width=4)
    d.line([(86, 164), (138, 164)], fill=(245, 240, 230), width=3)
    img.save(path)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    draw_kiondo(OUT / "KND-01.png")
    draw_kiondo(OUT / "NK-99.png")   # photo shows a kiondo; the title claims Nike
    draw_sufuria(OUT / "THD-02.png")
    draw_kanga(OUT / "KNG-04.png")
    for p in sorted(OUT.glob("*.png")):
        print(f"wrote {p.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
