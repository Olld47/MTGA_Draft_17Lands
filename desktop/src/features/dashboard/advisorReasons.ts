import type { Lang } from "../../i18n/locales";

/** Localizes the advisor's reasoning chips (Recommendation.reasoning, emitted
 *  as English by the shared src/advisor engine) for the Chinese UI. The engine
 *  is shared with the English-only tkinter app, so the translation lives here:
 *  each known template matches a regex and maps to a Chinese string, keeping
 *  the interpolated numbers/colors/roles. Unknown templates pass through
 *  untouched (English) rather than ever dropping a reason. */
export function localizeReason(reason: string, lang: Lang): string {
  if (lang !== "zh") return reason;
  for (const [pattern, translate] of REASON_RULES) {
    const match = pattern.exec(reason);
    if (match) return translate(match);
  }
  return reason;
}

// Role words embedded in the VOR templates, translated consistently.
const ROLE_ZH: Record<string, string> = {
  "2-Drops": "2费牌",
  Removal: "解场",
  Evasion: "穿透",
};

type Rule = [RegExp, (m: RegExpExecArray) => string];

// Ordered (specificity doesn't overlap, but the exact-match rules are kept
// before their siblings for readability). Mirrors every reason the engine can
// emit: src/advisor/engine.py evaluate_pack + the castability/composition/
// wheel helpers.
const REASON_RULES: Rule[] = [
  [/^LATE SIGNAL$/, () => "晚信号"],
  [/^Archetype Glue \(\+([\d.]+)\)$/, (m) => `思路胶水（+${m[1]}）`],
  [/^Archetype Synergy \(\+([\d.]+)\)$/, (m) => `思路协同（+${m[1]}）`],
  [
    /^High VOR: Scarce ([WUBRG]) (2-Drops|Removal|Evasion) \(\+(\d+)\)$/,
    (m) => `高替换价值：${m[1]}色${ROLE_ZH[m[2]]}稀缺（+${m[3]}）`,
  ],
  [/^Highly Replaceable (2-Drops|Removal|Evasion)$/, (m) => `${ROLE_ZH[m[1]]}易被替代`],
  [/^Improves Best Deck \(\+([\d.]+)\)$/, (m) => `提升最佳套牌（+${m[1]}）`],
  [/^This is the only available option\.$/, () => "这是唯一可选的牌。"],
  [/^Basic Land \(Skip\)$/, () => "基本地（跳过）"],
  [/^TRUE BOMB \(High IWD\)$/, () => "真炸弹（高 IWD）"],
  [/^Uncastable \(Double Pip\)$/, () => "无法施放（双色费）"],
  [/^Bomb Splash$/, () => "炸弹混色"],
  [/^Premium Removal Splash$/, () => "优质解场混色"],
  [/^Greedy Bomb Splash$/, () => "贪心炸弹混色"],
  [/^Splashable$/, () => "可混色"],
  [/^Off-Color$/, () => "异色"],
  [/^Curve Too Heavy$/, () => "曲线过重"],
  [/^Critical: Needs Creatures$/, () => "关键：需要生物"],
  [/^Artifact Synergy$/, () => "神器协同"],
  [/^Graveyard Synergy$/, () => "坟场协同"],
  [/^Counters Synergy$/, () => "指示物协同"],
  [/^Critical: Needs Fixing$/, () => "关键：需要调色"],
  [/^Enables Bomb Splash$/, () => "支持炸弹混色"],
  [/^Premium Fixing$/, () => "优质调色"],
  [/^Critical: Needs Removal$/, () => "关键：需要解场"],
  [/^Removal Saturated$/, () => "解场过剩"],
  [/^Critical: Needs 2-Drops$/, () => "关键：需要2费牌"],
  [/^Curve Foundation$/, () => "曲线基础"],
  [/^Wheels ~(\d+)%$/, (m) => `轮转 ~${m[1]}%`],
];
