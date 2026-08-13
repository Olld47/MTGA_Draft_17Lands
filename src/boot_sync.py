"""
src/boot_sync.py
Typed outcome of the boot-time dataset sync, shared by the producer
(src.bootstrap._sync_cloud_datasets), the forwarder (mtga_bridge.boot), and
the consumer (mtga_bridge.dataset_notifier). Kept import-light — only stdlib
dataclasses — so the notifier can import it at module load without dragging in
the scanner/dataset stack.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BootSyncOutcome:
    """What the boot-time dataset sync did.

    `attempted` is the discriminator the notifier keys on: whether boot
    actually ran a sync at all. `downloaded` carries how many datasets that
    run downloaded (0 when unchanged or the sync failed). Naming the two
    states as fields instead of a bare Optional[int] makes the None/0/>0
    tri-state explicit — a falsy default (0, None) can no longer be passed
    in place of a real outcome, and the notifier never discriminates on
    truthiness.

    `already_synced_today` marks the once-per-UTC-day skip: boot did NOT run
    a sync because today's auto-sync already ran (an earlier boot, the
    post-boot check, or the upgrade refresh). The desktop notifier treats this
    like an attempted sync — report nothing and do NOT run the fresh silent
    sync a not-attempted outcome would trigger ~1.5s after boot.
    """

    attempted: bool
    downloaded: int = 0
    already_synced_today: bool = False


# The "boot never attempted a sync" state (auto-sync off and not an upgrade).
# A frozen dataclass instance is safe to share.
BOOT_NOT_ATTEMPTED = BootSyncOutcome(attempted=False)

# The "boot skipped because today's auto-sync already ran" state.
BOOT_SKIPPED_TODAY = BootSyncOutcome(attempted=False, already_synced_today=True)
