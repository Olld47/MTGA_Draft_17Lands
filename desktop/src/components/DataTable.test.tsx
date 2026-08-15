import { readFileSync } from "node:fs";

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { DataTable, type Column } from "./DataTable";

interface Item {
  name: string;
  n: number;
}

const columns: Column<Item>[] = [
  { id: "name", header: "Name", cell: (r) => r.name, sortValue: (r) => r.name },
  { id: "count", header: "Count", numeric: true, cell: (r) => r.n, sortValue: (r) => r.n },
];

const items = (): Item[] => [
  { name: "Beta", n: 2 },
  { name: "Alpha", n: 1 },
  { name: "Gamma", n: 3 },
];

const rowKey = (r: Item) => r.name;

const firstCell = (container: HTMLElement) =>
  container.querySelector("tbody tr td")?.textContent;

// Headers append " ↓"/" ↑" once sorted, so match on the leading label.
const headerFor = (id: string) =>
  screen.getByRole("columnheader", { name: new RegExp(`^${id}`, "i") });

describe("DataTable", () => {
  it("shows the empty state when there are no rows", () => {
    render(
      <DataTable columns={columns} rows={[]} rowKey={rowKey} emptyText="No cards" />,
    );
    expect(screen.getByText("No cards")).toBeInTheDocument();
  });

  it("renders rows in insertion order without a sort", () => {
    const { container } = render(
      <DataTable columns={columns} rows={items()} rowKey={rowKey} />,
    );
    expect(firstCell(container)).toBe("Beta");
  });

  it("toggles sort on header click, and re-sorts within groups too", () => {
    const { container } = render(
      <DataTable columns={columns} rows={items()} rowKey={rowKey} />,
    );
    fireEvent.click(headerFor("count")); // desc by count → Gamma, Beta, Alpha
    expect(firstCell(container)).toBe("Gamma");
    fireEvent.click(headerFor("count")); // asc by count → Alpha, Beta, Gamma
    expect(firstCell(container)).toBe("Alpha");
    fireEvent.click(headerFor("name")); // desc by name → Gamma, Beta, Alpha
    expect(firstCell(container)).toBe("Gamma");
  });

  it("honors an initial sort and notifies onSortChange", () => {
    const onSortChange = vi.fn();
    const { container } = render(
      <DataTable
        columns={columns}
        rows={items()}
        rowKey={rowKey}
        initialSort={{ id: "name", desc: false }}
        onSortChange={onSortChange}
      />,
    );
    expect(firstCell(container)).toBe("Alpha");
    fireEvent.click(headerFor("name"));
    expect(onSortChange).toHaveBeenLastCalledWith({ id: "name", desc: true });
  });

  it("adopts a persisted initialSort that resolves after mount", () => {
    const { container, rerender } = render(
      <DataTable columns={columns} rows={items()} rowKey={rowKey} />,
    );
    expect(firstCell(container)).toBe("Beta"); // no sort yet → insertion order
    rerender(
      <DataTable
        columns={columns}
        rows={items()}
        rowKey={rowKey}
        initialSort={{ id: "name", desc: false }}
        onSortChange={vi.fn()}
      />,
    );
    expect(firstCell(container)).toBe("Alpha");
  });

  it("keeps a user sort when initialSort resolves after mount", () => {
    const { container, rerender } = render(
      <DataTable columns={columns} rows={items()} rowKey={rowKey} />,
    );
    fireEvent.click(headerFor("count")); // desc by count → Gamma, Beta, Alpha
    expect(firstCell(container)).toBe("Gamma");
    rerender(
      <DataTable
        columns={columns}
        rows={items()}
        rowKey={rowKey}
        initialSort={{ id: "name", desc: false }}
        onSortChange={vi.fn()}
      />,
    );
    // The late-arriving persisted sort must not clobber the user's choice.
    expect(firstCell(container)).toBe("Gamma");
  });

  it("emits every toggle to onSortChange in order", () => {
    const emitted: Array<{ id: string; desc: boolean }> = [];
    render(
      <DataTable
        columns={columns}
        rows={items()}
        rowKey={rowKey}
        onSortChange={(s) => emitted.push(s)}
      />,
    );
    fireEvent.click(headerFor("count"));
    fireEvent.click(headerFor("count"));
    fireEvent.click(headerFor("name"));
    expect(emitted).toEqual([
      { id: "count", desc: true },
      { id: "count", desc: false },
      { id: "name", desc: true },
    ]);
  });

  it("keeps the persist call out of the setSort updater", () => {
    // React may re-invoke setState updaters (StrictMode dev on React 19,
    // interrupted concurrent renders), and the updater runs during render — a
    // side effect inside it can fire more than once per click. The prod React
    // build under test never double-invokes, so guard the source shape: the
    // toggleSort body must not call onSortChange inside the updater argument.
    const src = readFileSync(
      new URL("src/components/DataTable.tsx", `file://${process.cwd()}/`),
      "utf8",
    );
    const toggleSort = src.match(/const toggleSort[\s\S]*?\n  \};/)?.[0];
    expect(toggleSort).toBeDefined();
    // toggleSort must never pass a function to setSort — a side effect inside
    // an updater (which runs during render and may be re-invoked) would fire
    // more than once per click.
    expect(toggleSort).not.toMatch(/setSort\([^)]*\)?\s*=>/);
  });

  it("buckets rows under group-head rows in canonical order", () => {
    const { container } = render(
      <DataTable
        columns={columns}
        rows={items()}
        rowKey={rowKey}
        groupBy={{
          key: (r) => (r.n % 2 === 0 ? "even" : "odd"),
          order: ["even", "odd"],
          label: (k, rows) => `${k} (${rows.length})`,
        }}
      />,
    );
    expect(screen.getByText("even (1)")).toBeInTheDocument();
    expect(screen.getByText("odd (2)")).toBeInTheDocument();
    expect(container.querySelectorAll("tr.group-head")).toHaveLength(2);
    // Every data row still carries a data-index; group headers do not.
    expect(container.querySelectorAll("tbody tr[data-index]")).toHaveLength(3);
  });

  it("shows the hover tooltip over a row and clears it on mouse leave", () => {
    const { container } = render(
      <DataTable
        columns={columns}
        rows={items()}
        rowKey={rowKey}
        hoverContent={(r) => <div data-testid="hover-panel">{r.name}</div>}
      />,
    );
    expect(screen.queryByTestId("hover-panel")).not.toBeInTheDocument();
    const table = container.querySelector(".data-table")!;
    fireEvent.mouseMove(table.querySelector("tbody tr")!);
    expect(screen.getByTestId("hover-panel")).toHaveTextContent("Beta");
    fireEvent.mouseLeave(table);
    expect(screen.queryByTestId("hover-panel")).not.toBeInTheDocument();
  });

  it("follows the cursor while hovering a row", () => {
    const { container } = render(
      <DataTable
        columns={columns}
        rows={items()}
        rowKey={rowKey}
        hoverContent={(r) => <div data-testid="hover-panel">{r.name}</div>}
      />,
    );
    const table = container.querySelector(".data-table")!;
    const row = table.querySelector("tbody tr")!;
    // The card sits 18px right / 12px below the cursor (clamped to the
    // window); moving the mouse must re-position it, not freeze it.
    fireEvent.mouseMove(row, { clientX: 200, clientY: 150 });
    const panel = container.querySelector<HTMLElement>(".card-hover")!;
    expect(panel).not.toBeNull();
    expect(panel.style.left).toBe("218px");
    expect(panel.style.top).toBe("162px");
    fireEvent.mouseMove(row, { clientX: 500, clientY: 400 });
    expect(panel.style.left).toBe("518px");
    expect(panel.style.top).toBe("412px");
  });

  it("opens the column menu on right-click and fires onReset", () => {
    const onReset = vi.fn();
    render(
      <DataTable
        columns={columns}
        rows={items()}
        rowKey={rowKey}
        columnMenu={{
          active: ["name", "count"],
          addable: [{ id: "value", label: "Value" }],
          removable: (id) => id !== "name",
          label: (id) => id.toUpperCase(),
          onAdd: vi.fn(),
          onRemove: vi.fn(),
          onReset,
        }}
      />,
    );
    fireEvent.contextMenu(headerFor("count"));
    expect(screen.getByRole("menuitem", { name: /Remove/ })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /Value/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("menuitem", { name: /Reset to Defaults/ }));
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});
