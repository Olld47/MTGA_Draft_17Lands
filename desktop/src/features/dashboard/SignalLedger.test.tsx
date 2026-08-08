import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { SignalLedger } from "./SignalLedger";

const COLORS = ["W", "U", "B", "R", "G"];

function dot(container: HTMLElement, color: string): HTMLElement {
  const el = container.querySelector(
    `.signal-lane.${color.toLowerCase()} .lane-dot`,
  );
  if (!el) throw new Error(`no lane-dot for ${color}`);
  return el as HTMLElement;
}

describe("SignalLedger", () => {
  it("turns the strongest lane green and the weakest red", () => {
    const { container } = render(
      <SignalLedger scores={{ W: 4, U: 1, B: 2, R: 0, G: 3 }} />,
    );

    // W is the open lane, R is the cut lane.
    expect(dot(container, "W").classList.contains("open")).toBe(true);
    expect(dot(container, "R").classList.contains("cut")).toBe(true);
    // The remaining lanes carry no signal.
    for (const color of ["U", "B", "G"]) {
      expect(dot(container, color).classList.contains("open")).toBe(false);
      expect(dot(container, color).classList.contains("cut")).toBe(false);
    }
  });

  it("renders every lane as a plain dot when no signals exist", () => {
    const { container } = render(
      <SignalLedger scores={{ W: 0, U: 0, B: 0, R: 0, G: 0 }} />,
    );

    for (const color of COLORS) {
      expect(dot(container, color).classList.contains("open")).toBe(false);
      expect(dot(container, color).classList.contains("cut")).toBe(false);
    }
  });

  it("draws one dot per lane instead of a progress track", () => {
    const { container } = render(
      <SignalLedger scores={{ W: 2, U: 1, B: 0, R: 0, G: 0 }} />,
    );

    expect(container.querySelectorAll(".lane-dot")).toHaveLength(5);
    // The old progress bar is gone.
    expect(container.querySelector(".lane-track")).toBeNull();
    expect(container.querySelector(".lane-fill")).toBeNull();
  });
});
