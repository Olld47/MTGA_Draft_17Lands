import { useCallback, useEffect, useState } from "react";

import {
  deleteTierLists,
  getTierLists,
  importTierList,
} from "../../api/client";
import type { TierListEntry, TierLists } from "../../api/types";
import { DataTable, type Column } from "../../components/DataTable";

export function TiersPage() {
  const [lists, setLists] = useState<TierLists | null>(null);
  const [url, setUrl] = useState("");
  const [label, setLabel] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    getTierLists().then(setLists).catch(console.warn);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const doImport = () => {
    if (!url.trim()) return;
    setBusy(true);
    setMessage("");
    importTierList(url.trim(), label.trim())
      .then((r) => {
        setLists(r.lists);
        setMessage(r.message);
        if (r.ok) {
          setUrl("");
          setLabel("");
        }
      })
      .catch((e) => setMessage(String(e)))
      .finally(() => setBusy(false));
  };

  const remove = (entry: TierListEntry) => {
    deleteTierLists([entry.fileName])
      .then((r) => {
        setLists(r.lists);
        setMessage(r.message);
      })
      .catch((e) => setMessage(String(e)));
  };

  const columns: Column<TierListEntry>[] = [
    {
      id: "set",
      header: "Set",
      cell: (t) => <span className="card-name">{t.setCode}</span>,
      sortValue: (t) => t.setCode,
    },
    {
      id: "label",
      header: "Label",
      cell: (t) => t.label,
      sortValue: (t) => t.label,
    },
    {
      id: "date",
      header: "Added",
      cell: (t) => t.date || "—",
      sortValue: (t) => t.date,
    },
    {
      id: "actions",
      header: "",
      cell: (t) => (
        <button className="ghost-btn" onClick={() => remove(t)}>
          Delete
        </button>
      ),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)" }}>
      <section className="panel">
        <h2>Import a tier list</h2>
        <div className="download-form">
          <label className="field" style={{ flex: 2 }}>
            <span>17Lands / URL</span>
            <input
              value={url}
              placeholder="https://www.17lands.com/tier_list/..."
              onChange={(e) => setUrl(e.target.value)}
            />
          </label>
          <label className="field">
            <span>Label (optional)</span>
            <input value={label} onChange={(e) => setLabel(e.target.value)} />
          </label>
          <button onClick={doImport} disabled={busy || !url.trim()}>
            {busy ? "Importing..." : "Import"}
          </button>
        </div>
        {message && <div className="sim-note">{message}</div>}
      </section>

      <section className="panel">
        <h2>Installed tier lists</h2>
        <DataTable
          columns={columns}
          rows={lists?.lists ?? []}
          rowKey={(t) => t.fileName}
          defaultSort={{ id: "date", desc: true }}
          emptyText="Import a tier list to fold community grades into your picks"
        />
      </section>
    </div>
  );
}
