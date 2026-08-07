// Vitest global setup: extends `expect` with the jest-dom matchers
// (toBeInTheDocument, toHaveTextContent, ...) used across the component tests.
import "@testing-library/jest-dom/vitest";

// vitest runs with `globals: false`, so testing-library's auto-cleanup (which
// relies on a global afterEach) never registers itself. Register it explicitly
// or every render leaks its DOM into the next test.
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
afterEach(() => cleanup());

// jsdom 26 ships neither matchMedia nor — once vitest skips copying it under
// Node's experimental web-storage accessor — a reachable localStorage. Install
// both so components that read the theme / language stores can run in tests.
const storage = (() => {
  let data = new Map<string, string>();
  return {
    get length(): number {
      return data.size;
    },
    clear(): void {
      data = new Map();
    },
    getItem(key: string): string | null {
      return data.has(key) ? data.get(key)! : null;
    },
    key(i: number): string | null {
      return [...data.keys()][i] ?? null;
    },
    removeItem(key: string): void {
      data.delete(key);
    },
    setItem(key: string, value: string): void {
      data.set(key, String(value));
    },
  };
})();

Object.defineProperty(window, "localStorage", {
  value: storage,
  writable: true,
  configurable: true,
});

Object.defineProperty(window, "matchMedia", {
  value: (query: string): MediaQueryList => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
  writable: true,
  configurable: true,
});

