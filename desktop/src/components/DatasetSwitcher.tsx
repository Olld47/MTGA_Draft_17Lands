import { useEffect, useRef, useState } from "react";

import { selectDataset } from "../api/client";
import type { DatasetSwitcher } from "../api/types";

/** Masthead event-type + user-group dataset switcher, a port of the legacy
 *  top_bar om_event / om_group dropdowns. Selecting a combination loads that
 *  dataset file (which the backend makes the active one for every view). */
export function DatasetSwitcher({ switcher }: { switcher: DatasetSwitcher }) {
  const [event, setEvent] = useState("");
  const [group, setGroup] = useState("");
  const syncedKey = useRef("");

  // Sync the dropdowns to the backend's reported (active|detected) selection,
  // but only when that actually changed — a per-pick draftRefresh returns a
  // fresh object with identical values, which must not clobber a manual pick.
  useEffect(() => {
    const key = `${switcher.activeEvent}|${switcher.activeGroup}|${switcher.detectedEvent}`;
    if (key === syncedKey.current) return;
    syncedKey.current = key;

    const events = switcher.events;
    if (events.length === 0) {
      setEvent("");
      setGroup("");
      return;
    }
    let ev =
      switcher.activeEvent ?? switcher.detectedEvent ?? events[0]?.name ?? "";
    if (!events.some((e) => e.name === ev)) ev = events[0]?.name ?? "";
    setEvent(ev);

    const current = events.find((e) => e.name === ev);
    let grp =
      switcher.activeEvent === ev && switcher.activeGroup
        ? switcher.activeGroup
        : "";
    if (!grp && current) {
      grp = current.groups.some((g) => g.name === "All")
        ? "All"
        : (current.groups[0]?.name ?? "");
    }
    setGroup(grp);
  }, [switcher]);

  const currentEvent = switcher.events.find((e) => e.name === event);
  const groups = currentEvent?.groups ?? [];

  const pick = (ev: string, grp: string) => {
    const entry = switcher.events
      .find((e) => e.name === ev)
      ?.groups.find((g) => g.name === grp);
    if (entry) selectDataset(entry.path).catch(console.warn);
  };

  const onEvent = (value: string) => {
    setEvent(value);
    const e = switcher.events.find((x) => x.name === value);
    const g = e?.groups.some((x) => x.name === "All")
      ? "All"
      : (e?.groups[0]?.name ?? "");
    setGroup(g);
    pick(value, g);
  };

  if (switcher.events.length === 0) return null;

  return (
    <span className="dataset-switcher">
      <select
        value={event}
        onChange={(e) => onEvent(e.target.value)}
        title={`Dataset event type — ${switcher.setCode}`}
      >
        {switcher.events.map((e) => (
          <option key={e.name} value={e.name}>
            {e.name}
          </option>
        ))}
      </select>
      <select
        value={group}
        onChange={(e) => {
          const v = e.target.value;
          setGroup(v);
          pick(event, v);
        }}
        title="Dataset user group"
      >
        {groups.map((g) => (
          <option key={g.name} value={g.name}>
            {g.name}
          </option>
        ))}
      </select>
    </span>
  );
}
