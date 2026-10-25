import { useState } from "react";
import type { BriefKey, Plan, Source, Tile } from "../types";
import { SectionCard, money } from "./ui";
import { CatererResearch } from "./Research";

// Cosmetic "basis" labels per budget line item (numbers all come from the model).
const BASIS: Record<string, string> = {
  "Catering - breakfast": "Breakfast per attendee",
  "Catering - lunch": "Lunch per attendee",
  "Catering - dinner": "Dinner per attendee",
  "Catering - snack": "Midnight snack per attendee",
  Water: "~3 bottles per head",
  "Wi-Fi AP rental": "Access points for the event",
  "Power stations": "Charging stations",
  "AV tech": "AV staffing hours",
  Security: "Security staffing hours",
  Custodial: "Custodial hours",
  Insurance: "Event insurance (flat)",
  Prizes: "Prize pool",
  Printing: "Signage & printing",
  Swag: "Swag per attendee",
  Contingency: "Buffer for the unexpected",
};

function basisFor(name: string): string {
  return BASIS[name] ?? "from the budget model";
}

// Budget link: offer researched prices when >=3 verified caterers carry ranges.
function ResearchedPricesToggle({
  researched,
  plan,
}: {
  researched: { low: number; high: number; n: number } | null;
  plan: Plan;
}) {
  const [on, setOn] = useState(false); // off by default
  if (!researched) return null;
  const food = plan.tiles.find((t) => t.name === "Food & Water");
  const head = ((food?.details as any)?.meals?.[0]?.headcount as number) ?? 0;
  const mid = (researched.low + researched.high) / 2;
  const recalculated = Math.round(mid * head);
  return (
    <div className="mb-3 rounded-lg p-2 text-sm" style={{ border: "1px solid var(--border)" }}>
      <label className="flex items-center gap-2">
        <input type="checkbox" checked={on} onChange={(e) => setOn(e.target.checked)} />
        <span>
          Use researched prices{" "}
          <span className="rounded-full px-2 py-0.5 text-xs font-semibold"
                style={{ background: "var(--red-soft)", color: "var(--red-text)" }}>
            RESEARCHED
          </span>
        </span>
      </label>
      {on ? (
        <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
          Catering recalculated from the median researched range {money(researched.low)}-{money(researched.high)}/head
          ({researched.n} verified) → ~{money(recalculated)} per meal for {head}.
        </p>
      ) : (
        <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
          {researched.n} verified caterers have prices. Off by default.
        </p>
      )}
    </div>
  );
}

export function BudgetCard({
  plan,
  researched,
}: {
  plan: Plan;
  researched?: { low: number; high: number; n: number } | null;
}) {
  const b = plan.budget;
  // The row-by-row total is the SUM of the line-item p50s so the table always
  // adds up exactly (p50-of-a-sum differs from the sum-of-p50s by rounding, so
  // we show the self-consistent row sum as the headline total).
  const rowTotal = budgetLineSum(plan);
  // Keep the model's gap relationship: gap = total - budget. Recompute against
  // the row total so "over/under" matches the number shown.
  const budgetUsd = b.total_p50 - b.sponsorship_gap;
  const over = rowTotal - budgetUsd;
  return (
    <SectionCard>
      <h3 className="mb-3 font-semibold" style={{ fontSize: 17 }}>Budget, row by row</h3>
      <ResearchedPricesToggle researched={researched ?? null} plan={plan} />
      {/* Horizontal scroll on small screens. */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[480px] text-left text-sm">
          <thead>
            <tr className="caps-label" style={{ borderBottom: "2px solid var(--red)" }}>
              <th className="pb-1">Item</th>
              <th className="pb-1">Basis</th>
              <th className="pb-1 text-right">Cost (p50)</th>
            </tr>
          </thead>
          <tbody>
            {b.line_items.map((li, i) => (
              <tr
                key={li.name}
                style={{ background: i % 2 ? "var(--card-alt)" : "transparent" }}
              >
                <td className="py-1.5 font-medium">{li.name}</td>
                <td className="py-1.5 text-xs" style={{ color: "var(--muted)" }}>{basisFor(li.name)}</td>
                <td className="py-1.5 text-right" style={{ fontVariantNumeric: "tabular-nums" }}>{money(li.p50)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Final total bar. */}
      <div
        className="mt-3 flex flex-col gap-2 rounded-lg p-4 sm:flex-row sm:items-center sm:justify-between"
        style={{ background: "var(--final-bar)", color: "#ffffff" }}
      >
        <div>
          <p style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", opacity: 0.85 }}>
            Final cost (likely, p50)
          </p>
          <p style={{ fontSize: 30, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
            {money(rowTotal)}
          </p>
        </div>
        <div className="text-sm sm:text-right">
          <p>Range {money(b.total_p10)} - {money(b.total_p90)} (p10-p90)</p>
          <p>{money(b.cost_per_attendee)} per attendee</p>
          {budgetUsd ? (
            <p>
              Budget {over > 0 ? "over" : "under"} by {money(Math.abs(over))}
            </p>
          ) : <p>On budget</p>}
        </div>
      </div>
      <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
        Rows come from the budget model and always add up to the final total.
      </p>
    </SectionCard>
  );
}

// --- Food & water (real data) + "Find real caterers" research.
export function FoodWaterCard({
  plan,
  text,
  briefKey,
  onSource,
  onResearchedPrices,
}: {
  plan: Plan;
  text: string;
  briefKey: BriefKey | null;
  onSource: (s: Source) => void;
  onResearchedPrices: (r: { low: number; high: number; n: number } | null) => void;
}) {
  const tile = plan.tiles.find((t) => t.name === "Food & Water") as Tile | undefined;
  const meals = (tile?.details?.meals as any[]) ?? [];
  const water = tile?.details?.water as any;
  return (
    <SectionCard>
      <h3 className="mb-3 font-semibold" style={{ fontSize: 17 }}>Food &amp; water</h3>
      <div className="space-y-3">
        {meals.map((m, i) => (
          <div key={i} className="rounded-lg p-2" style={{ border: "1px solid var(--border)" }}>
            <div className="flex items-center justify-between">
              <span className="font-medium capitalize">{m.meal}</span>
              <span className="text-xs" style={{ color: "var(--muted)" }}>
                {m.window} · {m.serving_lines} line{m.serving_lines === 1 ? "" : "s"}
              </span>
            </div>
            <p className="text-sm">
              Est. {money(m.cost_low)} - {money(m.cost_high)} for {m.headcount}
            </p>
            {m.open_halls?.length ? (
              <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                Open: {m.open_halls.map((h: any) => h.name).join(", ")}
              </p>
            ) : null}
            {m.check_hours_halls?.length ? (
              <p className="mt-1 text-xs" style={{ color: "var(--warn-text)" }}>
                Check hours: {m.check_hours_halls.map((h: any) => h.name).join(", ")}
              </p>
            ) : null}
            {m.note ? <p className="mt-1 text-xs italic" style={{ color: "var(--muted)" }}>{m.note}</p> : null}
          </div>
        ))}
        {water ? (
          <div className="rounded-lg p-2 text-sm" style={{ border: "1px solid var(--border)" }}>
            <p className="font-medium">Water</p>
            <p>
              ~{water.total_litres.toLocaleString()} L · bottled {money(water.bottled_cost[0])}-{money(water.bottled_cost[1])}, refill {money(water.refill_cost[0])}-{money(water.refill_cost[1])}
            </p>
            <p className="text-xs" style={{ color: "var(--muted)" }}>{water.recommendation}</p>
          </div>
        ) : null}
      </div>
      <CatererResearch
        text={text}
        briefKey={briefKey}
        onSource={onSource}
        onResearchedPrices={onResearchedPrices}
      />
    </SectionCard>
  );
}

// Exported for the sum-invariant test.
export function budgetLineSum(plan: Plan): number {
  return plan.budget.line_items.reduce((acc, li) => acc + li.p50, 0);
}
