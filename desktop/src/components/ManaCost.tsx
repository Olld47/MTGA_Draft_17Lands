const PIP_RE = /\{([^}]+)\}/g;

const COLOR_CLASS: Record<string, string> = {
  W: "w",
  U: "u",
  B: "b",
  R: "r",
  G: "g",
};

/** Renders "{2}{W}{W}" as inline mana pips. */
export function ManaCost({ cost }: { cost: string }) {
  if (!cost) return null;
  const pips = [...cost.matchAll(PIP_RE)].map((m) => m[1]);
  if (pips.length === 0) return null;
  return (
    <span className="mana" aria-label={`Mana cost ${cost}`}>
      {pips.map((pip, i) => (
        <span key={i} className={`pip ${COLOR_CLASS[pip] ?? "c"}`}>
          {COLOR_CLASS[pip] ? "" : pip}
        </span>
      ))}
    </span>
  );
}
