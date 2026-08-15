import { useState } from "react";

import { useLanguage } from "../../i18n/useLanguage";
import { useFileTools } from "../../state/useFileTools";
import { useFilterOptions } from "../../state/useFilterOptions";
import { useSettings } from "../../state/useSettings";

// Option arrays carry the persisted value + a label i18n key: the <select>
// value stays the backend string ("Percentage", "Dark", ...) while the option
// text is translated.
const RESULT_FORMATS = [
  { value: "Percentage", labelKey: "settings.resultFormat.percentage" },
  { value: "Rating", labelKey: "settings.resultFormat.ratingValue" },
  { value: "Grade", labelKey: "settings.resultFormat.grade" },
];

const FILTER_FORMATS = [
  { value: "Colors", labelKey: "settings.filterFormat.colors" },
  { value: "Names", labelKey: "settings.filterFormat.names" },
];

const THEMES = [
  { value: "System", labelKey: "settings.theme.system" },
  { value: "Dark", labelKey: "settings.theme.dark" },
  { value: "Light", labelKey: "settings.theme.light" },
];

// Languages name themselves (a locale's endonym is never translated).
const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "zh", label: "简体中文" },
];

// The legacy uiSize setting is a percentage string (UI_SIZE_DICT, 40%..250%),
// and the <select> label IS the persisted value — no i18n key needed.
const UI_SCALES = [
  "40%", "50%", "60%", "70%", "80%", "90%", "100%",
  "110%", "120%", "130%", "140%", "150%", "160%", "170%",
  "180%", "190%", "200%", "210%", "220%", "230%", "240%", "250%",
];

interface ToggleRowProps {
  labelKey: string;
  hintKey?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}

function ToggleRow({ labelKey, hintKey, checked, onChange }: ToggleRowProps) {
  const { t } = useLanguage();
  return (
    <div className="setting-row">
      <label>
        {t(labelKey)}
        {hintKey && <div className="hint">{t(hintKey)}</div>}
      </label>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
    </div>
  );
}

export function SettingsPage() {
  const { settings, patch, reset } = useSettings();
  const { t } = useLanguage();
  const { busy, message, browseLogFile, browseMtgaData } = useFileTools();
  const filters = useFilterOptions(settings?.filterFormat);
  // Two-click confirm — Tauri's webview doesn't reliably support
  // window.confirm, so the button arms itself on the first click.
  const [confirmReset, setConfirmReset] = useState(false);

  const restoreDefaults = () => {
    if (!confirmReset) {
      setConfirmReset(true);
      return;
    }
    setConfirmReset(false);
    reset();
  };

  if (!settings) {
    return <div className="empty-state">{t("settings.loading")}</div>;
  }

  // card_logic.filter_options reports "All Decks" until pick 5, which as a
  // detection result means "not enough pool yet" rather than a chosen lane.
  const detected = filters?.autoDetected ?? "";
  const autoHint =
    settings.deckFilter !== "Auto"
      ? t("settings.deckFilterAutoHint")
      : !detected || detected === "All Decks"
        ? t("settings.deckFilterAutoDetecting")
        : t("settings.deckFilterAuto", {
            label: filters?.autoDetectedLabel || detected,
          });

  return (
    <div className="settings-grid">
      <section className="settings-group">
        <h2>{t("settings.display")}</h2>
        <div className="setting-row">
          <label>
            {t("settings.appearance")}
            <div className="hint">{t("settings.appearanceHint")}</div>
          </label>
          <select
            value={settings.desktopTheme}
            onChange={(e) => patch({ desktopTheme: e.target.value })}
          >
            {THEMES.map((o) => (
              <option key={o.value} value={o.value}>
                {t(o.labelKey)}
              </option>
            ))}
          </select>
        </div>
        <div className="setting-row">
          <label>
            {t("settings.uiSize")}
            <div className="hint">{t("settings.uiSizeHint")}</div>
          </label>
          <select
            value={settings.uiSize}
            onChange={(e) => patch({ uiSize: e.target.value })}
          >
            {UI_SCALES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="setting-row">
          <label>
            {t("settings.language")}
            <div className="hint">{t("settings.languageHint")}</div>
          </label>
          <select
            value={settings.language}
            onChange={(e) => patch({ language: e.target.value })}
          >
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
        </div>
        <div className="setting-row">
          <label>
            {t("settings.deckFilter")}
            <div className="hint">{autoHint}</div>
          </label>
          <select
            value={settings.deckFilter}
            onChange={(e) => patch({ deckFilter: e.target.value })}
          >
            {(
              filters?.options ?? [
                { key: settings.deckFilter, label: settings.deckFilter, winRate: null },
              ]
            ).map((f) => (
              <option key={f.key} value={f.key}>
                {f.winRate != null ? `${f.label} (${f.winRate}%)` : f.label}
              </option>
            ))}
          </select>
        </div>
        <div className="setting-row">
          <label>
            {t("settings.filterFormat")}
            <div className="hint">{t("settings.filterFormatHint")}</div>
          </label>
          <select
            value={settings.filterFormat}
            onChange={(e) => patch({ filterFormat: e.target.value })}
          >
            {FILTER_FORMATS.map((o) => (
              <option key={o.value} value={o.value}>
                {t(o.labelKey)}
              </option>
            ))}
          </select>
        </div>
        <div className="setting-row">
          <label>{t("settings.resultFormat")}</label>
          <select
            value={settings.resultFormat}
            onChange={(e) => patch({ resultFormat: e.target.value })}
          >
            {RESULT_FORMATS.map((o) => (
              <option key={o.value} value={o.value}>
                {t(o.labelKey)}
              </option>
            ))}
          </select>
        </div>
        <ToggleRow
          labelKey="settings.colorCode"
          hintKey="settings.colorCodeHint"
          checked={settings.cardColorsEnabled}
          onChange={(v) => patch({ cardColorsEnabled: v })}
        />
        <ToggleRow
          labelKey="settings.alwaysOnTop"
          hintKey="settings.alwaysOnTopHint"
          checked={settings.alwaysOnTop}
          onChange={(v) => patch({ alwaysOnTop: v })}
        />
      </section>

      <section className="settings-group">
        <h2>{t("settings.data")}</h2>
        <ToggleRow
          labelKey="settings.autoSync"
          hintKey="settings.autoSyncHint"
          checked={settings.autoSyncDatasets}
          onChange={(v) => patch({ autoSyncDatasets: v })}
        />
        <ToggleRow
          labelKey="settings.updateNotifications"
          hintKey="settings.updateNotificationsHint"
          checked={settings.updateNotificationsEnabled}
          onChange={(v) => patch({ updateNotificationsEnabled: v })}
        />
        <ToggleRow
          labelKey="settings.saveDraftLogs"
          hintKey="settings.saveDraftLogsHint"
          checked={settings.draftLogEnabled}
          onChange={(v) => patch({ draftLogEnabled: v })}
        />
        <ToggleRow
          labelKey="settings.missingDatasetNotifs"
          checked={settings.missingNotificationsEnabled}
          onChange={(v) => patch({ missingNotificationsEnabled: v })}
        />
      </section>

      <section className="settings-group">
        <h2>{t("settings.locations")}</h2>
        <div className="setting-row">
          <label>
            {t("settings.arenaLog")}
            <div className="hint path">
              {settings.arenaLogLocation || t("settings.notSet")}
            </div>
          </label>
          <button
            disabled={busy}
            onClick={() =>
              browseLogFile().then((path) => {
                if (path) patch({ arenaLogLocation: path });
              })
            }
          >
            {t("settings.browse")}
          </button>
        </div>
        <div className="setting-row">
          <label>
            {t("settings.mtgaDatabase")}
            <div className="hint path">
              {settings.databaseLocation || t("settings.notSet")}
            </div>
          </label>
          <button
            disabled={busy}
            onClick={() =>
              browseMtgaData().then((path) => {
                // locate_mtga_data already persisted it; mirror it locally.
                if (path) patch({ databaseLocation: path });
              })
            }
          >
            {t("settings.locate")}
          </button>
        </div>
        {message && <div className="setting-note">{message}</div>}
      </section>

      <section className="settings-group">
        <h2>{t("settings.reset")}</h2>
        <div className="setting-row">
          <label>
            {t("settings.restoreDefaults")}
            <div className="hint">{t("settings.restoreDefaultsHint")}</div>
          </label>
          <button
            className="ghost-btn"
            onClick={restoreDefaults}
            onBlur={() => setConfirmReset(false)}
          >
            {confirmReset
              ? t("settings.clickAgainToConfirm")
              : t("settings.restoreDefaults")}
          </button>
        </div>
      </section>
    </div>
  );
}
