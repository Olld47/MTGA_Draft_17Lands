"""
mtga_bridge.tier_service
Pure command implementations for tier-list management, ported from
src/ui/windows/tier_list_panel.py::TierListWindow. Wraps the stateless
file-based src.tier_list.TierList classmethods (list / import / delete). No
pytauri, no tkinter — the commands package wraps these with the IPC glue and
handles the post-mutation scanner refresh.
"""

import logging
import os
from datetime import datetime
from typing import List

from src.tier_list import (
    TierList,
    TIER_FILE_PREFIX,
    TIER_FOLDER,
    TIER_URL_17LANDS,
)

from mtga_bridge.viewmodels import (
    TierActionVM,
    TierListEntryVM,
    TierListsVM,
)

logger = logging.getLogger(__name__)


def list_tier_lists(active_filter: str = "") -> TierListsVM:
    """Port of TierListWindow._update_history_table. Returns every indexed tier
    file (optionally filtered by set), newest first, plus the distinct set codes
    for the filter dropdown."""
    all_files = TierList._get_all_files()
    sets = sorted({f[0] for f in all_files})

    # Reset an out-of-range filter to "All Sets" (empty string), as the panel did
    if active_filter and active_filter not in sets:
        active_filter = ""

    entries: List[TierListEntryVM] = []
    for f_set, f_label, f_date, f_name, _ in all_files:
        if active_filter and f_set != active_filter:
            continue
        entries.append(
            TierListEntryVM(
                set_code=f_set, label=f_label, date=f_date, file_name=f_name
            )
        )
    entries.sort(key=lambda e: e.date, reverse=True)

    return TierListsVM(lists=entries, sets=sets, active_filter=active_filter)


def import_tier_list(url: str, label: str) -> TierActionVM:
    """Blocking port of TierListWindow._run_import: validate, fetch from the
    17Lands API, stamp the custom label, and persist. Call off the event loop."""
    url = (url or "").strip()
    label = (label or "").strip()
    if not url.startswith(TIER_URL_17LANDS):
        return TierActionVM(
            ok=False,
            message="Use a 17Lands tier list URL.",
            lists=list_tier_lists(),
        )
    if not label:
        return TierActionVM(
            ok=False, message="Provide a label.", lists=list_tier_lists()
        )

    try:
        new_tl = TierList.from_api(url)
    except Exception as exc:  # noqa: BLE001 — mirror the panel's broad catch
        logger.warning("Tier list import failed: %s", exc)
        return TierActionVM(ok=False, message=str(exc), lists=list_tier_lists())

    if not new_tl:
        return TierActionVM(
            ok=False,
            message="Could not fetch the tier list (API error).",
            lists=list_tier_lists(),
        )

    new_tl.meta.label = label
    filename = (
        f"{TIER_FILE_PREFIX}_{new_tl.meta.set}_"
        f"{int(datetime.now().timestamp())}.txt"
    )
    new_tl.to_file(os.path.join(TIER_FOLDER, filename))
    return TierActionVM(
        ok=True,
        message=f"Imported '{label}' ({new_tl.meta.set}).",
        lists=list_tier_lists(),
    )


def delete_tier_lists(file_names: List[str], active_filter: str = "") -> TierActionVM:
    """Port of TierListWindow._delete_selected (sans the confirm dialog, which
    the frontend owns)."""
    if not file_names:
        return TierActionVM(
            ok=False, message="Nothing selected.", lists=list_tier_lists(active_filter)
        )
    for name in file_names:
        TierList.delete_file(name)
    return TierActionVM(
        ok=True,
        message=f"Deleted {len(file_names)} tier list(s).",
        lists=list_tier_lists(active_filter),
    )
