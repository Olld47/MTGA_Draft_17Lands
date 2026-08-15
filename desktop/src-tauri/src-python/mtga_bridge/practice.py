"""
mtga_bridge.practice
Practice-pool adapter for the desktop bridge. Builds a practice Sealed pool —
either six randomly generated packs or an MTGA decklist pasted by the user —
delegating the pure construction to src.practice_actions (the single
implementation both this bridge and the legacy tkinter dialog consume —
ticket 09 convergence), and hands the pool to SealedStudioSession.

No tkinter, no pytauri. The dialog reads the set list from the app context
and the decklist from the tkinter clipboard; here the set list comes from the
scanner and the decklist text arrives as an argument.
"""

import logging
from typing import List, Optional

from src.practice_actions import (
    build_set_options,
    dataset_rank,
    generate_random_pool,
    new_session_id,
    parse_pool_text,
)
from src.utils import read_local_manifest, retrieve_local_set_list

from mtga_bridge.datasets import select_dataset_blocking
from mtga_bridge.viewmodels import PracticeSetsVM, PracticeSetVM, SealedActionVM

logger = logging.getLogger(__name__)


# --- Set listing --------------------------------------------------------------


def list_practice_sets(scanner) -> PracticeSetsVM:
    """Set dropdown options for the frontend: manifest-active sets first in
    manifest order, the rest follow alphabetically (shared
    build_set_options from src.practice_actions)."""
    set_list = getattr(scanner, "set_list", None)
    sets_data = getattr(set_list, "data", {}) or {}
    if not sets_data:
        return PracticeSetsVM()

    active_codes = list(read_local_manifest().get("active_sets", []) or [])
    latest = getattr(set_list, "latest_set", "")
    options = build_set_options(sets_data, active_codes, latest)

    vms = [
        PracticeSetVM(
            code=o["code"],
            name=o["name"],
            label=f"{o['name']} ({o['code']})",
            is_active=o["is_active"],
        )
        for o in options
    ]
    return PracticeSetsVM(sets=vms, default_code=vms[0].code if vms else "")


# --- Dataset selection --------------------------------------------------------


def _load_set_dataset(scanner, config, set_code: str) -> bool:
    """Switches the whole app to the best downloaded dataset for `set_code`, so
    the practice pool's stats match every other view. Sealed data is preferred,
    then Premier, then Traditional."""
    datasets, _ = retrieve_local_set_list(codes=[set_code])
    if not datasets:
        return False
    best = min(datasets, key=lambda d: dataset_rank(d[1]))
    return select_dataset_blocking(scanner, config, best[6])


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
