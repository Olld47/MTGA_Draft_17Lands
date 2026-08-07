// Vitest global setup: extends `expect` with the jest-dom matchers
// (toBeInTheDocument, toHaveTextContent, ...) used across the component tests.
import "@testing-library/jest-dom/vitest";

// vitest runs with `globals: false`, so testing-library's auto-cleanup (which
// relies on a global afterEach) never registers itself. Register it explicitly
// or every render leaks its DOM into the next test.
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
afterEach(() => cleanup());
