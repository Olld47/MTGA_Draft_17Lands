import os
import json
import gzip
import hashlib
import logging
import shutil
from server import config

logger = logging.getLogger(__name__)


def ensure_output_dir():
    if not os.path.exists(config.OUTPUT_DIR):
        os.makedirs(config.OUTPUT_DIR)


def atomic_write(filepath, write_func):
    """Safely writes to a temporary file, then performs an atomic rename."""
    tmp_filepath = f"{filepath}.tmp"
    try:
        write_func(tmp_filepath)
        os.replace(tmp_filepath, filepath)
    except BaseException as e:
        if os.path.exists(tmp_filepath):
            os.remove(tmp_filepath)
        raise


def save_dataset(set_code, draft_format, user_group, dataset) -> dict:
    ensure_output_dir()
    filename = f"{set_code}_{draft_format}_{user_group}_Data.json.gz"
    filepath = os.path.join(config.OUTPUT_DIR, filename)

    json_str = json.dumps(dataset, separators=(",", ":"))

    internal_name = filename.replace(".gz", "")

    def _write_gz(tmp_path):
        with open(tmp_path, "wb") as f_out:
            with gzip.GzipFile(filename=internal_name, mode="wb", fileobj=f_out) as gz:
                gz.write(json_str.encode("utf-8"))

    atomic_write(filepath, _write_gz)

    with open(filepath, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    size_kb = os.path.getsize(filepath) // 1024
    logger.info(f"Saved {filename} ({size_kb} KB)")

    return {
        "filename": filename,
        "hash": file_hash,
        "size_kb": size_kb,
    }


def save_manifest(manifest_data):
    ensure_output_dir()
    filepath = os.path.join(config.OUTPUT_DIR, "manifest.json")

    def _write_json(tmp_path):
        with open(tmp_path, "w") as f:
            json.dump(manifest_data, f, indent=2)

    atomic_write(filepath, _write_json)
    logger.info("Manifest saved successfully.")


def save_report(report_data: dict):
    ensure_output_dir()
    filepath = os.path.join(config.OUTPUT_DIR, "report.json")

    def _write_json(tmp_path):
        with open(tmp_path, "w") as f:
            json.dump(report_data, f, indent=2)

    atomic_write(filepath, _write_json)
    logger.info(f"Run report saved → {filepath}")


def deploy_web_assets():
    """Copies static HTML/CSS/JS and calendar.json to the GitHub Pages build directory."""
    ensure_output_dir()

    # Copy the calendar for frontend parsing
    calendar_src = os.path.join(os.path.dirname(__file__), "calendar.json")
    if os.path.exists(calendar_src):
        shutil.copy2(calendar_src, os.path.join(config.OUTPUT_DIR, "calendar.json"))

    template_dir = os.path.join(os.path.dirname(__file__), "templates")

    # Load the unified navigation bar and footer
    nav_content = ""
    footer_content = ""

    nav_path = os.path.join(template_dir, "nav.html")
    if os.path.exists(nav_path):
        with open(nav_path, "r", encoding="utf-8") as f:
            nav_content = f.read()

    footer_path = os.path.join(template_dir, "footer.html")
    if os.path.exists(footer_path):
        with open(footer_path, "r", encoding="utf-8") as f:
            footer_content = f.read()

    # i18n.js carries the message dictionary via a deploy-time sentinel —
    # i18n-messages.json is the canonical source (tests json.load() it
    # directly), so the shipped JS stays static and key validation never
    # depends on parsing the script.
    i18n_messages_path = os.path.join(template_dir, "i18n-messages.json")
    if not os.path.exists(i18n_messages_path):
        raise FileNotFoundError(
            "missing i18n-messages.json — required to deploy i18n.js"
        )
    with open(i18n_messages_path, "r", encoding="utf-8") as f:
        i18n_messages_json = json.dumps(json.load(f), ensure_ascii=False)

    # Repo URL sentinels (templates carry __GITHUB_*_URL__ placeholders) are
    # resolved from the single ETL source here, so a namespace/project move
    # touches server/config.py + src/constants/repo.py only.
    sentinel_replacements = {
        "__GITHUB_REPO_URL__": config.GITHUB_REPO_URL,
        "__GITHUB_API_REPO_URL__": config.GITHUB_API_REPO_URL,
        "__GITHUB_PAGES_URL__": config.GITHUB_PAGES_URL,
    }

    # Process and copy static templates (HTML, CSS, JS)
    if os.path.exists(template_dir):
        for filename in os.listdir(template_dir):
            if filename in ["nav.html", "footer.html"]:
                continue  # Don't output the raw snippets

            src_file = os.path.join(template_dir, filename)
            dest_file = os.path.join(config.OUTPUT_DIR, filename)

            if os.path.isfile(src_file):
                with open(src_file, "r", encoding="utf-8") as f:
                    content = f.read()

                if filename.endswith(".html"):
                    # Inject the unified layout components
                    content = content.replace("<!-- INJECT_NAV -->", nav_content)
                    content = content.replace("<!-- INJECT_FOOTER -->", footer_content)
                elif filename == "i18n.js":
                    # Embed the dictionary as a double-escaped JSON string
                    # literal: the JS literal evaluation unescapes the first
                    # layer, the script's single JSON.parse() the second —
                    # the two levels must stay in lockstep (see i18n.js).
                    content = content.replace(
                        '"__I18N_MESSAGES__"', json.dumps(i18n_messages_json)
                    )

                for sentinel, value in sentinel_replacements.items():
                    content = content.replace(sentinel, value)

                with open(dest_file, "w", encoding="utf-8") as f:
                    f.write(content)

    logger.info("Web assets deployed successfully.")
