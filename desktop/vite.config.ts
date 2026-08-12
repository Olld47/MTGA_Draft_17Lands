import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { rewriteUiScaleBounds } from "./src/state/uiScaleClamp";

// index.html's pre-paint script must run before the bundle loads, so it can't
// import the clamp module; rewrite its bound literals from
// state/uiScaleClamp.ts at every dev/build instead.
// tests/test_desktop_bundle_config.py pins the source to the same values, so
// this rewrite is normally a no-op — it only matters when the two drift.
function inlineUiScaleClamp(): Plugin {
  return {
    name: "inline-ui-scale-clamp",
    transformIndexHtml(html) {
      return rewriteUiScaleBounds(html);
    },
  };
}

// https://vitejs.dev/config/
export default defineConfig(async () => ({
  plugins: [react(), inlineUiScaleClamp()],

  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent vite from obscuring rust errors
  clearScreen: false,
  // 2. tauri expects a fixed port, fail if that port is not available
  server: {
    port: 1420,
    strictPort: true,
    watch: {
      // 3. tell vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**", "**/.venv/**"],
    },
  },
}));
