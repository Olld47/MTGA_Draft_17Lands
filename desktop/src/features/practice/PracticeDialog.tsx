import { useEffect, useState } from "react";

import { listPracticeSets, startPractice } from "../../api/client";
import type { PracticeSet, SealedAction } from "../../api/types";
import { useLanguage } from "../../i18n/useLanguage";

type Mode = "generate" | "import";

export function PracticeDialog({
  onClose,
  onStarted,
}: {
  onClose: () => void;
  onStarted: (result: SealedAction) => void;
}) {
  const { t } = useLanguage();
  const [sets, setSets] = useState<PracticeSet[]>([]);
  const [setCode, setSetCode] = useState("");
  const [mode, setMode] = useState<Mode>("generate");
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listPracticeSets()
      .then((r) => {
        setSets(r.sets);
        setSetCode(r.defaultCode);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const confirm = () => {
    setBusy(true);
    setError("");
    startPractice(setCode, mode === "import" ? text : undefined)
      .then((r) => {
        if (r.ok) {
          onStarted(r);
          onClose();
        } else {
          setError(r.message);
        }
      })
      .catch((e) => setError(String(e)))
      .finally(() => setBusy(false));
  };

  const active = sets.filter((s) => s.isActive);
  const inactive = sets.filter((s) => !s.isActive);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-label={t("practice.aria")}
        onClick={(e) => e.stopPropagation()}
      >
        <h2>{t("practice.title")}</h2>

        <label className="modal-field">
          <span>{t("practice.set")}</span>
          <select
            className="archetype-select"
            value={setCode}
            onChange={(e) => setSetCode(e.target.value)}
          >
            {active.length > 0 && (
              <optgroup label={t("practice.active")}>
                {active.map((s) => (
                  <option key={s.code} value={s.code}>
                    {s.label}
                  </option>
                ))}
              </optgroup>
            )}
            {inactive.length > 0 && (
              <optgroup label={t("practice.otherSets")}>
                {inactive.map((s) => (
                  <option key={s.code} value={s.code}>
                    {s.label}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        </label>

        <div className="modal-modes">
          <label>
            <input
              type="radio"
              checked={mode === "generate"}
              onChange={() => setMode("generate")}
            />
            {t("practice.generate6")}
          </label>
          <label>
            <input
              type="radio"
              checked={mode === "import"}
              onChange={() => setMode("import")}
            />
            {t("practice.importPool")}
          </label>
        </div>

        {mode === "import" && (
          <textarea
            className="modal-textarea"
            placeholder={t("practice.placeholder")}
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={8}
          />
        )}

        {error && <div className="boot-error">{error}</div>}

        <div className="modal-actions">
          <button className="ghost-btn" onClick={onClose}>
            {t("practice.cancel")}
          </button>
          <button
            onClick={confirm}
            disabled={busy || !setCode || (mode === "import" && !text.trim())}
          >
            {mode === "import" ? t("practice.importPoolBtn") : t("practice.generatePool")}
          </button>
        </div>
      </div>
    </div>
  );
}
