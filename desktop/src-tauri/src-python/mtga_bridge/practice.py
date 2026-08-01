"""
mtga_bridge.practice
Headless port of src/ui/windows/practice_dialog.py::PracticeDialog. Builds a
practice Sealed pool — either six randomly generated packs or an MTGA decklist
pasted by the user — and hands it to the already-ported SealedStudioSession.

No tkinter, no pytauri. The dialog read the set list from the app context and
the decklist from the tkinter clipboard; here the set list comes from the
scanner and the decklist text arrives as an argument.
"""

import random
import re
import uuid
from typing import List, Optional, Tuple

from src import constants
from src.utils import read_local_manifest, retrieve_local_set_list, sanitize_card_name

from mtga_bridge.datasets import select_dataset_blocking
from mtga_bridge.viewmodels import PracticeSetsVM, PracticeSetVM, SealedActionVM

PACK_COUNT = 6
RARES_PER_PACK = 1
UNCOMMONS_PER_PACK = 3
COMMONS_PER_PACK = 10

_DATASET_PRIORITY = ("Sealed", "PremierDraft", "TradDraft")


# --- Set listing --------------------------------------------------------------


def list_practice_sets(scanner) -> PracticeSetsVM:
    """Port of PracticeDialog._build_ui's dropdown assembly: sets that the
    manifest marks active come first in manifest order, the rest follow
    alphabetically."""
    set_list = getattr(scanner, "set_list", None)
    sets_data = getattr(set_list, "data", {}) or {}
    if not sets_data:
        return PracticeSetsVM()

    active_codes = list(read_local_manifest().get("active_sets", []) or [])
    latest = getattr(set_list, "latest_set", "")
    if latest and latest not in active_codes:
        active_codes.append(latest)

    active: List[Tuple[int, PracticeSetVM]] = []
    inactive: List[PracticeSetVM] = []

    for set_name, info in sets_data.items():
        code = info.set_code
        if not code:
            continue
        sl_code = info.seventeenlands[0] if info.seventeenlands else code
        vm = PracticeSetVM(code=sl_code, name=set_name, label=f"{set_name} ({sl_code})")

        rank = next(
            (active_codes.index(c) for c in (sl_code, code) if c in active_codes), None
        )
        if rank is None:
            inactive.append(vm)
        else:
            vm.is_active = True
            active.append((rank, vm))

    active.sort(key=lambda pair: pair[0])
    inactive.sort(key=lambda vm: vm.label)
    ordered = [vm for _, vm in active] + inactive

    return PracticeSetsVM(
        sets=ordered, default_code=ordered[0].code if ordered else ""
    )


# --- Dataset selection --------------------------------------------------------


def _dataset_rank(event_type: str) -> int:
    for i, kind in enumerate(_DATASET_PRIORITY):
        if kind in event_type:
            return i
    return len(_DATASET_PRIORITY)


def _load_set_dataset(scanner, config, set_code: str) -> bool:
    """Switches the whole app to the best downloaded dataset for `set_code`, so
    the practice pool's stats match every other view. Sealed data is preferred,
    then Premier, then Traditional."""
    datasets, _ = retrieve_local_set_list(codes=[set_code])
    if not datasets:
        return False
    best = min(datasets, key=lambda d: _dataset_rank(d[1]))
    return select_dataset_blocking(scanner, config, best[6])


# --- Pool construction --------------------------------------------------------


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


# --- Entry point --------------------------------------------------------------


def start_practice(
    scanner, config, sealed_session, set_code: str, import_text: Optional[str] = None
) -> SealedActionVM:
    """Builds a practice pool for `set_code` and loads it into the sealed
    studio. Passing `import_text` imports an MTGA decklist instead of
    generating random packs."""
    if not set_code:
        return SealedActionVM(
            ok=False, message="Select a set first.", state=sealed_session.build_state()
        )

    if not _load_set_dataset(scanner, config, set_code):
        return SealedActionVM(
            ok=False,
            message=(
                f"No downloaded dataset found for {set_code}. "
                f"Download it from the Datasets tab first."
            ),
            state=sealed_session.build_state(),
        )

    dataset = scanner.set_data
    if import_text is None:
        pool, error = generate_random_pool(dataset)
    else:
        pool, error = parse_pool_text(dataset, import_text)

    if error:
        return SealedActionVM(
            ok=False, message=error, state=sealed_session.build_state()
        )

    sealed_session.load_external_pool(pool, new_session_id())
    return SealedActionVM(
        ok=True,
        message=f"Practice pool ready ({len(pool)} cards).",
        state=sealed_session.build_state(),
    )
