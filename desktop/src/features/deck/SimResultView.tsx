import type { SimResult } from "../../api/types";

const pct = (v: number) => `${v.toFixed(1)}%`;

/** Monte-Carlo simulation results + advisor heuristics. Shared shape between
 *  the custom-deck and (future) sealed simulate actions. */
export function SimResultView({ result }: { result: SimResult }) {
  if (!result.ok || !result.stats) {
    return (
      <section className="panel">
        <h2>Simulation</h2>
        <div className="empty-inline">{result.message || "No result."}</div>
      </section>
    );
  }
  const s = result.stats;
  const rows: [string, string][] = [
    ["Mulligans", pct(s.mulligans)],
    ["Cast on curve T2", pct(s.castT2)],
    ["Cast on curve T3", pct(s.castT3)],
    ["Screw by T3", pct(s.screwT3)],
    ["Color screw T3", pct(s.colorScrewT3)],
    ["Flood by T5", pct(s.floodT5)],
    ["Removal by T4", pct(s.removalT4)],
  ];
  return (
    <section className="panel">
      <h2>Simulation</h2>
      {result.optimizationNote && (
        <div className="sim-note">{result.optimizationNote}</div>
      )}
      <table className="sim-table">
        <tbody>
          {rows.map(([label, val]) => (
            <tr key={label}>
              <td>{label}</td>
              <td className="num">{val}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {result.advice.length > 0 && (
        <ul className="sim-advice">
          {result.advice.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
