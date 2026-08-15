"""
mtga_bridge.recap
Post-draft recap adapter for the desktop bridge. Computes the recap through
the shared src.recap_actions.build_recap_data (the single implementation both
this bridge and the legacy tkinter screen consume — ticket 09 convergence)
and maps the plain result to view-models for the frontend. The 17Lands
draft-record fetch is likewise delegated. No tkinter, no pytauri —
unit-testable from the root poetry environment.
"""

import logging
from typing import List, Optional

from src.recap_actions import build_recap_data, fetch_draft_record as fetch_record

from mtga_bridge.viewmodels import (
    DraftRecordVM,
    RecapArchetypeVM,
    RecapCardVM,
    RecapPickVM,
    RecapRoleVM,
    RecapVM,
)

logger = logging.getLogger(__name__)


def build_recap(taken_cards, metrics, draft_id, event_type) -> RecapVM:
    """Computes the post-draft recap and maps it to a view-model. Returns
    has_data=False when fewer than 40 cards are available."""
    data = build_recap_data(taken_cards, metrics, draft_id, event_type)
    if not data.has_data:
        return RecapVM(has_data=False)

    return RecapVM(
        has_data=True,
        pool_power=round(data.pool_power, 0),
        grade=data.grade,
        grade_style=data.grade_style,
        top_23_avg=round(data.top_23_avg, 1),
        format_avg=round(data.format_avg, 1),
        archetypes=[
            RecapArchetypeVM(
                name=name, win_rate=round(wr, 1) if wr and wr > 0 else None
            )
            for name, wr in data.archetypes
        ],
        best_cards=[
            RecapCardVM(name=name, win_rate=round(wr, 1))
            for name, wr in data.best_cards
        ],
        steals=[
            RecapPickVM(
                name=name,
                pack=pack,
                pick=pick,
                reference=round(reference, 1),
                delta=round(delta, 1),
            )
            for name, pack, pick, reference, delta in data.steals
        ],
        reaches=[
            RecapPickVM(
                name=name,
                pack=pack,
                pick=pick,
                reference=round(reference, 1),
                delta=round(delta, 1),
            )
            for name, pack, pick, reference, delta in data.reaches
        ],
        tribes=[RecapRoleVM(label=label, count=count) for label, count in data.tribes],
        roles=[RecapRoleVM(label=label, count=count) for label, count in data.roles],
        staples=[
            RecapCardVM(name=name, win_rate=round(wr, 1))
            for name, wr in data.staples
        ],
        non_basic_lands=[
            RecapCardVM(name=name, win_rate=round(wr, 1))
            for name, wr in data.non_basic_lands
        ],
        rares=[
            RecapCardVM(name=name, win_rate=round(wr, 1)) for name, wr in data.rares
        ],
        cmc_distribution=list(data.cmc_distribution),
        type_counts=dict(data.type_counts),
        is_sealed=data.is_sealed,
        draft_id=data.draft_id,
    )


def fetch_draft_record(draft_id: str) -> DraftRecordVM:
    """Blocking 17Lands draft-record fetch. Call off the event loop."""
    record = fetch_record(draft_id)
    if record is None:
        return DraftRecordVM(found=False)
    wins, losses, url = record
    return DraftRecordVM(found=True, wins=wins, losses=losses, url=url)
