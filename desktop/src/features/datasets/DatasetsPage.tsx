import { useCallback, useEffect, useState } from "react";

import {
  deleteDataset,
  downloadDataset,
  listAvailableSets,
  listDatasets,
  selectDataset,
} from "../../api/client";
import type { AvailableSet, DatasetInfo, DatasetList } from "../../api/types";
import { DataTable, type Column } from "../../components/DataTable";
import { useLanguage } from "../../i18n/useLanguage";

const EVENT_TYPES = ["PremierDraft", "TradDraft", "QuickDraft", "Sealed", "TradSealed"];
const USER_GROUPS = ["All", "Top", "Middle", "Bottom"];

interface DownloadState {
  running: boolean;
  percent: number;
  status: string;
}

interface Props {
  /** Set code of the current draft when no dataset is loaded (missing-dataset banner). */
  missingSet?: string;
}

export function DatasetsPage({ missingSet }: Props) {
  const { t } = useLanguage();
  const [list, setList] = useState<DatasetList | null>(null);
  const [sets, setSets] = useState<AvailableSet[]>([]);
  const [setCode, setSetCode] = useState("");
  const [eventType, setEventType] = useState("PremierDraft");
  const [userGroup, setUserGroup] = useState("All");
  const [dl, setDl] = useState<DownloadState>({
    running: false,
    percent: 0,
    status: "",
  });
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    listDatasets().then(setList).catch(console.warn);
  }, []);

  useEffect(() => {
    refresh();
    listAvailableSets()
      .then((r) => {
        setSets(r.sets);
        if (r.sets.length > 0) setSetCode(r.sets[0].name);
      })
      .catch(console.warn);
  }, [refresh]);

  useEffect(() => {
    if (missingSet) setSetCode(missingSet);
  }, [missingSet]);

  const startDownload = async () => {
    if (!setCode || dl.running) return;
    setError("");
    setDl({ running: true, percent: 0, status: t("datasets.starting") });
    try {
      const result = await downloadDataset(setCode, eventType, userGroup, (p) => {
        setDl((prev) => ({
          running: true,
          percent: p.kind === "percent" ? p.value : prev.percent,
          status: p.kind === "status" ? p.text : prev.status,
        }));
      });
      if (!result.ok) setError(result.message);
      refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setDl((prev) => ({ ...prev, running: false }));
    }
  };

  const columns: Column<DatasetInfo>[] = [
    {
      id: "label",
      header: t("datasets.colDataset"),
      cell: (d) => (
        <span className="card-name">
          {d.isActive ? "● " : ""}
          {d.label}
        </span>
      ),
      sortValue: (d) => d.label,
    },
    {
      id: "modified",
      header: t("datasets.colUpdated"),
      numeric: true,
      cell: (d) =>
        d.modified ? new Date(d.modified * 1000).toLocaleDateString() : "—",
      sortValue: (d) => d.modified,
    },
    {
      id: "size",
      header: t("datasets.colSize"),
      numeric: true,
      cell: (d) => `${(d.sizeBytes / 1024 / 1024).toFixed(1)} MB`,
      sortValue: (d) => d.sizeBytes,
    },
    {
      id: "actions",
      header: "",
      cell: (d) => (
        <span style={{ display: "inline-flex", gap: 6 }}>
          {!d.isActive && (
            <button onClick={() => selectDataset(d.path).then(refresh)}>
              {t("datasets.use")}
            </button>
          )}
          <button
            onClick={() => deleteDataset(d.path).then(setList).catch((e) => setError(String(e)))}
          >
            {t("datasets.delete")}
          </button>
        </span>
      ),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)" }}>
      {missingSet && (
        <div className="dataset-banner">
          <span>{t("datasets.missingBanner", { set: missingSet })}</span>
        </div>
      )}

      <section className="panel">
        <h2>{t("datasets.downloadTitle")}</h2>
        <div className="download-form">
          <label className="field">
            <span>{t("datasets.set")}</span>
            <select value={setCode} onChange={(e) => setSetCode(e.target.value)}>
              {sets.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{t("datasets.event")}</span>
            <select
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
            >
              {EVENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{t("datasets.players")}</span>
            <select
              value={userGroup}
              onChange={(e) => setUserGroup(e.target.value)}
            >
              {USER_GROUPS.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </label>
          <button onClick={startDownload} disabled={dl.running || !setCode}>
            {dl.running ? t("datasets.downloading") : t("datasets.download")}
          </button>
        </div>
        {(dl.running || dl.status) && (
          <div>
            <div className="progress-track">
              <div
                className="progress-fill"
                style={{ width: `${Math.min(100, dl.percent)}%` }}
              />
            </div>
            <div className="progress-status">{dl.status}</div>
          </div>
        )}
        {error && <div className="boot-error">{error}</div>}
      </section>

      <section className="panel">
        <h2>{t("datasets.local")}</h2>
        <DataTable
          columns={columns}
          rows={list?.datasets ?? []}
          rowKey={(d) => d.path}
          defaultSort={{ id: "modified", desc: true }}
          emptyText={t("datasets.empty")}
        />
      </section>
    </div>
  );
}
