import { useCallback, useState } from "react";

// Mini Mode — the compact, always-on-top overlay that sits over the Arena
// client during a live draft (the pytauri port of `CompactOverlay`). Toggling
// it shrinks the OS window, strips its chrome, and pins it above other windows;
// restoring returns the window to its full size. Every Tauri call is guarded so
// the same components render harmlessly in a plain browser (vite preview,
// Storybook) where `@tauri-apps/api` has no backend.

const FULL_SIZE = { width: 1180, height: 860 };
const MINI_SIZE = { width: 380, height: 600 };

async function applyWindow(mini: boolean): Promise<void> {
  try {
    const [{ getCurrentWindow }, { LogicalSize }] = await Promise.all([
      import("@tauri-apps/api/window"),
      import("@tauri-apps/api/dpi"),
    ]);
    const win = getCurrentWindow();
    const size = mini ? MINI_SIZE : FULL_SIZE;
    await win.setDecorations(!mini);
    await win.setAlwaysOnTop(mini);
    await win.setSize(new LogicalSize(size.width, size.height));
  } catch {
    // Not running inside Tauri (or the permission is unavailable) — the
    // in-app layout still switches; only the OS-level window tweaks are skipped.
  }
}

export function useMiniMode() {
  const [mini, setMini] = useState(false);

  const toggle = useCallback(() => {
    setMini((prev) => {
      const next = !prev;
      void applyWindow(next);
      return next;
    });
  }, []);

  const startDragging = useCallback(() => {
    void (async () => {
      try {
        const { getCurrentWindow } = await import("@tauri-apps/api/window");
        await getCurrentWindow().startDragging();
      } catch {
        // no-op outside Tauri
      }
    })();
  }, []);

  return { mini, toggle, startDragging };
}
