import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

export interface Column<T> {
  id: string;
  header: string;
  numeric?: boolean;
  cell: (row: T) => ReactNode;
  sortValue?: (row: T) => number | string;
}

/** Optional column add/remove/persist wiring (the legacy per-table column
 *  config menus). When provided, the header row gains a trailing "+" cell and
 *  a right-click heading menu with Remove / Add / Reset — both persist through
 *  the caller's useColumnConfig(viewId). */
export interface ColumnMenu {
  /** Currently visible configurable fields, in display order. */
  active: string[];
  /** Fields that can be added, with display labels (already excludes active). */
  addable: { id: string; label: string }[];
  /** True if the field may be removed (base columns like name/cost cannot). */
  removable: (id: string) => boolean;
  /** Display label for a field, used by the "Remove" entry. */
  label: (id: string) => string;
  onAdd: (id: string) => void;
  onRemove: (id: string) => void;
  onReset: () => void;
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
  /** Optional right-click handler (legacy <Button-3> card context menu).
   *  Receives viewport coords for positioning a floating menu. */
  onContextMenu?: (row: T, x: number, y: number) => void;
  /** Column add/remove/persist wiring; see ColumnMenu. */
  columnMenu?: ColumnMenu;
  /** Hide the trailing "+" add-cell (ComparePage has its own last column). */
  showAddColumn?: boolean;
}

interface MenuState {
  x: number;
  y: number;
  field?: string;
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
  onContextMenu,
  columnMenu,
  showAddColumn = true,
}: Props<T>) {
  const [sort, setSort] = useState(defaultSort ?? null);
  const [hoverUrl, setHoverUrl] = useState<string | null>(null);
  const [menu, setMenu] = useState<MenuState | null>(null);
  const posRef = useRef({ x: 0, y: 0 });

  // Floating column menu: dismiss on outside-click, Escape, or window blur —
  // same dismiss contract as the card context menu.
  useEffect(() => {
    if (!menu) return;
    const onDown = (e: MouseEvent) => {
      if (!(e.target as Element).closest(".context-menu")) setMenu(null);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenu(null);
    };
    const onBlur = () => setMenu(null);
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    window.addEventListener("blur", onBlur);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("blur", onBlur);
    };
  }, [menu]);

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
                onContextMenu={
                  columnMenu
                    ? (e) => {
                        e.preventDefault();
                        setMenu({ x: e.clientX, y: e.clientY, field: c.id });
                      }
                    : undefined
                }
              >
                {c.header}
                {sort?.id === c.id ? (sort.desc ? " ↓" : " ↑") : ""}
              </th>
            ))}
            {columnMenu && showAddColumn && (
              <th
                className="col-add"
                title="Add column"
                onClick={(e) => {
                  const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
                  setMenu({ x: r.right - 8, y: r.bottom + 2 });
                }}
              >
                +
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr
              key={rowKey(row)}
              data-index={i}
              className={rowClass?.(row) ?? ""}
              onDoubleClick={onRowDoubleClick ? () => onRowDoubleClick(row) : undefined}
              onContextMenu={
                onContextMenu
                  ? (e) => {
                      e.preventDefault();
                      onContextMenu(row, e.clientX, e.clientY);
                    }
                  : undefined
              }
            >
              {columns.map((c) => (
                <td key={c.id} className={c.numeric ? "num" : ""}>
                  {c.cell(row)}
                </td>
              ))}
              {columnMenu && showAddColumn && <td />}
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
      {columnMenu && menu && (
        <div
          className="context-menu"
          style={{ left: menu.x + 4, top: menu.y - 8 }}
          onClick={(e) => e.stopPropagation()}
          role="menu"
        >
          {menu.field && columnMenu.removable(menu.field) && (
            <button
              role="menuitem"
              onClick={() => {
                columnMenu.onRemove(menu.field!);
                setMenu(null);
              }}
            >
              Remove “{columnMenu.label(menu.field)}”
            </button>
          )}
          {columnMenu.addable.length > 0 && (
            <>
              {menu.field && columnMenu.removable(menu.field) && <hr />}
              {columnMenu.addable.map((a) => (
                <button
                  key={a.id}
                  role="menuitem"
                  onClick={() => {
                    columnMenu.onAdd(a.id);
                    setMenu(null);
                  }}
                >
                  + {a.label}
                </button>
              ))}
            </>
          )}
          <hr />
          <button role="menuitem" onClick={() => { columnMenu.onReset(); setMenu(null); }}>
            Reset to Defaults
          </button>
        </div>
      )}
    </div>
  );
}
