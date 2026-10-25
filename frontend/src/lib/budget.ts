// Pure, client-side budget recompute for the Compare view.
//
// The backend provides the Monte Carlo line items per tier (p10/p50/p90). The
// user can scale any category with a multiplier (0.5x..2x); we recompute the
// adjusted p50 total client-side so sliders feel instant. This never fabricates
// new figures: it scales the SIMULATED p50 the model produced. The result is
// labelled "customized (client-side)" in the UI so it is never mistaken for a
// fresh model run.

import type { LineItem } from "../types";

export interface CustomBudget {
  total: number; // adjusted p50 total
  base: number; // original p50 total (all multipliers = 1)
  adjusted: { name: string; p50: number; adjusted: number; mult: number }[];
  gap: number | null; // adjusted total - budget target (positive = over)
}

// Group line items into the categories the slider panel exposes.
export function categoryOf(name: string): string {
  if (name.startsWith("Catering")) return "Catering";
  if (name === "Water") return "Water";
  if (name === "Wi-Fi AP rental" || name === "Power stations") return "Tech";
  if (name === "AV tech" || name === "Security" || name === "Custodial") return "Staffing";
  if (name === "Prizes" || name === "Swag") return "Prizes & swag";
  return "Other"; // Insurance, Printing, Contingency
}

export const CATEGORIES = [
  "Catering",
  "Water",
  "Tech",
  "Staffing",
  "Prizes & swag",
  "Other",
] as const;

export type Category = (typeof CATEGORIES)[number];

export function recompute(
  lineItems: LineItem[],
  multipliers: Record<string, number>,
  budgetTarget: number | null
): CustomBudget {
  let base = 0;
  let total = 0;
  const adjusted = lineItems.map((li) => {
    const cat = categoryOf(li.name);
    const mult = multipliers[cat] ?? 1;
    base += li.p50;
    const adj = li.p50 * mult;
    total += adj;
    return { name: li.name, p50: li.p50, adjusted: Math.round(adj), mult };
  });
  return {
    total: Math.round(total),
    base: Math.round(base),
    adjusted,
    gap: budgetTarget != null ? Math.round(total) - budgetTarget : null,
  };
}

// Sum p50 of the catering lines only (used to show the per-tier menu cost).
export function cateringTotal(lineItems: LineItem[]): number {
  return lineItems
    .filter((li) => li.name.startsWith("Catering"))
    .reduce((s, li) => s + li.p50, 0);
}
