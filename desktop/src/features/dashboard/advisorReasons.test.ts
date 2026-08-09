import { describe, expect, it } from "vitest";

import { localizeReason } from "./advisorReasons";

describe("localizeReason", () => {
  it("keeps English untouched when the language is English", () => {
    expect(localizeReason("LATE SIGNAL", "en")).toBe("LATE SIGNAL");
    expect(localizeReason("Wheels ~80%", "en")).toBe("Wheels ~80%");
  });

  it("translates every known template to Chinese, preserving interpolation", () => {
    expect(localizeReason("LATE SIGNAL", "zh")).toBe("晚信号");
    expect(localizeReason("Archetype Glue (+3.2)", "zh")).toBe("思路胶水（+3.2）");
    expect(localizeReason("Archetype Synergy (+2.8)", "zh")).toBe("思路协同（+2.8）");
    expect(localizeReason("High VOR: Scarce W 2-Drops (+6)", "zh")).toBe(
      "高替换价值：W色2费牌稀缺（+6）",
    );
    expect(localizeReason("High VOR: Scarce B Removal (+6)", "zh")).toBe(
      "高替换价值：B色解场稀缺（+6）",
    );
    expect(localizeReason("High VOR: Scarce G Evasion (+6)", "zh")).toBe(
      "高替换价值：G色穿透稀缺（+6）",
    );
    expect(localizeReason("Highly Replaceable 2-Drops", "zh")).toBe("2费牌易被替代");
    expect(localizeReason("Highly Replaceable Removal", "zh")).toBe("解场易被替代");
    expect(localizeReason("Highly Replaceable Evasion", "zh")).toBe("穿透易被替代");
    expect(localizeReason("Improves Best Deck (+3.2)", "zh")).toBe("提升最佳套牌（+3.2）");
    expect(localizeReason("This is the only available option.", "zh")).toBe(
      "这是唯一可选的牌。",
    );
    expect(localizeReason("Basic Land (Skip)", "zh")).toBe("基本地（跳过）");
    expect(localizeReason("TRUE BOMB (High IWD)", "zh")).toBe("真炸弹（高 IWD）");
    expect(localizeReason("Uncastable (Double Pip)", "zh")).toBe("无法施放（双色费）");
    expect(localizeReason("Bomb Splash", "zh")).toBe("炸弹混色");
    expect(localizeReason("Premium Removal Splash", "zh")).toBe("优质解场混色");
    expect(localizeReason("Greedy Bomb Splash", "zh")).toBe("贪心炸弹混色");
    expect(localizeReason("Splashable", "zh")).toBe("可混色");
    expect(localizeReason("Off-Color Gold", "zh")).toBe("异色金牌");
    expect(localizeReason("Off-Color", "zh")).toBe("异色");
    expect(localizeReason("Curve Too Heavy", "zh")).toBe("曲线过重");
    expect(localizeReason("Critical: Needs Creatures", "zh")).toBe("关键：需要生物");
    expect(localizeReason("Artifact Synergy", "zh")).toBe("神器协同");
    expect(localizeReason("Graveyard Synergy", "zh")).toBe("坟场协同");
    expect(localizeReason("Counters Synergy", "zh")).toBe("指示物协同");
    expect(localizeReason("Critical: Needs Fixing", "zh")).toBe("关键：需要调色");
    expect(localizeReason("Enables Bomb Splash", "zh")).toBe("支持炸弹混色");
    expect(localizeReason("Premium Fixing", "zh")).toBe("优质调色");
    expect(localizeReason("Critical: Needs Removal", "zh")).toBe("关键：需要解场");
    expect(localizeReason("Removal Saturated", "zh")).toBe("解场过剩");
    expect(localizeReason("Critical: Needs 2-Drops", "zh")).toBe("关键：需要2费牌");
    expect(localizeReason("Curve Foundation", "zh")).toBe("曲线基础");
    expect(localizeReason("Wheels ~80%", "zh")).toBe("轮转 ~80%");
  });

  it("passes unknown templates through untouched", () => {
    expect(localizeReason("Some Future Reason", "zh")).toBe("Some Future Reason");
  });
});
