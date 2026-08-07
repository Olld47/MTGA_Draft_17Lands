import { useCallback, useEffect, useState } from "react";

// Mini Mode — the compact, always-on-top overlay that sits over the Arena
// client during a live draft (the pytauri port of `CompactOverlay`). Toggling
// it shrinks the OS window, strips its chrome, and pins it above other windows;
// restoring returns the window to its full size. Every Tauri call is guarded so
// the same components render harmlessly in a plain browser (vite preview,
// Storybook) where `@tauri-apps/api` has no backend.
//
// Geometry persists through Settings.overlayGeometry ("WxH+X+Y" in logical px,
// the legacy `CompactOverlay._save_geometry` format): entering mini restores
// the saved size+position, moving/resizing while mini live-saves it (debounced
// via the window's onMoved/onResized events), and exiting captures it once more
// BEFORE the window enlarges back to full size — so the next mini session
// returns to exactly where you left it. Window transparency itself is a CSS
// `opacity` on the overlay over the transparent OS window configured in
// tauri.conf.json (Tauri v2 has no setOpacity API).

const FULL_SIZE = { width: 1180, height: 860 };
const DEFAULT_MINI_GEOMETRY = "380x600+50+50";
/** Debounce for live geometry saves while dragging/resizing in mini mode. */
const SAVE_DEBOUNCE_MS = 400;

interface MiniGeometry {
  width: number;
  height: number;
  x: number;
  y: number;
}

function parseGeometry(geometry?: string): MiniGeometry {
  const m = /^(\d+)x(\d+)([+-]\d+)([+-]\d+)$/.exec(geometry ?? "");
  if (!m) {
    const [w, h, x, y] = DEFAULT_MINI_GEOMETRY.match(/\d+/g)!.map(Number);
    return { width: w, height: h, x, y };
  }
  return {
    width: +m[1],
    height: +m[2],
    x: +m[3],
    y: +m[4],
  };
}

function formatGeometry(g: MiniGeometry): string {
  return `${g.width}x${g.height}+${g.x}+${g.y}`;
}

async function applyWindow(mini: boolean, geometry?: string): Promise<void> {
  try {
    const [{ getCurrentWindow }, { PhysicalPosition, PhysicalSize }] =
      await Promise.all([
        import("@tauri-apps/api/window"),
        import("@tauri-apps/api/dpi"),
      ]);
    const win = getCurrentWindow();
    await win.setDecorations(!mini);
    await win.setAlwaysOnTop(mini);
    const sf = await win.scaleFactor();
    if (mini) {
      // Shrink to the saved mini geometry (size first, then position — the
      // top-left corner is the stable anchor between the two calls).
      const { width, height, x, y } = parseGeometry(geometry);
      await win.setSize(new PhysicalSize(Math.round(width * sf), Math.round(height * sf)));
      await win.setPosition(new PhysicalPosition(Math.round(x * sf), Math.round(y * sf)));
    } else {
      await win.setSize(
        new PhysicalSize(Math.round(FULL_SIZE.width * sf), Math.round(FULL_SIZE.height * sf)),
      );
    }
  } catch {
    // Not running inside Tauri (or the permission is unavailable) — the
    // in-app layout still switches; only the OS-level window tweaks are skipped.
  }
}

export function useMiniMode(
  overlayGeometry?: string,
  saveOverlayGeometry?: (geometry: string) => void,
) {
  const [mini, setMini] = useState(false);

  /** Read the current window geometry and persist it as "WxH+X+Y". */
  const saveGeometry = useCallback(async () => {
    if (!saveOverlayGeometry) return;
    try {
      const { getCurrentWindow } = await import("@tauri-apps/api/window");
      const win = getCurrentWindow();
      const sf = await win.scaleFactor();
      const [pos, size] = await Promise.all([win.outerPosition(), win.outerSize()]);
      saveOverlayGeometry(
        formatGeometry({
          width: Math.round(size.width / sf),
          height: Math.round(size.height / sf),
          x: Math.round(pos.x / sf),
          y: Math.round(pos.y / sf),
        }),
      );
    } catch {
      // no-op outside Tauri
    }
  }, [saveOverlayGeometry]);

  const toggle = useCallback(() => {
    setMini((prev) => {
      const next = !prev;
      if (prev) {
        // Leaving mini: capture the geometry BEFORE the window enlarges, so a
        // mid-drag position survives into the next mini session.
        void (async () => {
          await saveGeometry();
          await applyWindow(false);
        })();
      } else {
        void applyWindow(true, overlayGeometry);
      }
      return next;
    });
  }, [overlayGeometry, saveGeometry]);

  // While mini, live-save geometry (debounced) on move/resize so dragging the
  // overlay around during a draft persists even without toggling out. The
  // unlisten runs before the enlarge-on-exit setSize resolves, so that resize
  // event can never overwrite the captured mini geometry with the full size.
  useEffect(() => {
    if (!mini) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let unlisten: Array<() => void> = [];

    const schedule = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => void saveGeometry(), SAVE_DEBOUNCE_MS);
    };

    void (async () => {
      try {
        const { getCurrentWindow } = await import("@tauri-apps/api/window");
        const win = getCurrentWindow();
        const listeners = await Promise.all([
          win.onMoved(schedule),
          win.onResized(schedule),
        ]);
        if (cancelled) {
          listeners.forEach((u) => u());
          return;
        }
        unlisten = listeners;
      } catch {
        // no-op outside Tauri
      }
    })();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      unlisten.forEach((u) => u());
    };
  }, [mini, saveGeometry]);

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

  /** Grow the overlay to a logical size (bottom-right anchored resize grip). */
  const resizeOverlay = useCallback(async (width: number, height: number) => {
    try {
      const [{ getCurrentWindow }, { PhysicalSize }] = await Promise.all([
        import("@tauri-apps/api/window"),
        import("@tauri-apps/api/dpi"),
      ]);
      const win = getCurrentWindow();
      const sf = await win.scaleFactor();
      await win.setSize(
        new PhysicalSize(Math.round(width * sf), Math.round(height * sf)),
      );
    } catch {
      // no-op outside Tauri
    }
  }, []);

  return { mini, toggle, startDragging, resizeOverlay };
}
