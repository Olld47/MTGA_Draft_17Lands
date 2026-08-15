import { useCallback, useEffect, useState } from "react";

import {
  deleteTierLists,
  getTierLists,
  importTierList,
} from "../../api/client";
import type { TierListEntry, TierLists } from "../../api/types";
import { DataTable, type Column } from "../../components/DataTable";
import { useLanguage } from "../../i18n/useLanguage";

export function TiersPage() {
  const { t } = useLanguage();
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
      header: t("tiers.colSet"),
      cell: (e) => <span className="card-name">{e.setCode}</span>,
      sortValue: (e) => e.setCode,
    },
    {
      id: "label",
      header: t("tiers.colLabel"),
      cell: (e) => e.label,
      sortValue: (e) => e.label,
    },
    {
      id: "date",
      header: t("tiers.colAdded"),
      cell: (e) => e.date || "—",
      sortValue: (e) => e.date,
    },
    {
      id: "actions",
      header: "",
      cell: (e) => (
        <button className="ghost-btn" onClick={() => remove(e)}>
          {t("tiers.delete")}
        </button>
      ),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)" }}>
      <section className="panel">
        <h2>{t("tiers.importTitle")}</h2>
        <div className="download-form">
          <label className="field" style={{ flex: 2 }}>
            <span>{t("tiers.urlLabel")}</span>
            <input
              value={url}
              placeholder={t("tiers.urlPlaceholder")}
              onChange={(e) => setUrl(e.target.value)}
            />
          </label>
          <label className="field">
            <span>{t("tiers.labelOptional")}</span>
            <input value={label} onChange={(e) => setLabel(e.target.value)} />
          </label>
          <button onClick={doImport} disabled={busy || !url.trim()}>
            {busy ? t("tiers.importing") : t("tiers.import")}
          </button>
        </div>
        {message && <div className="sim-note">{message}</div>}
      </section>

      <section className="panel">
        <h2>{t("tiers.installed")}</h2>
        <DataTable
          columns={columns}
          rows={lists?.lists ?? []}
          rowKey={(e) => e.fileName}
          defaultSort={{ id: "date", desc: true }}
          emptyText={t("tiers.empty")}
        />
      </section>
    </div>
  );
}
