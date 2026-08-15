"""Regenerates desktop/src-tauri/icons from a single vector-ish description.

There is no SVG rasterizer in the toolchain (no rsvg/inkscape/imagemagick), so
the artwork is drawn with PIL supersampled and downsampled. Run from the repo
root:

    ./.venv/bin/python desktop/scripts/make_icons.py

Palette is lifted from desktop/src/styles/tokens.css so the icon and the app
masthead stay the same brand.
"""

import os

from PIL import Image, ImageDraw, ImageFilter

INK = (16, 19, 24, 255)
FELT = (26, 31, 39, 255)
GOLD = (201, 164, 76, 255)
PARCHMENT = (232, 228, 216, 255)
LINE = (44, 52, 64, 255)
SLATE = (95, 104, 118, 255)
SLATE_FAR = (60, 68, 80, 255)

SS = 4  # supersample factor
MASTER = 1024

ICONS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "src-tauri", "icons"
)

PNG_SIZES = {
    "32x32.png": 32,
    "128x128.png": 128,
    "128x128@2x.png": 256,
    "icon.png": 512,
    "Square30x30Logo.png": 30,
    "Square44x44Logo.png": 44,
    "Square71x71Logo.png": 71,
    "Square89x89Logo.png": 89,
    "Square107x107Logo.png": 107,
    "Square142x142Logo.png": 142,
    "Square150x150Logo.png": 150,
    "Square284x284Logo.png": 284,
    "Square310x310Logo.png": 310,
    "StoreLogo.png": 50,
}

ICNS_SIZES = [16, 32, 64, 128, 256, 512, 1024]
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def _squircle_mask(size, radius_ratio=0.225):
    """Rounded-square mask in the macOS idiom."""
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=int(size * radius_ratio), fill=255
    )
    return mask


def _card(w, h, fill, outline=None, outline_w=0, radius_ratio=0.09):
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(
        (0, 0, w - 1, h - 1),
        radius=int(min(w, h) * radius_ratio),
        fill=fill,
        outline=outline,
        width=outline_w,
    )
    return layer


def _fan_card(base, w, h, angle, pivot, arm, fill, outline):
    """Splay a card about a pivot `arm` px below its bottom edge, like a held hand."""
    span = h + arm
    layer = Image.new("RGBA", (max(w, span * 2), span * 2), (0, 0, 0, 0))
    layer.alpha_composite(
        _card(w, h, fill, outline=outline, outline_w=max(1, w // 26)),
        ((layer.width - w) // 2, 0),
    )
    rot = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    base.alpha_composite(rot, (pivot[0] - rot.width // 2, pivot[1] - rot.height // 2))


def render(size=MASTER):
    """The mark: a fanned pack with the picked card drawn up out of it, in gold."""
    n = size * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))

    tile = Image.new("RGBA", (n, n), FELT)
    grad = Image.new("RGBA", (n, n), INK)
    ramp = Image.new("L", (1, n))
    for y in range(n):
        ramp.putpixel((0, y), int(255 * (y / n) ** 1.4))
    tile = Image.composite(grad, tile, ramp.resize((n, n)))
    tile.putalpha(_squircle_mask(n))
    img.alpha_composite(tile)

    cw, ch = int(n * 0.26), int(n * 0.37)
    pivot = (n // 2, int(n * 0.83))
    arm = int(n * 0.05)

    # Outermost first so nearer cards overlap them, as a held fan does.
    for angle, fill in ((36, SLATE_FAR), (-36, SLATE_FAR), (18, SLATE), (-18, SLATE)):
        _fan_card(img, cw, ch, angle, pivot, arm, fill, LINE)

    pw, ph = int(cw * 1.12), int(ch * 1.12)
    px, py = (n - pw) // 2, int(n * 0.17)

    glow = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle(
        (px - int(n * 0.02), py - int(n * 0.02), px + pw + int(n * 0.02), py + ph),
        radius=int(pw * 0.13),
        fill=GOLD,
    )
    glow = glow.filter(ImageFilter.GaussianBlur(int(n * 0.028)))
    glow.putalpha(glow.getchannel("A").point(lambda a: a * 95 // 255))
    img.alpha_composite(glow)

    pick = _card(pw, ph, GOLD, outline=PARCHMENT, outline_w=int(n * 0.007))
    ImageDraw.Draw(pick).line(
        [
            (pw * 0.27, ph * 0.52),
            (pw * 0.44, ph * 0.68),
            (pw * 0.75, ph * 0.33),
        ],
        fill=INK,
        width=int(pw * 0.13),
        joint="curve",
    )
    img.alpha_composite(pick, (px, py))

    return img.resize((size, size), Image.LANCZOS)


def main():
    master = render(MASTER)
    out = os.path.normpath(ICONS_DIR)

    for name, size in PNG_SIZES.items():
        master.resize((size, size), Image.LANCZOS).save(os.path.join(out, name))

    master.resize((256, 256), Image.LANCZOS).save(
        os.path.join(out, "icon.ico"),
        sizes=[(s, s) for s in ICO_SIZES],
    )

    iconset = os.path.join(out, "icon.iconset")
    os.makedirs(iconset, exist_ok=True)
    for size in ICNS_SIZES:
        img = master.resize((size, size), Image.LANCZOS)
        img.save(os.path.join(iconset, f"icon_{size}x{size}.png"))
        if size > 16:
            img.save(os.path.join(iconset, f"icon_{size // 2}x{size // 2}@2x.png"))
    os.system(f'iconutil -c icns "{iconset}" -o "{os.path.join(out, "icon.icns")}"')
    for f in os.listdir(iconset):
        os.remove(os.path.join(iconset, f))
    os.rmdir(iconset)

    print(f"wrote {len(PNG_SIZES)} pngs + icon.ico + icon.icns to {out}")


if __name__ == "__main__":
    main()
