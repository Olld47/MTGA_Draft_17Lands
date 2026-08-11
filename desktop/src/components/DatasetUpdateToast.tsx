import { useEffect, useState } from "react";

import { EVENTS, on, type DatasetsUpdatedPayload } from "../api/events";
import { useLanguage } from "../i18n/useLanguage";

/** Toast shown when the background dataset check (dataset_notifier.py) actually
 *  downloaded something. Self-subscribing: no parent state, mounts once next to
 *  the error toast and listens for datasets://updated for its whole life. */
export function DatasetUpdateToast() {
  const { t } = useLanguage();
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const un = on<DatasetsUpdatedPayload>(EVENTS.datasetsUpdated, (p) => {
      if (cancelled) return;
      setMessage(t("datasets.updatedToast", { n: p.updatedCount }));
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        if (!cancelled) setMessage("");
      }, 8000);
    });

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      un.then((f) => f());
    };
  }, [t]);

  return message ? <div className="dataset-toast">{message}</div> : null;
}
