import pytest
import os
import json
import gzip
import re
from pathlib import Path
from unittest.mock import patch
from server.load import save_dataset, save_manifest, atomic_write, deploy_web_assets
from server import config


@pytest.fixture
def output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("server.config.OUTPUT_DIR", str(tmp_path))
    return tmp_path


def test_atomic_write(output_dir):
    filepath = str(output_dir / "atomic_test.txt")

    def writer(tmp_path):
        with open(tmp_path, "w") as f:
            f.write("Safe Content")

    atomic_write(filepath, writer)

    assert os.path.exists(filepath)
    assert not os.path.exists(f"{filepath}.tmp")
    with open(filepath, "r") as f:
        assert f.read() == "Safe Content"


def test_save_dataset_compresses_and_hashes(output_dir):
    mock_dataset = {"card_ratings": {"123": {"name": "Bolt", "data": "X" * 5000}}}

    result = save_dataset("M10", "PremierDraft", "All", mock_dataset)

    expected_filename = "M10_PremierDraft_All_Data.json.gz"
    filepath = output_dir / expected_filename

    assert result["filename"] == expected_filename
    assert "hash" in result
    assert (
        result["size_kb"] >= 0
    )  # GZIP compresses repetitive text heavily, so it will be < 1KB
    assert filepath.exists()

    # Verify decompression yields the exact original data
    with gzip.open(filepath, "rb") as f:
        loaded_data = json.loads(f.read().decode("utf-8"))
        assert loaded_data["card_ratings"]["123"]["name"] == "Bolt"


def test_save_manifest(output_dir):
    mock_manifest = {"active_sets": ["M10"]}
    save_manifest(mock_manifest)

    filepath = output_dir / "manifest.json"
    assert filepath.exists()
    with open(filepath, "r") as f:
        assert json.load(f)["active_sets"] == ["M10"]


def test_deploy_web_assets_injects_i18n_messages(output_dir):
    """deploy_web_assets embeds i18n-messages.json into the shipped i18n.js.

    The sentinel must be fully replaced and the embedded JSON must round-trip
    to exactly the canonical dictionary — the site's translations ship in the
    script, and any drift means users see raw keys.
    """
    deploy_web_assets()

    deployed = Path(config.OUTPUT_DIR) / "i18n.js"
    assert deployed.exists()
    content = deployed.read_text(encoding="utf-8")
    assert '"__I18N_MESSAGES__"' not in content, "sentinel not replaced"

    match = re.search(r'JSON\.parse\("((?:[^"\\]|\\.)*)"\)', content)
    assert match is not None, "no JSON.parse message load in deployed i18n.js"
    # The capture is a JS string literal body; decode it as a JSON string
    # first, then parse the embedded dictionary JSON.
    inner_json = json.loads('"' + match.group(1) + '"')
    embedded = json.loads(inner_json)

    canonical = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "server"
            / "templates"
            / "i18n-messages.json"
        ).read_text(encoding="utf-8")
    )
    assert embedded == canonical
    assert embedded["zh"]["nav.app"] == "应用与下载"


def test_deploy_resolves_repo_url_sentinels(output_dir):
    """Repo URL placeholders must resolve to the canonical endpoints on deploy,
    so a namespace/project move only touches server/config.py (and its mirror
    src/constants/repo.py) instead of every template.

    nav.html/footer.html are snippets: they keep the raw sentinels in the
    template dir and are resolved only after being injected into a page.
    """
    deploy_web_assets()

    # Deployed pages/scripts: every sentinel resolved, canonical URL present.
    for name, expected in (
        ("index.html", config.GITHUB_REPO_URL),
        ("docs.html", config.GITHUB_PAGES_URL),
        ("app.js", config.GITHUB_API_REPO_URL),
    ):
        content = (Path(config.OUTPUT_DIR) / name).read_text(encoding="utf-8")
        for sentinel in ("__GITHUB_REPO_URL__", "__GITHUB_API_REPO_URL__", "__GITHUB_PAGES_URL__"):
            assert sentinel not in content, f"{name}: {sentinel} not resolved"
        assert expected in content, f"{name}: expected URL missing"

    # The injected nav lands in the deployed index.html (covered above via the
    # repo URL), so the raw snippet is expected to keep its sentinel.
    snippet = (
        Path(__file__).resolve().parents[2] / "server" / "templates" / "nav.html"
    ).read_text(encoding="utf-8")
    assert "__GITHUB_REPO_URL__" in snippet, "nav.html should keep the sentinel"
