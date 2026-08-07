import { useMemo, useRef, useState, type ReactNode } from "react";

export interface Column<T> {
  id: string;
  header: string;
  numeric?: boolean;
  cell: (row: T) => ReactNode;
  sortValue?: (row: T) => number | string;
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  rowClass?: (row: T) => string;
  defaultSort?: { id: string; desc: boolean };
  emptyText?: string;
  /** Optional card-art preview shown while hovering a row (pack tables). */
  hoverImage?: (row: T) => string | null;
  /** Optional double-click handler — the legacy Custom Deck moved one copy of
   *  a card between deck and sideboard on <Double-Button-1>. */
  onRowDoubleClick?: (row: T) => void;
}

/** Small hand-rolled sortable table — pack tables are ≤15 rows, no
 *  virtualization needed. */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  rowClass,
  defaultSort,
  emptyText = "No data",
  hoverImage,
  onRowDoubleClick,
}: Props<T>) {
  const [sort, setSort] = useState(defaultSort ?? null);
  const [hoverUrl, setHoverUrl] = useState<string | null>(null);
  const posRef = useRef({ x: 0, y: 0 });

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.id === sort.id);
    if (!col?.sortValue) return rows;
    const sv = col.sortValue;
    return [...rows].sort((a, b) => {
      const va = sv(a);
      const vb = sv(b);
      const cmp =
        typeof va === "number" && typeof vb === "number"
          ? va - vb
          : String(va).localeCompare(String(vb));
      return sort.desc ? -cmp : cmp;
    });
  }, [rows, sort, columns]);

  const toggleSort = (id: string) => {
    setSort((prev) =>
      prev?.id === id ? { id, desc: !prev.desc } : { id, desc: true },
    );
  };

  // Row delegation: moving between rows updates the preview without the
  // leave/enter churn of per-row handlers.
  const handleRowOver = (e: React.MouseEvent<HTMLTableElement>) => {
    posRef.current = { x: e.clientX, y: e.clientY };
    if (!hoverImage) return;
    const tr = (e.target as Element).closest("tr");
    const idx = tr?.getAttribute("data-index");
    const row = idx == null ? undefined : sorted[Number(idx)];
    setHoverUrl(row ? (hoverImage(row) ?? null) : null);
  };

  if (rows.length === 0) {
    return <div className="empty-state">{emptyText}</div>;
  }

  return (
    <div className="table-wrap">
      <table className="data-table" onMouseMove={handleRowOver} onMouseLeave={() => setHoverUrl(null)}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.id}
                className={sort?.id === c.id ? "sorted" : ""}
                onClick={() => c.sortValue && toggleSort(c.id)}
              >
                {c.header}
                {sort?.id === c.id ? (sort.desc ? " ↓" : " ↑") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr
              key={rowKey(row)}
              data-index={i}
              className={rowClass?.(row) ?? ""}
              onDoubleClick={onRowDoubleClick ? () => onRowDoubleClick(row) : undefined}
            >
              {columns.map((c) => (
                <td key={c.id} className={c.numeric ? "num" : ""}>
                  {c.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {hoverUrl && (
        <img
          className="card-hover"
          src={hoverUrl}
          alt=""
          style={{ left: posRef.current.x + 18, top: posRef.current.y - 140 }}
        />
      )}
    </div>
  );
}
