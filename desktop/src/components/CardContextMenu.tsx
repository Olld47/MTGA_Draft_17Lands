import { useCallback, useEffect, useState } from "react";

import { compareAddCard, openUrl } from "../api/client";
import { navigateTab } from "../state/navigation";

/** Scryfall search URL for a card name — legacy card_interactions.open_scryfall. */
export function scryfallUrl(name: string): string {
  return `https://scryfall.com/search?q=${encodeURIComponent(name)}`;
}

export interface CardMenuState {
  name: string;
  x: number;
  y: number;
}

/** Opens the legacy card context menu (Compare / Copy name / Scryfall) on the
 *  active card. Call open(name, x, y) from a DataTable onContextMenu handler
 *  and render {element} at the end of the page. */
export function useCardMenu() {
  const [menu, setMenu] = useState<CardMenuState | null>(null);

  const open = useCallback((name: string, x: number, y: number) => {
    setMenu({ name, x, y });
  }, []);
  const close = useCallback(() => setMenu(null), []);

  // Close on outside click, Escape, or window blur — the menu is a floating
  // fixed-position element, so a backdrop-free dismiss is enough.
  useEffect(() => {
    if (!menu) return;
    const onDown = (e: MouseEvent) => {
      if (!(e.target as Element).closest(".context-menu")) setMenu(null);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenu(null);
    };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    window.addEventListener("blur", close);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("blur", close);
    };
  }, [menu, close]);

  return {
    open,
    close,
    element: menu ? <CardContextMenu menu={menu} onClose={close} /> : null,
  };
}

function CardContextMenu({
  menu,
  onClose,
}: {
  menu: CardMenuState;
  onClose: () => void;
}) {
  const { name } = menu;

  const compare = () => {
    compareAddCard(name).catch(console.warn);
    navigateTab("compare");
    onClose();
  };
  const copy = () => {
    navigator.clipboard?.writeText(name).catch(() => {});
    onClose();
  };
  const scryfall = () => {
    openUrl(scryfallUrl(name)).catch(console.warn);
    onClose();
  };

  return (
    <div
      className="context-menu"
      style={{ left: menu.x + 4, top: menu.y - 8 }}
      onClick={(e) => e.stopPropagation()}
      role="menu"
    >
      <button role="menuitem" onClick={compare}>
        🔍 Compare “{name}”
      </button>
      <button role="menuitem" onClick={copy}>
        📋 Copy Name
      </button>
      <hr />
      <button role="menuitem" onClick={scryfall}>
        🌐 View on Scryfall
      </button>
    </div>
  );
}
