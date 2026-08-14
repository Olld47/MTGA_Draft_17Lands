import { useEffect, useState } from "react";

import { EVENTS, on, type DatasetSyncFailedPayload } from "../api/events";
import { useLanguage } from "../i18n/useLanguage";

/** Toast shown when the background dataset check (dataset_notifier.py) fails —
 *  the once-per-day stamp is NOT written, so the next launch retries, and this
 *  makes the failure visible instead of silently serving yesterday's data.
 *  Self-subscribing: mounts once next to the other toasts and listens for
 *  datasets://syncFailed for its whole life. */
export function DatasetSyncFailedToast() {
  const { t } = useLanguage();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const un = on<DatasetSyncFailedPayload>(EVENTS.datasetsSyncFailed, () => {
      if (cancelled) return;
      setFailed(true);
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        if (!cancelled) setFailed(false);
      }, 10000);
    });

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      un.then((f) => f());
    };
  }, []);

  return failed ? <div className="error-toast">{t("datasets.syncFailedToast")}</div> : null;
}
