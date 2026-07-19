import { useSettings } from "../../state/useSettings";

const DECK_FILTERS = [
  "Auto",
  "All Decks",
  "W", "U", "B", "R", "G",
  "WU", "WB", "WR", "WG", "UB", "UR", "UG", "BR", "BG", "RG",
];

const RESULT_FORMATS = ["Percentage", "Rating", "Grade"];

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

  if (!settings) {
    return <div className="empty-state">Loading settings...</div>;
  }

  return (
    <div className="settings-grid">
      <section className="settings-group">
        <h2>Display</h2>
        <div className="setting-row">
          <label>
            Deck filter
            <div className="hint">Auto detects your two strongest colors</div>
          </label>
          <select
            value={settings.deckFilter}
            onChange={(e) => patch({ deckFilter: e.target.value })}
          >
            {DECK_FILTERS.map((f) => (
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
            <div className="hint">{settings.arenaLogLocation || "not set"}</div>
          </label>
        </div>
        <div className="setting-row">
          <label>
            MTGA database
            <div className="hint">{settings.databaseLocation || "not set"}</div>
          </label>
        </div>
      </section>
    </div>
  );
}
