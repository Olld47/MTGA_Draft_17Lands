"""
src/practice_actions.py
Shared practice-pool construction for the Sealed Practice dialog, consumed by
both the desktop bridge (mtga_bridge.practice) and the legacy tkinter view
(src/ui/windows/practice_dialog.py). Pure: random-pack generation, MTGA
decklist import, set-dropdown assembly, dataset priority ranking, session-id
generation — no tkinter, no pytauri, no viewmodels. Scanner access, manifest
reads, dataset switching, clipboard access, and presentation stay in the
adapters.

Ticket 09 convergence: the pool-building and set-ranking code was duplicated
verbatim between the bridge and the tkinter dialog (with the pack-size
constants inlined in the dialog as 6/1/3/10). This module is the single
implementation both sides delegate to.
"""

import logging
import random
import re
import uuid
from typing import List, Optional, Tuple

from src import constants
from src.utils import sanitize_card_name

logger = logging.getLogger(__name__)

PACK_COUNT = 6
RARES_PER_PACK = 1
UNCOMMONS_PER_PACK = 3
COMMONS_PER_PACK = 10

#: Dataset preference when several are downloaded for a set: Sealed data
#: outranks Premier, which outranks Traditional.
DATASET_PRIORITY = ("Sealed", "PremierDraft", "TradDraft")


def dataset_rank(event_type: str) -> int:
    """Lower rank = preferred dataset event type."""
    for i, kind in enumerate(DATASET_PRIORITY):
        if kind in event_type:
            return i
    return len(DATASET_PRIORITY)


def build_set_options(
    set_list_data: dict, active_codes: List[str], latest_set: str = ""
) -> List[dict]:
    """Ordered dropdown options: manifest-active sets first (manifest order),
    then the rest alphabetically. Each option is
    {"code": <17Lands code>, "name": <set name>, "is_active": bool}; entries
    without a set code are skipped."""
    codes = list(active_codes)
    if latest_set and latest_set not in codes:
        codes.append(latest_set)

    active: List[Tuple[int, dict]] = []
    inactive: List[dict] = []

    for set_name, info in set_list_data.items():
        code = getattr(info, "set_code", "")
        if not code:
            continue
        sl_code = info.seventeenlands[0] if info.seventeenlands else code
        option = {"code": sl_code, "name": set_name, "is_active": False}

        rank = next(
            (codes.index(c) for c in (sl_code, code) if c in codes), None
        )
        if rank is None:
            inactive.append(option)
        else:
            option["is_active"] = True
            active.append((rank, option))

    active.sort(key=lambda pair: pair[0])
    inactive.sort(key=lambda option: option["name"])
    return [option for _, option in active] + inactive


def generate_random_pool(dataset) -> Tuple[List[dict], str]:
    """Six packs of 1 rare/mythic + 3 uncommons + 10 commons, drawn with
    replacement from the set's unique non-basic cards."""
    unique = {}
    for card in dataset.get_card_ratings().values():
        name = card.get(constants.DATA_FIELD_NAME)
        if name and name not in unique:
            unique[name] = card

    commons, uncommons, rares = [], [], []
    for card in unique.values():
        if (
            "Basic" in card.get("types", [])
            or card.get(constants.DATA_FIELD_NAME) in constants.BASIC_LANDS
        ):
            continue
        rarity = str(card.get("rarity", "common")).lower()
        if rarity == "common":
            commons.append(card)
        elif rarity == "uncommon":
            uncommons.append(card)
        elif rarity in ("rare", "mythic"):
            rares.append(card)

    if not commons or not uncommons or not rares:
        return [], "Dataset is incomplete — cannot generate a pool."

    pool: List[dict] = []
    for _ in range(PACK_COUNT):
        picks = (
            random.choices(rares, k=RARES_PER_PACK)
            + random.choices(uncommons, k=UNCOMMONS_PER_PACK)
            + random.choices(commons, k=COMMONS_PER_PACK)
        )
        pool.extend(dict(card) for card in picks)
    return pool, ""


def parse_pool_text(dataset, text: str) -> Tuple[List[dict], str]:
    """Resolves an MTGA decklist against the loaded dataset, expanding each
    line's count into that many pool entries."""
    pool: List[dict] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.lower() in ("deck", "sideboard", "commander", "companion"):
            continue
        match = re.match(r"^(\d+)\s+([^(]+)", line)
        if not match:
            continue
        count = int(match.group(1))
        found = dataset.get_data_by_name([sanitize_card_name(match.group(2).strip())])
        if found:
            pool.extend(dict(found[0]) for _ in range(count))

    if not pool:
        return [], "No valid MTGA format cards found in the pasted text."
    return pool, ""


def new_session_id() -> str:
    return f"practice_{uuid.uuid4().hex[:8]}"
