"""
Contrast guard for the desktop UI's two palettes.

Deliberately narrow: it re-derives WCAG ratios for the pairings `app.css`
actually renders, using the hexes declared in `tokens.css`. It cannot evaluate
`color-mix()` or alpha, and it will not notice a *new* bad pairing added to
`app.css` — the pair table below is hand-written. What it does catch is a token
value edited into illegibility, and a token added to one palette but forgotten
in the other.
"""

import os
import re

import pytest

TOKENS_CSS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "desktop",
    "src",
    "styles",
    "tokens.css",
)

# WCAG 2.1: 4.5:1 for body text, 3:1 for large text and non-text UI shapes.
AA_TEXT = 4.5
AA_SHAPE = 3.0

_BLOCK_RE = re.compile(r"(:root[^{]*)\{(.*?)\n\}", re.DOTALL)
_DECL_RE = re.compile(r"--([a-z0-9-]+)\s*:\s*([^;]+);")


def _parse_blocks() -> dict:
    """{'dark': {token: value}, 'light': {...}} with var() references resolved."""
    with open(TOKENS_CSS, encoding="utf-8") as handle:
        css = handle.read()

    blocks = {}
    for selector, body in _BLOCK_RE.findall(css):
        if '[data-theme="light"]' in selector:
            name = "light"
        elif '[data-theme="dark"]' in selector:
            name = "dark"
        else:
            continue  # the shared type/metrics block
        blocks[name] = dict(
            (token, value.split("/*")[0].strip())
            for token, value in _DECL_RE.findall(body)
        )

    for palette in blocks.values():
        for token, value in list(palette.items()):
            match = re.fullmatch(r"var\(--([a-z0-9-]+)\)", value)
            if match:
                palette[token] = palette[match.group(1)]

    return blocks


PALETTES = _parse_blocks()


def _luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip("#")
    channels = []
    for offset in (0, 2, 4):
        channel = int(hex_color[offset : offset + 2], 16) / 255
        channels.append(
            channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(fg: str, bg: str) -> float:
    light, dark = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


# (foreground, background, minimum) — each mirrors a real rule in app.css.
PAIRS = [
    ("parchment", "ink", AA_TEXT),  # body text on the app background
    ("parchment", "felt", AA_TEXT),  # body text on panels
    ("parchment", "felt-hover", AA_TEXT),  # hovered table rows
    ("gruff", "ink", AA_TEXT),  # muted labels, ~30 sites
    ("gruff", "felt", AA_TEXT),
    ("gruff", "felt-hover", AA_TEXT),
    ("gold-foil", "ink", AA_TEXT),  # elite card names, active tab
    ("gold-foil", "felt", AA_TEXT),
    ("ok", "felt", AA_TEXT),
    ("err", "felt", AA_TEXT),
    # Mana hues as text: .pip-count.* and .pool-strip .pips .*
    ("mana-w", "felt", AA_TEXT),
    ("mana-u", "felt", AA_TEXT),
    ("mana-b", "felt", AA_TEXT),
    ("mana-r", "felt", AA_TEXT),
    ("mana-g", "felt", AA_TEXT),
    ("mana-w", "felt-hover", AA_TEXT),
    ("mana-u", "felt-hover", AA_TEXT),
    ("mana-b", "felt-hover", AA_TEXT),
    ("mana-r", "felt-hover", AA_TEXT),
    ("mana-g", "felt-hover", AA_TEXT),
    # Pip glyphs on their own backgrounds (.mana .pip.*)
    ("mana-w-fg", "mana-w", AA_TEXT),
    ("mana-u-fg", "mana-u", AA_TEXT),
    ("mana-b-fg", "mana-b", AA_TEXT),
    ("mana-r-fg", "mana-r", AA_TEXT),
    ("mana-g-fg", "mana-g", AA_TEXT),
    ("pip-fg", "gruff", AA_TEXT),  # .mana .pip.c — the only glyph-bearing pip
    # Non-text: filled shapes that must be distinguishable from their surface
    ("mana-w", "ink", AA_SHAPE),  # signal lane fills, row tints
    ("mana-u", "ink", AA_SHAPE),
    ("mana-b", "ink", AA_SHAPE),
    ("mana-r", "ink", AA_SHAPE),
    ("mana-g", "ink", AA_SHAPE),
    ("gold-foil", "felt-hover", AA_SHAPE),  # progress-fill on a track
]


def test_both_palettes_parsed():
    """A selector rename would otherwise turn every test below into a no-op."""
    assert set(PALETTES) == {"dark", "light"}
    assert len(PALETTES["dark"]) >= 20


def test_palettes_define_the_same_tokens():
    """A token added to dark and forgotten in light silently falls back to the
    dark value, which is exactly the bug this theme work exists to prevent."""
    assert set(PALETTES["dark"]) == set(PALETTES["light"])


@pytest.mark.parametrize("palette", sorted(PALETTES))
def test_every_color_token_is_a_hex_or_resolved(palette):
    for token, value in PALETTES[palette].items():
        if token == "scrim":
            continue  # rgba, and it sits over arbitrary content
        assert re.fullmatch(r"#[0-9a-f]{6}", value), f"{palette} --{token} = {value}"


@pytest.mark.parametrize("palette", sorted(PALETTES))
@pytest.mark.parametrize("fg,bg,minimum", PAIRS, ids=[f"{f}-on-{b}" for f, b, _ in PAIRS])
def test_contrast(palette, fg, bg, minimum):
    colors = PALETTES[palette]
    ratio = contrast(colors[fg], colors[bg])
    assert ratio >= minimum, (
        f"{palette}: --{fg} ({colors[fg]}) on --{bg} ({colors[bg]}) "
        f"is {ratio:.2f}:1, need {minimum}:1"
    )


def test_scrim_is_translucent_in_both_palettes():
    for palette in PALETTES.values():
        assert palette["scrim"].startswith("rgb(")
