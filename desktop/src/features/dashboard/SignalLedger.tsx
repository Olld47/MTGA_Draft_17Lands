// The Signal Ledger — five WUBRG lanes filling like a mana pool over the
// draft. The strongest lane reads "open", the weakest "cut" — table slang.

const ORDER = ["W", "U", "B", "R", "G"] as const;

interface Props {
  scores: Record<string, number>;
}

export function SignalLedger({ scores }: Props) {
  const values = ORDER.map((c) => scores[c] ?? 0);
  const max = Math.max(...values, 0.001);
  const maxColor = ORDER[values.indexOf(Math.max(...values))];
  const minColor = ORDER[values.indexOf(Math.min(...values))];
  const anySignal = values.some((v) => v > 0);

  return (
    <div className="signal-ledger">
      {ORDER.map((color) => {
        const value = scores[color] ?? 0;
        const pct = Math.max(2, (value / max) * 100);
        const word =
          anySignal && color === maxColor
            ? "open"
            : anySignal && color === minColor
              ? "cut"
              : "";
        return (
          <div key={color} className={`signal-lane ${color.toLowerCase()}`}>
            <span className="lane-symbol">{color}</span>
            <span className="lane-track">
              <span
                className="lane-fill"
                style={{ width: anySignal ? `${pct}%` : "0%" }}
              />
            </span>
            <span className={`lane-word${word === "open" ? " open" : ""}`}>
              {word}
            </span>
          </div>
        );
      })}
    </div>
  );
}
