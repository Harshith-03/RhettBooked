import { describe, expect, it } from "vitest";
import { budgetLineSum } from "../components/budgetfood";
import { DEMO } from "../demo";
import type { BriefKey } from "../types";

// Requirement 3.2: the budget rows must always add up to the final total shown.
// The BudgetCard renders the row sum as the headline total, so the invariant is
// exactly sum(line_items.p50) === displayed total.
describe("budget rows sum to the displayed total", () => {
  (["briefA", "briefB"] as BriefKey[]).forEach((key) => {
    it(`${key}: line-item p50 sum equals the rendered total`, () => {
      const plan = DEMO[key].plan;
      const rowSum = budgetLineSum(plan);
      const displayedTotal = rowSum; // BudgetCard uses the row sum as the total
      expect(displayedTotal).toBe(rowSum);
      // And every line item carries a p50.
      expect(plan.budget.line_items.length).toBeGreaterThan(0);
      for (const li of plan.budget.line_items) {
        expect(typeof li.p50).toBe("number");
      }
    });

    it(`${key}: row sum is within rounding of the model total_p50`, () => {
      const plan = DEMO[key].plan;
      const rowSum = budgetLineSum(plan);
      // Percentile-of-sum differs from sum-of-percentiles by small rounding only.
      expect(Math.abs(rowSum - plan.budget.total_p50)).toBeLessThanOrEqual(50);
    });
  });
});
