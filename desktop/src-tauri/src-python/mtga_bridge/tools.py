"""
mtga_bridge.tools
Pure command implementations for the legacy File menu's tools
(src/ui/menu_bar.py::AppMenuBar): draft export and MTGA_Data folder location.
No pytauri, no tkinter — the native file/directory dialogs live on the
frontend (Tauri dialog plugin), so these take and return plain values.
"""

import logging
import os

from src.card_logic import export_draft_to_csv, export_draft_to_json
from src.configuration import write_configuration

from mtga_bridge.viewmodels import Ack, DraftExportVM, LocateDataVM

logger = logging.getLogger(__name__)


def export_draft(scanner, fmt: str) -> DraftExportVM:
    """Port of AppMenuBar._export_csv / _export_json. Returns the serialized
    draft history plus a suggested file name; the frontend picks the save path
    and writes the file."""
    if fmt not in ("csv", "json"):
        return DraftExportVM(ok=False, message=f"Unknown export format: {fmt}")

    with scanner.lock:
        history = list(scanner.retrieve_draft_history() or [])
        set_data = scanner.set_data
        picked = [list(p) for p in scanner.picked_cards]
        event_set = scanner.draft_sets[0] if scanner.draft_sets else ""

    if not history:
        return DraftExportVM(ok=False, message="No draft history to export.")

    serialize = export_draft_to_csv if fmt == "csv" else export_draft_to_json
    try:
        text = serialize(history, set_data, picked)
    except Exception as exc:
        logger.warning("Draft export failed: %s", exc)
        return DraftExportVM(ok=False, message=f"Export failed: {exc}")

    name = f"DraftExport_{event_set}" if event_set else "DraftExport"
    return DraftExportVM(ok=True, text=text, file_name=f"{name}.{fmt}", format=fmt)


def save_text_file(path: str, text: str) -> Ack:
    """Writes an exported document to the path the user chose in the native save
    dialog. The write lives in Python so the Tauri fs plugin (whose scope would
    have to be widened to every user-writable path) isn't needed."""
    if not path:
        return Ack(ok=False, message="No file selected.")
    try:
        # newline="" — export_draft_to_csv already emits CRLF line endings, so
        # newline translation would double the CRs on Windows.
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    except OSError as exc:
        logger.warning("Saving %s failed: %s", path, exc)
        return Ack(ok=False, message=f"Could not write {os.path.basename(path)}: {exc}")
    return Ack(message=f"Saved {os.path.basename(path)}")


def locate_mtga_data(runtime, folder: str) -> LocateDataVM:
    """Port of AppMenuBar._locate_mtga_data. Accepts the directory the user
    picked natively, validates it holds Downloads/Raw, then persists it and
    re-points the scanner's card database at it."""
    if not folder:
        return LocateDataVM(ok=False, message="No folder selected.")

    # The picker may land on MTGA's parent directory rather than MTGA_Data.
    if not folder.endswith("MTGA_Data") and os.path.isdir(
        os.path.join(folder, "MTGA_Data")
    ):
        folder = os.path.join(folder, "MTGA_Data")

    if not os.path.exists(os.path.join(folder, "Downloads", "Raw")):
        return LocateDataVM(
            ok=False,
            message=(
                "Could not find 'Downloads/Raw' in the selected folder. "
                "Please select the valid MTGA_Data folder."
            ),
        )

    config = runtime.config
    config.settings.database_location = folder
    write_configuration(config)

    scanner = runtime.scanner
    if scanner is not None and getattr(scanner, "set_data", None):
        scanner.set_data.db_path = folder
        scanner.set_data.unknown_id_cache.clear()

    return LocateDataVM(
        ok=True,
        path=folder,
        message=f"MTGA Data folder set to {folder}. You can now download datasets.",
    )
