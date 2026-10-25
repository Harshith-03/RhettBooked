import { CATEGORIES } from "../lib/budget";
import { money } from "./ui";

export type Multipliers = Record<string, number>;

// The right-rail Customize card: per-category multipliers + a budget target.
// State is owned by App and shared with the Compare columns so every slider
// move updates all three plans live (client-side recompute).
export function CustomizeCard({
  mult,
  setMult,
  budgetTarget,
  setBudgetTarget,
  defaultBudget,
}: {
  mult: Multipliers;
  setMult: (m: Multipliers) => void;
  budgetTarget: number;
  setBudgetTarget: (n: number) => void;
  defaultBudget: number;
}) {
  const touched =
    budgetTarget !== defaultBudget ||
    CATEGORIES.some((c) => (mult[c] ?? 1) !== 1);

  function reset() {
    setMult(Object.fromEntries(CATEGORIES.map((c) => [c, 1])));
    setBudgetTarget(defaultBudget);
  }

  return (
    <div
      className="rounded-2xl"
      style={{ background: "var(--card)", border: "1px solid var(--border)", boxShadow: "var(--shadow-md)", padding: 18 }}
    >
      <div className="flex items-center justify-between">
        <div>
          <h3 style={{ fontSize: 16, fontWeight: 700, letterSpacing: "-0.01em" }}>Customize</h3>
          <p className="text-xs" style={{ color: "var(--muted)" }}>All three plans update live.</p>
        </div>
        {touched ? (
          <button
            onClick={reset}
            className="rounded-full px-3 py-1 text-xs font-medium"
            style={{ border: "1px solid var(--border)", color: "var(--text)" }}
          >
            Reset
          </button>
        ) : null}
      </div>

      {/* Budget target */}
      <div className="mt-4">
        <div className="flex items-center justify-between">
          <label htmlFor="budget-target" className="caps-label">Budget target</label>
          <span className="tnum text-sm font-semibold">{money(budgetTarget)}</span>
        </div>
        <input
          id="budget-target"
          type="range"
          className="rb-range mt-2"
          min={2000}
          max={30000}
          step={250}
          value={budgetTarget}
          onChange={(e) => setBudgetTarget(Number(e.target.value))}
        />
      </div>

      {/* Category multipliers */}
      <div className="mt-4 space-y-3">
        {CATEGORIES.map((cat) => {
          const v = mult[cat] ?? 1;
          return (
            <div key={cat}>
              <div className="flex items-center justify-between">
                <label htmlFor={`m-${cat}`} className="caps-label">{cat}</label>
                <span
                  className="tnum text-xs"
                  style={{ color: v === 1 ? "var(--muted)" : "var(--red-text)", fontWeight: 600 }}
                >
                  {v.toFixed(2)}×
                </span>
              </div>
              <input
                id={`m-${cat}`}
                type="range"
                className="rb-range mt-1.5"
                min={0.5}
                max={2}
                step={0.05}
                value={v}
                onChange={(e) => setMult({ ...mult, [cat]: Number(e.target.value) })}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
