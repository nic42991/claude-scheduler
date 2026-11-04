"""Brand pin/post image generator (Pillow). Cream + light blue, soft rounded card.

make_pin(product_image, headline, out_path, subline=None, size=(1000, 1500))
make_square(product_image, headline, out_path)  -> 1080x1080 for Instagram
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CREAM = (250, 246, 238)
BLUE = (196, 220, 236)
INK = (58, 66, 80)
ACCENT = (120, 160, 196)
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _compose(product_image: str | Path, headline: str, out_path: str | Path, subline: str | None, size: tuple[int, int], brand: str) -> Path:
    W, H = size
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    pad = int(W * 0.06)
    # photo area (top ~62%)
    photo_h = int(H * 0.62)
    d.rounded_rectangle([pad, pad, W - pad, pad + photo_h], radius=40, fill=BLUE)
    photo = Image.open(product_image).convert("RGB")
    box_w, box_h = W - 2 * pad - 40, photo_h - 40
    photo.thumbnail((box_w, box_h))
    px = pad + 20 + (box_w - photo.width) // 2
    py = pad + 20 + (box_h - photo.height) // 2
    mask = Image.new("L", photo.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, photo.width, photo.height], radius=28, fill=255)
    img.paste(photo, (px, py), mask)
    # headline
    y = pad + photo_h + int(H * 0.04)
    f_head = _font(int(W * 0.062))
    for line in _wrap(d, headline, f_head, W - 2 * pad)[:3]:
        d.text((pad, y), line, font=f_head, fill=INK)
        y += int(f_head.size * 1.25)
    if subline:
        f_sub = _font(int(W * 0.036))
        y += int(H * 0.01)
        for line in _wrap(d, subline, f_sub, W - 2 * pad)[:2]:
            d.text((pad, y), line, font=f_sub, fill=ACCENT)
            y += int(f_sub.size * 1.3)
    # brand footer
    f_brand = _font(int(W * 0.03))
    d.text((pad, H - pad - f_brand.size), brand, font=f_brand, fill=ACCENT)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=92)
    return out


def make_pin(product_image, headline, out_path, subline=None, brand="Curious Little by Gozde"):
    return _compose(product_image, headline, out_path, subline, (1000, 1500), brand)


def make_square(product_image, headline, out_path, subline=None, brand="Curious Little by Gozde"):
    return _compose(product_image, headline, out_path, subline, (1080, 1080), brand)
