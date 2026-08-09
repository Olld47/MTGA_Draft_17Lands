import { useCallback, useEffect, useState } from "react";

import { listDraftLogs, setLogFile } from "../api/client";
import { EVENTS, on, type RefreshPayload } from "../api/events";
import type { DraftLog } from "../api/types";

/** The live Arena log plus the saved DraftLog_* files, for the masthead
 *  switcher. `currentName` comes from DraftState.logName rather than being
 *  tracked here: the orchestrator snaps back to the live log on its own when it
 *  sees draft activity (src/ui/orchestrator.py), so the selection has to follow
 *  the scanner, not the last click. */
export function useDraftLogs(booted: boolean, currentName: string) {
  const [logs, setLogs] = useState<DraftLog[]>([]);
  const [swapping, setSwapping] = useState(false);

  const refresh = useCallback(() => {
    listDraftLogs()
      .then((r) => setLogs(r.logs))
      .catch((e) => console.warn("list_draft_logs failed", e));
  }, []);

  useEffect(() => {
    if (!booted) return;
    refresh();
    const un = on<RefreshPayload>(EVENTS.draftRefresh, refresh);
    return () => {
      un.then((f) => f());
    };
  }, [booted, refresh]);

  const select = useCallback(
    async (path: string) => {
      setSwapping(true);
      try {
        await setLogFile(path);
      } catch (e) {
        console.warn("set_log_file failed", e);
      } finally {
        setSwapping(false);
      }
    },
    [],
  );

  const selected =
    logs.find((l) => l.fileName === currentName)?.path ??
    // Reconnect fallback (legacy update_history_dropdown's options[0] default):
    // before the scanner's logName resolves — or when it matches no listed log —
    // default to the newest saved draft record by timestamp instead of leaving
    // the dropdown empty. The live log is skipped: a "轮抓记录" is a DraftLog_*
    // file, and when the scanner is on live it already matches by fileName.
    logs.find((l) => !l.isLive)?.path ??
    logs[0]?.path ??
    "";
  return { logs, selected, swapping, select };
}
