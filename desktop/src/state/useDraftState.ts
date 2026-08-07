import { useCallback, useEffect, useRef, useState } from "react";

import { getDraftState } from "../api/client";
import { EVENTS, on, type RefreshPayload, type StatusPayload } from "../api/events";
import type { DraftState } from "../api/types";
import { t } from "../i18n/useLanguage";

/** Listens for draft://refresh and re-fetches the full draft state.
 *  A monotonically increasing sequence drops stale responses. */
export function useDraftState(booted: boolean) {
  const [state, setState] = useState<DraftState | null>(null);
  const [statusText, setStatusText] = useState(t("state.waitingDraft"));
  const seqRef = useRef(0);

  const refresh = useCallback(async () => {
    const mySeq = ++seqRef.current;
    try {
      const s = await getDraftState();
      if (mySeq === seqRef.current) {
        setState(s);
        setStatusText(
          s.pack > 0
            ? t("state.packPick", { pack: s.pack, pick: s.pick })
            : t("state.waitingDraft"),
        );
      }
    } catch (e) {
      // Booting or transient failure — keep the previous state.
      console.warn("get_draft_state failed", e);
    }
  }, []);

  useEffect(() => {
    if (!booted) return;
    refresh();

    const unlisteners = [
      on<RefreshPayload>(EVENTS.draftRefresh, () => refresh()),
      on<StatusPayload>(EVENTS.draftStatus, (p) => setStatusText(p.text)),
    ];
    return () => {
      unlisteners.forEach((u) => u.then((f) => f()));
    };
  }, [booted, refresh]);

  return { state, statusText, refresh };
}
