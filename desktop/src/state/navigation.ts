// Tiny module-level tab-navigation bus. The context menu's "Compare" action
// needs to switch to the Compare tab from inside a table deep in the tree
// (PackTable, TakenPage, ...) without threading a setTab callback through every
// intermediate component. App subscribes once; navigateTab() fans out.

type NavListener = (tab: string) => void;

const listeners = new Set<NavListener>();

export function onNavigateTab(fn: NavListener): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export function navigateTab(tab: string): void {
  listeners.forEach((fn) => fn(tab));
}
