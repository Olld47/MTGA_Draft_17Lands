import { EVENTS, type DatasetSyncFailedPayload } from "../api/events";
import { useLanguage } from "../i18n/useLanguage";
import { useToastEvent } from "../state/useToastEvent";

/** Toast shown when the background dataset check (dataset_notifier.py) fails —
 *  the once-per-day stamp is NOT written, so the next launch retries, and this
 *  makes the failure visible instead of silently serving yesterday's data.
 *  Self-subscribing: mounts once next to the other toasts and listens for
 *  datasets://syncFailed for its whole life. */
export function DatasetSyncFailedToast() {
  const { t } = useLanguage();
  const failed = useToastEvent<DatasetSyncFailedPayload>(
    EVENTS.datasetsSyncFailed,
    10000,
  );

  return failed ? <div className="error-toast">{t("datasets.syncFailedToast")}</div> : null;
}
