"""Player.log event strings for draft/scanner event detection.

Fuzzy-matched by src/log_scanner.py — never exact-equality matched — so minor
Arena log format updates survive. Quick Draft uses `BotDraft_*` strings with
0-indexed pack/pick numbers; pick-two drafts use the PickTwo event.
"""

DRAFT_LOG_PREFIX = "DraftLog_"

DRAFT_DETECTION_CATCH_ALL = ["Draft", "draft"]

DRAFT_START_STRING_PREMIER = "[UnityCrossThreadLogger]==> Event_Join "
DRAFT_PICK_STRING_PREMIER = "[UnityCrossThreadLogger]==> Event_PlayerDraftMakePick "
DRAFT_PICK_STRING_PREMIER_OLD = "[UnityCrossThreadLogger]==> Draft.MakeHumanDraftPick "
DRAFT_PACK_STRING_PREMIER = "[UnityCrossThreadLogger]Draft.Notify "

DRAFT_START_STRING_QUICK_DRAFT = "[UnityCrossThreadLogger]==> BotDraft_DraftStatus "
DRAFT_PACK_STRING_QUICK = "DraftPack"
DRAFT_PICK_STRING_QUICK = "[UnityCrossThreadLogger]==> BotDraft_DraftPick "

DRAFT_START_STRINGS = [DRAFT_START_STRING_PREMIER, DRAFT_START_STRING_QUICK_DRAFT]

PICK_TWO_EVENT_STRING = "PickTwo"

__all__ = [
    "DRAFT_LOG_PREFIX",
    "DRAFT_DETECTION_CATCH_ALL",
    "DRAFT_START_STRING_PREMIER",
    "DRAFT_PICK_STRING_PREMIER",
    "DRAFT_PICK_STRING_PREMIER_OLD",
    "DRAFT_PACK_STRING_PREMIER",
    "DRAFT_START_STRING_QUICK_DRAFT",
    "DRAFT_PACK_STRING_QUICK",
    "DRAFT_PICK_STRING_QUICK",
    "DRAFT_START_STRINGS",
    "PICK_TWO_EVENT_STRING",
]
