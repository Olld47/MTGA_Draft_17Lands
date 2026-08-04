import { useFileTools } from "../../state/useFileTools";
import { useFilterOptions } from "../../state/useFilterOptions";
import { useSettings } from "../../state/useSettings";

const RESULT_FORMATS = ["Percentage", "Rating", "Grade"];

const FILTER_FORMATS = ["Colors", "Names"];

const THEMES = ["System", "Dark", "Light"];

interface ToggleRowProps {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}

function ToggleRow({ label, hint, checked, onChange }: ToggleRowProps) {
  return (
    <div className="setting-row">
      <label>
        {label}
        {hint && <div className="hint">{hint}</div>}
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
  const { settings, patch } = useSettings();
  const { busy, message, browseLogFile, browseMtgaData } = useFileTools();
  const filters = useFilterOptions(settings?.filterFormat);

  if (!settings) {
    return <div className="empty-state">Loading settings...</div>;
  }

  // card_logic.filter_options reports "All Decks" until pick 5, which as a
  // detection result means "not enough pool yet" rather than a chosen lane.
  const detected = filters?.autoDetected ?? "";
  const autoHint =
    settings.deckFilter !== "Auto"
      ? "Auto detects your two strongest colors"
      : !detected || detected === "All Decks"
        ? "Auto: detecting..."
        : `Auto: ${filters?.autoDetectedLabel || detected}`;

  return (
    <div className="settings-grid">
      <section className="settings-group">
        <h2>Display</h2>
        <div className="setting-row">
          <label>
            Appearance
            <div className="hint">System follows your OS light/dark setting</div>
          </label>
          <select
            value={settings.desktopTheme}
            onChange={(e) => patch({ desktopTheme: e.target.value })}
          >
            {THEMES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div className="setting-row">
          <label>
            Deck filter
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
            Deck filter format
            <div className="hint">Names shows "Azorius" instead of "WU"</div>
          </label>
          <select
            value={settings.filterFormat}
            onChange={(e) => patch({ filterFormat: e.target.value })}
          >
            {FILTER_FORMATS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>
        <div className="setting-row">
          <label>Result format</label>
          <select
            value={settings.resultFormat}
            onChange={(e) => patch({ resultFormat: e.target.value })}
          >
            {RESULT_FORMATS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>
        <ToggleRow
          label="Color-code card rows"
          hint="Tints table rows by mana color"
          checked={settings.cardColorsEnabled}
          onChange={(v) => patch({ cardColorsEnabled: v })}
        />
      </section>

      <section className="settings-group">
        <h2>Data</h2>
        <ToggleRow
          label="Auto-sync cloud datasets"
          hint="Downloads pre-compiled 17Lands datasets at startup"
          checked={settings.autoSyncDatasets}
          onChange={(v) => patch({ autoSyncDatasets: v })}
        />
        <ToggleRow
          label="Save draft logs"
          hint="Keeps per-draft logs in the Logs folder for 30 days"
          checked={settings.draftLogEnabled}
          onChange={(v) => patch({ draftLogEnabled: v })}
        />
        <ToggleRow
          label="Missing dataset notifications"
          checked={settings.missingNotificationsEnabled}
          onChange={(v) => patch({ missingNotificationsEnabled: v })}
        />
      </section>

      <section className="settings-group">
        <h2>Locations</h2>
        <div className="setting-row">
          <label>
            Arena log
            <div className="hint path">{settings.arenaLogLocation || "not set"}</div>
          </label>
          <button
            disabled={busy}
            onClick={() =>
              browseLogFile().then((path) => {
                if (path) patch({ arenaLogLocation: path });
              })
            }
          >
            Browse...
          </button>
        </div>
        <div className="setting-row">
          <label>
            MTGA database
            <div className="hint path">{settings.databaseLocation || "not set"}</div>
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
            Locate...
          </button>
        </div>
        {message && <div className="setting-note">{message}</div>}
      </section>
    </div>
  );
}
