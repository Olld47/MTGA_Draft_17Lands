import { useMemo, useState, type ReactNode } from "react";

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
}: Props<T>) {
  const [sort, setSort] = useState(defaultSort ?? null);

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

  if (rows.length === 0) {
    return <div className="empty-state">{emptyText}</div>;
  }

  return (
    <table className="data-table">
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
        {sorted.map((row) => (
          <tr key={rowKey(row)} className={rowClass?.(row) ?? ""}>
            {columns.map((c) => (
              <td key={c.id} className={c.numeric ? "num" : ""}>
                {c.cell(row)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
