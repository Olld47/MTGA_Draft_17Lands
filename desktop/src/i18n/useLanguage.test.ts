import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { setLanguage, t, useLanguage } from "./useLanguage";

// The language store is module-level and mirrors its choice into localStorage
// + document.lang, so each test restores the English default and clears the
// mirror to keep cases independent.
afterEach(() => {
  setLanguage("en");
  localStorage.removeItem("mtga.lang");
});

describe("t", () => {
  it("returns the English string by default", () => {
    expect(t("tab.draft")).toBe("Draft");
  });

  it("falls back to the key itself for unknown keys", () => {
    expect(t("no.such.key")).toBe("no.such.key");
  });

  it("switches to Chinese and back via setLanguage", () => {
    setLanguage("zh");
    expect(t("tab.draft")).toBe("轮抓");
    setLanguage("en");
    expect(t("tab.draft")).toBe("Draft");
  });

  it("interpolates {name} placeholders in both locales", () => {
    setLanguage("en");
    expect(t("dash.curveIdealTarget", { i: 2, target: 5 })).toBe(
      "CMC 2: ideal 5",
    );
    setLanguage("zh");
    expect(t("dash.curveIdealTarget", { i: 2, target: 5 })).toBe(
      "费用 2：理想 5",
    );
  });
});

describe("useLanguage", () => {
  it("mirrors the language onto document.lang and localStorage", () => {
    setLanguage("zh");
    expect(document.documentElement.lang).toBe("zh");
    expect(localStorage.getItem("mtga.lang")).toBe("zh");
  });

  it("re-renders subscribers when the language changes", () => {
    const { result } = renderHook(() => useLanguage());
    expect(result.current.lang).toBe("en");

    act(() => setLanguage("zh"));
    expect(result.current.lang).toBe("zh");
    expect(result.current.t("tab.draft")).toBe("轮抓");

    act(() => setLanguage("en"));
    expect(result.current.lang).toBe("en");
  });
});
