import { describe, expect, it } from "vitest";
import { DEMO } from "../demo";
import {
  CATEGORIES,
  categoryOf,
  cateringTotal,
  recompute,
} from "../lib/budget";
import type { BriefKey, LineItem } from "../types";

const UNIT: Record<string, number> = Object.fromEntries(
  CATEGORIES.map((c) => [c, 1])
);

describe("Compare: options snapshot shape", () => {
  (["briefA", "briefB"] as BriefKey[]).forEach((key) => {
    it(`${key}: three tiers each with enriched line items`, () => {
      const options = (DEMO[key] as any).options.options as any[];
      expect(options.map((o) => o.name)).toEqual(["Lean", "Balanced", "Premium"]);
      for (const o of options) {
        expect(Array.isArray(o.line_items)).toBe(true);
        expect(o.line_items.length).toBeGreaterThan(0);
        for (const li of o.line_items) {
          expect(typeof li.p50).toBe("number");
        }
      }
    });

    it(`${key}: tiers are genuinely different (lean < balanced < premium catering)`, () => {
      const options = (DEMO[key] as any).options.options as any[];
      const [lean, balanced, premium] = options;
      expect(cateringTotal(lean.line_items)).toBeLessThan(cateringTotal(balanced.line_items));
      expect(cateringTotal(balanced.line_items)).toBeLessThan(cateringTotal(premium.line_items));
    });
  });
});

describe("Compare: client-side recompute", () => {
  const items: LineItem[] = [
    { name: "Catering - lunch", p10: 80, p50: 100, p90: 130 },
    { name: "Water", p10: 8, p50: 10, p90: 13 },
    { name: "AV tech", p10: 40, p50: 50, p90: 60 },
    { name: "Contingency", p10: 8, p50: 10, p90: 12 },
  ];

  it("with all multipliers = 1, total equals the base p50 sum", () => {
    const r = recompute(items, UNIT, null);
    expect(r.base).toBe(170);
    expect(r.total).toBe(170);
    expect(r.gap).toBeNull();
  });

  it("scaling a category changes only that category's contribution", () => {
    const r = recompute(items, { ...UNIT, Catering: 2 }, null);
    // Catering 100 -> 200, others unchanged: 200 + 10 + 50 + 10 = 270
    expect(r.total).toBe(270);
    expect(r.base).toBe(170);
  });

  it("computes the gap against a budget target", () => {
    const r = recompute(items, UNIT, 150);
    expect(r.gap).toBe(20); // 170 - 150, over budget
    const under = recompute(items, UNIT, 300);
    expect(under.gap).toBe(-130); // under budget
  });

  it("the sum of adjusted line items equals the reported total", () => {
    const r = recompute(items, { ...UNIT, Staffing: 1.5, Catering: 0.5 }, null);
    const sum = r.adjusted.reduce((s, li) => s + li.adjusted, 0);
    expect(sum).toBe(r.total);
  });
});

describe("Compare: category mapping", () => {
  it("maps line-item names to the expected categories", () => {
    expect(categoryOf("Catering - dinner")).toBe("Catering");
    expect(categoryOf("Water")).toBe("Water");
    expect(categoryOf("Wi-Fi AP rental")).toBe("Tech");
    expect(categoryOf("Power stations")).toBe("Tech");
    expect(categoryOf("AV tech")).toBe("Staffing");
    expect(categoryOf("Security")).toBe("Staffing");
    expect(categoryOf("Prizes")).toBe("Prizes & swag");
    expect(categoryOf("Insurance")).toBe("Other");
    expect(categoryOf("Contingency")).toBe("Other");
  });
});
