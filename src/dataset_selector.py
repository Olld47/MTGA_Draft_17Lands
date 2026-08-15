"""
src/dataset_selector.py

Dataset selection for ArenaScanner (architecture-review issue 11 Phase 2).

ArenaScanner used to inline three dataset responsibilities: scanning the local
set files into a label->path catalog, ranking that catalog to pick the most
representative dataset for a draft event, and loading the chosen file into its
in-memory Dataset. This module owns the first two — the catalog scan and the
event-type/user-group ranking — as a small, state-free module:

- `_dataset_event_type_rank` / `_best_dataset_by_rank`: the ranking helpers
  (moved verbatim from src/log_scanner.py).
- `DatasetSelector.retrieve_data_sources(draft_type)`: the local-file catalog
  scan. draft_type is an explicit parameter because the scan prefers the
  active draft's event type when collection dates tie.
- `DatasetSelector.select_best_dataset(catalog, s_code, event_name)`: pure
  ranking over a catalog (the caller fetches the catalog).

Loading the chosen file stays with the scanner: `retrieve_set_data` mutates
the scanner-owned `Dataset` instance (clear + open_file + metrics cache), so
the Dataset memory state is not moved. ArenaScanner keeps same-signature
proxies, so callers (bootstrap, orchestrator, tkinter UI, tests) are
untouched.
"""

import re
from datetime import datetime
from typing import Optional

import src.constants as constants
from src.logger import create_logger
from src.utils import retrieve_local_set_list

logger = create_logger()


def _dataset_event_type_rank(
    label_event_type: str, event_name: str
) -> Optional[int]:
    """0 = exact event-name section match, 1 = containment match, None = no match.

    Dataset labels carry an event type like "QuickDraft" or "PickTwoQuickDraft".
    We prefer an exact section of the draft's event name (e.g. "QuickDraft" in
    "QuickDraft_MSH_20260806") and fall back to containment so pick-two variants
    still resolve ("QuickDraft" in "PickTwoQuickDraft_MSH_..."). Returns None
    when the dataset's type is unrelated to the event.
    """
    if not event_name:
        return 0
    lowered = event_name.lower()
    for section in event_name.split("_"):
        if label_event_type.lower() == section.lower():
            return 0
    if label_event_type.lower() in lowered:
        return 1
    return None


def _best_dataset_by_rank(sources, set_tag: str, type_rank_for):
    """The best (score, path) among one set's dataset sources, or None.

    Scores each label by (type_rank, group_rank, label) — lower wins, so an
    exact event-type match beats a containment match, and the broad "All"
    sample beats "Top" within a rank. type_rank_for(label) returns the event-type
    rank or None to skip that source; the label must carry the set's [TAG] to be
    considered at all.
    """
    best = None
    for label, path in sources.items():
        if set_tag not in label.upper():
            continue
        type_rank = type_rank_for(label)
        if type_rank is None:
            continue
        group_rank = 0 if label.rstrip().endswith("(All)") else 1
        score = (type_rank, group_rank, label)
        if best is None or score < best[0]:
            best = (score, path)
    return best


class DatasetSelector:
    """Selects which local dataset file represents a draft event.

    Owns the local-file catalog scan and the event-type/group ranking that
    ArenaScanner used to inline. The scan is the only stateful-feeling piece
    (it reads the local Sets folder); ranking a catalog is pure. Loading the
    chosen file into the scanner's in-memory Dataset is NOT here — that mutates
    scanner state (`retrieve_set_data` stays on ArenaScanner).
    """

    def retrieve_data_sources(
        self, draft_type: int = constants.LIMITED_TYPE_UNKNOWN
    ) -> dict:
        """Scan the local Sets folder into a label->path catalog.

        Labels are "[SET] EventType (UserGroup)". When a draft is active
        (draft_type known) the scan prefers that event type's datasets on
        collection-date ties. Returns DATA_SOURCES_NONE when nothing is found.
        """
        data_sources = {}
        try:
            file_list, error_list = retrieve_local_set_list()
            if draft_type != constants.LIMITED_TYPE_UNKNOWN:
                found_types = [
                    k
                    for k, v in constants.LIMITED_TYPES_DICT.items()
                    if v == draft_type
                ]
                if file_list:
                    file_list.sort(
                        key=lambda x: (
                            0 if x.event_type in found_types else 1,
                            datetime.strptime(x.end_date, "%Y-%m-%d"),
                        ),
                        reverse=True,
                    )
                    file_list.sort(key=lambda x: x.collection_date, reverse=True)
            for file in file_list:
                set_code, event_type, user_group, location = (
                    file.set_name,
                    file.event_type,
                    file.user_group,
                    file.file_location,
                )
                prefix = (
                    f"[{set_code[0:6]}]"
                    if re.search(r"^[Yy]\d{2}", set_code)
                    else f"[{set_code}]"
                )
                data_sources[f"{prefix} {event_type} ({user_group})"] = location
        except Exception as error:
            logger.error(error)
        return data_sources if data_sources else constants.DATA_SOURCES_NONE

    def select_best_dataset(
        self, data_sources: dict, s_code: str, event_name: str = ""
    ) -> str:
        """Pick the most representative dataset for an event from a catalog.

        Ranks every source for the set by event-type agreement with the draft
        (see _dataset_event_type_rank) and by user group, preferring the broad
        "All" sample over "Top". Returns the file path, or "" when the set has
        no local dataset. Callers use this instead of matching only the set
        bracket — a set has one dataset per event type, and loading the wrong
        one (e.g. a PickTwo draft for a QuickDraft) yields all-zero stats.
        """
        set_tag = f"[{s_code.upper()}]"

        def rank_by_event(label: str) -> Optional[int]:
            label_type = label.split("]", 1)[1].split("(", 1)[0].strip()
            return _dataset_event_type_rank(label_type, event_name)

        best = _best_dataset_by_rank(data_sources, set_tag, rank_by_event)
        if best is None:
            # No dataset matched the event name: fall back to any source for the set.
            best = _best_dataset_by_rank(data_sources, set_tag, lambda _label: 1)
        return best[1] if best else ""
