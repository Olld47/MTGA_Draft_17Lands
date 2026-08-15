import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { useLanguage } from "../i18n/useLanguage";

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
 *  the caller's useColumnConfig(viewId). With `onMove` the configurable
 *  headings also become draggable, mirroring the legacy header drag-to-reorder
 *  (display_order.insert(target, pop(source))). */
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
  /** Move `from` to just before `to` (both configurable field ids). */
  onMove?: (from: string, to: string) => void;
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  rowClass?: (row: T) => string;
  defaultSort?: { id: string; desc: boolean };
  /** Persisted initial sort (from Settings.tableSortStates) — takes precedence
   *  over defaultSort on mount. Set together with onSortChange to persist. */
  initialSort?: { id: string; desc: boolean } | null;
  /** Called on every sort toggle so the caller can persist the choice. */
  onSortChange?: (sort: { id: string; desc: boolean }) => void;
  emptyText?: string;
  /** Optional hover tooltip rendered beside the cursor over a row — the card
   *  art plus the legacy CardToolTip stat panel. Return null for rows without
   *  a preview (basic lands, cards with no image). */
  hoverContent?: (row: T) => ReactNode | null;
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
  /** Optional group-by (legacy sealed_studio group view): buckets the sorted
   *  rows under header rows, in `order` (empty buckets skipped). The column
   *  sort still applies within each group. */
  groupBy?: {
    key: (row: T) => string;
    order: string[];
    label: (key: string, rows: T[]) => string;
  };
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
  initialSort,
  onSortChange,
  emptyText,
  hoverContent,
  onRowDoubleClick,
  onContextMenu,
  columnMenu,
  showAddColumn = true,
  groupBy,
}: Props<T>) {
  const { t } = useLanguage();
  const [sort, setSort] = useState(initialSort ?? defaultSort ?? null);
  const [hovered, setHovered] = useState<T | null>(null);
  const [menu, setMenu] = useState<MenuState | null>(null);
  const posRef = useRef({ x: 0, y: 0 });
  const hoverElRef = useRef<HTMLDivElement | null>(null);
  // True once the user has picked a sort — the late-arriving persisted sort
  // (Settings loads async) must never clobber it.
  const userSortedRef = useRef(false);

  // The persisted initialSort resolves after mount (Settings is fetched async):
  // adopt it once it arrives. Guarded — only before the user has sorted.
  useEffect(() => {
    if (userSortedRef.current || !initialSort) return;
    setSort((prev) =>
      prev?.id === initialSort.id && prev?.desc === initialSort.desc
        ? prev
        : initialSort,
    );
  }, [initialSort]);

  // Header drag-to-reorder: the column being dragged, and a one-tick flag so
  // the release of a drag doesn't also toggle the sort (dragend → click in
  // WebKit). Cleared via the dragEnd timeout, which runs after the click.
  const dragFrom = useRef<string | null>(null);
  const dragEnded = useRef(false);

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

  // Group-by: bucket the already-sorted rows into canonical order (empty
  // buckets skipped). `dataRows` is the flattened data list so the row-hover
  // delegation can keep indexing by position — group-header rows carry no
  // data-index, so hovering one clears the preview.
  const buckets = useMemo(() => {
    if (!groupBy) return null;
    const map = new Map<string, T[]>();
    for (const row of sorted) {
      const key = groupBy.key(row);
      const list = map.get(key);
      if (list) list.push(row);
      else map.set(key, [row]);
    }
    return groupBy.order
      .map((key) => ({ key, rows: map.get(key) ?? [] }))
      .filter((b) => b.rows.length > 0);
  }, [sorted, groupBy]);
  const dataRows = buckets ? buckets.flatMap((b) => b.rows) : sorted;

  const toggleSort = (id: string) => {
    // Compute from the committed `sort` (the handler is fresh per render) and
    // keep the updater pure — side effects in updaters fire on every
    // invocation, which StrictMode double-invokes in dev.
    const next =
      sort?.id === id ? { id, desc: !sort.desc } : { id, desc: true };
    userSortedRef.current = true;
    setSort(next);
    onSortChange?.(next);
  };

  // Position the card below-right of the cursor, clamped so it stays on-screen
  // (it is much taller than the old image-only preview). Applied imperatively:
  // the position is DOM-only data — re-rendering the table per mousemove would
  // rebuild the hover card on every pixel.
  const positionHover = useCallback(() => {
    const node = hoverElRef.current;
    if (!node) return;
    const { x, y } = posRef.current;
    node.style.left = `${Math.max(8, Math.min(x + 18, window.innerWidth - 436))}px`;
    node.style.top = `${Math.max(8, Math.min(y + 12, window.innerHeight - 300))}px`;
  }, []);

  // Sets the initial position on mount (the entry coordinates are already in
  // posRef when the card first renders); later mousemoves update it directly.
  const attachHover = useCallback(
    (node: HTMLDivElement | null) => {
      hoverElRef.current = node;
      if (node) positionHover();
    },
    [positionHover],
  );

  // Row delegation: moving between rows updates the preview without the
  // leave/enter churn of per-row handlers.
  const handleRowOver = (e: React.MouseEvent<HTMLTableElement>) => {
    posRef.current = { x: e.clientX, y: e.clientY };
    positionHover();
    if (!hoverContent) return;
    const tr = (e.target as Element).closest("tr");
    const idx = tr?.getAttribute("data-index");
    const row = idx == null ? undefined : dataRows[Number(idx)];
    setHovered(row ?? null);
  };

  const hoverNode =
    hovered && hoverContent ? hoverContent(hovered) : null;

  if (rows.length === 0) {
    return <div className="empty-state">{emptyText ?? t("table.noData")}</div>;
  }

  const renderRow = (row: T, index: number) => (
    <tr
      key={rowKey(row)}
      data-index={index}
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
  );

  return (
    <div className="table-wrap">
      <table className="data-table" onMouseMove={handleRowOver} onMouseLeave={() => setHovered(null)}>
        <thead>
          <tr>
            {columns.map((c) => {
              const draggable = Boolean(
                columnMenu?.onMove && columnMenu.active.includes(c.id),
              );
              return (
                <th
                  key={c.id}
                  className={sort?.id === c.id ? "sorted" : ""}
                  draggable={draggable}
                  onClick={() => {
                    if (dragEnded.current) {
                      dragEnded.current = false;
                      return;
                    }
                    if (c.sortValue) toggleSort(c.id);
                  }}
                  onDragStart={
                    draggable
                      ? (e) => {
                          dragFrom.current = c.id;
                          e.dataTransfer.effectAllowed = "move";
                        }
                      : undefined
                  }
                  onDragOver={
                    draggable
                      ? (e) => {
                          if (dragFrom.current && dragFrom.current !== c.id) {
                            e.preventDefault();
                          }
                        }
                      : undefined
                  }
                  onDrop={
                    draggable
                      ? (e) => {
                          e.preventDefault();
                          const from = dragFrom.current;
                          dragFrom.current = null;
                          if (from && from !== c.id) columnMenu?.onMove?.(from, c.id);
                        }
                      : undefined
                  }
                  onDragEnd={
                    draggable
                      ? () => {
                          dragFrom.current = null;
                          dragEnded.current = true;
                          setTimeout(() => {
                            dragEnded.current = false;
                          }, 0);
                        }
                      : undefined
                  }
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
              );
            })}
            {columnMenu && showAddColumn && (
              <th
                className="col-add"
                title={t("table.addColumn")}
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
          {buckets && groupBy
            ? buckets.map((b) => (
                <Fragment key={b.key}>
                  <tr className="group-head">
                    <td colSpan={columns.length + (columnMenu ? 1 : 0)}>
                      {groupBy.label(b.key, b.rows)}
                    </td>
                  </tr>
                  {b.rows.map((row) => renderRow(row, dataRows.indexOf(row)))}
                </Fragment>
              ))
            : sorted.map((row, i) => renderRow(row, i))}
        </tbody>
      </table>
      {hoverNode && (
        <div ref={attachHover} className="card-hover">
          {hoverNode}
        </div>
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
              {t("table.removeColumn", { label: columnMenu.label(menu.field) })}
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
            {t("table.resetToDefaults")}
          </button>
        </div>
      )}
    </div>
  );
}
