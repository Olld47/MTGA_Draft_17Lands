import { useEffect, useState } from "react";

import { on } from "../api/events";

// The setTimeout handle type differs between the DOM (number) and Node
// (NodeJS.Timeout) libs; derive it once here, the module that owns every
// toast timer, instead of spelling either lib-specific name.
type TimerHandle = ReturnType<typeof setTimeout>;

/** Shared toast lifecycle: subscribes to `event` for the component's whole
 *  life, keeps the latest payload in state, and auto-dismisses it after
 *  `timeoutMs`. The cancelled flag plus `un.then((f) => f())` teardown guard
 *  against a late event or a pending timer firing after unmount. Returns
 *  `null` when no event has fired yet or the toast has auto-dismissed. */
export function useToastEvent<T>(event: string, timeoutMs: number): T | null {
  const [payload, setPayload] = useState<T | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: TimerHandle | undefined;

    const un = on<T>(event, (p) => {
      if (cancelled) return;
      setPayload(p);
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (!cancelled) setPayload(null);
      }, timeoutMs);
    });

    return () => {
      cancelled = true;
      clearTimeout(timer);
      un.then((f) => f());
    };
  }, [event, timeoutMs]);

  return payload;
}
