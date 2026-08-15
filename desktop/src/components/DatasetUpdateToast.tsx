import { EVENTS, type DatasetsUpdatedPayload } from "../api/events";
import { useLanguage } from "../i18n/useLanguage";
import { useToastEvent } from "../state/useToastEvent";

/** Toast shown when the background dataset check (dataset_notifier.py) actually
 *  downloaded something. Self-subscribing: no parent state, mounts once next to
 *  the error toast and listens for datasets://updated for its whole life. */
export function DatasetUpdateToast() {
  const { t } = useLanguage();
  const payload = useToastEvent<DatasetsUpdatedPayload>(
    EVENTS.datasetsUpdated,
    8000,
  );

  // Translate at render from the raw payload — a string frozen in state at
  // event time would stay in the old language after a language switch.
  return payload === null ? null : (
    <div className="dataset-toast">
      {t("datasets.updatedToast", { n: payload.updatedCount })}
    </div>
  );
}
