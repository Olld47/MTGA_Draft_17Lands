// The Signal Ledger — five WUBRG lanes, each a dot that goes green when the
// lane is open and red when it is cut. The strongest lane reads "open", the
// weakest "cut" — table slang. A plain dot means no signal either way.

import { useLanguage } from "../../i18n/useLanguage";

const ORDER = ["W", "U", "B", "R", "G"] as const;

interface Props {
  scores: Record<string, number>;
}

export function SignalLedger({ scores }: Props) {
  const { t } = useLanguage();
  const values = ORDER.map((c) => scores[c] ?? 0);
  const maxColor = ORDER[values.indexOf(Math.max(...values))];
  const minColor = ORDER[values.indexOf(Math.min(...values))];
  const anySignal = values.some((v) => v > 0);

  return (
    <div className="signal-ledger">
      {ORDER.map((color) => {
        const word =
          anySignal && color === maxColor
            ? "open"
            : anySignal && color === minColor
              ? "cut"
              : "";
        return (
          <div key={color} className={`signal-lane ${color.toLowerCase()}`}>
            <span className="lane-symbol">{color}</span>
            <span
              className={`lane-dot${word ? ` ${word}` : ""}`}
              aria-label={`${color} ${word}`.trim()}
            />
            <span
              className={`lane-word${word === "open" ? " open" : ""}${word === "cut" ? " cut" : ""}`}
            >
              {word === "open"
                ? t("dash.open")
                : word === "cut"
                  ? t("dash.cut")
                  : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
}
