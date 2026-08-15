"""i18n coverage guards for the GitHub Pages web templates.

Every data-i18n attribute in the templates and every I18N.t() call in the
static JS must resolve to a key that exists in BOTH the en and zh dictionaries
of templates/i18n.js — a missing translation silently renders the raw key on
the live site. These guards are the unit tests for the bilingual site; the
equivalent checks run manually in a browser during development.
"""

import re
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "server" / "templates"

# Pages that load their own scripts; nav/footer are injected snippets.
HTML_PAGES = ["index.html", "releases.html", "warehouse.html", "calendar.html", "docs.html"]
# Nav/footer keys are injected into every page, so they must be translated too.
HTML_SNIPPETS = ["nav.html", "footer.html"]
JS_FILES = ["app.js", "calendar.js"]

ATTR_RE = re.compile(r'data-i18n(?:-html|-placeholder|-title)?="([a-z][a-zA-Z0-9.]*)"')
T_CALL_RE = re.compile(r"I18N\.t\('([a-z][a-zA-Z0-9.]*)")


def _load_i18n_dicts():
    src = (TEMPLATES_DIR / "i18n.js").read_text(encoding="utf-8")
    en_block = re.search(r"en: \{(.*?)\n    \},", src, re.S).group(1)
    zh_block = re.search(r"zh: \{(.*?)\n    \},", src, re.S).group(1)
    key_re = re.compile(r"'([a-z][a-zA-Z0-9.]*)'\s*:")
    return set(key_re.findall(en_block)), set(key_re.findall(zh_block))


def test_every_page_loads_i18n_before_page_scripts():
    """i18n.js must load before app.js/calendar.js — they call I18N.t()."""
    for name in HTML_PAGES:
        html = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
        i18n_pos = html.find('src="i18n.js?v=3"')
        assert i18n_pos != -1, f"{name} is missing the i18n.js script tag"
        for js in JS_FILES:
            js_pos = html.find(f'src="{js}?v=3"')
            if js_pos != -1:
                assert i18n_pos < js_pos, f"{name}: i18n.js must load before {js}"


def test_template_keys_exist_in_en_dict():
    en_keys, _ = _load_i18n_dicts()
    files = HTML_PAGES + HTML_SNIPPETS
    missing = sorted(
        {
            key
            for name in files
            for key in ATTR_RE.findall((TEMPLATES_DIR / name).read_text(encoding="utf-8"))
        }
        - en_keys
    )
    assert not missing, f"data-i18n keys missing from i18n.js en dict: {missing}"


def test_js_t_calls_exist_in_en_dict():
    en_keys, _ = _load_i18n_dicts()
    missing = sorted(
        {
            key
            for name in JS_FILES
            for key in T_CALL_RE.findall((TEMPLATES_DIR / name).read_text(encoding="utf-8"))
        }
        - en_keys
    )
    assert not missing, f"I18N.t() keys missing from i18n.js en dict: {missing}"


def test_zh_dict_is_symmetric_with_en():
    """Every en key needs a zh translation, and zh has no orphan keys."""
    en_keys, zh_keys = _load_i18n_dicts()
    assert not en_keys - zh_keys, "en keys missing zh translations"
    assert not zh_keys - en_keys, "zh keys with no en source"
