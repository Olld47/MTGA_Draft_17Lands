import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Unit-test config, separate from vite.config.ts whose async defineConfig is
// tailored to the Tauri dev/build server. jsdom + the react plugin are all the
// components need; test files live next to their modules under src/.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    // A real origin (not the default about:blank) so jsdom enables its
    // localStorage implementation for the language store's persistence.
    environmentOptions: { jsdom: { url: "http://localhost:3000" } },
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
