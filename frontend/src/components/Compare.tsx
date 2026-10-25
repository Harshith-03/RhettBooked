import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { usePrefersReducedMotion } from "../theme";
import type { PlanOption } from "../types";
import { CATEGORIES, cateringTotal, recompute } from "../lib/budget";
import { CountUp, StatusPill, money } from "./ui";

// Tier accent: Premium gets the full red, Balanced a mid red, Lean a quiet tone.
const TIER_ACCENT: Record<string, string> = {
  lean: "var(--muted)",
  balanced: "var(--red)",
  premium: "var(--red)",
};

const TIER_BLURB: Record<string, string> = {
  lean: "Keep it tight. Cheapest catering and minimal staffing.",
  balanced: "The recommended middle. Mid catering, standard staffing.",
  premium: "Go all in. Top catering and extended staffing.",
};

function gapLine(gap: number): { text: string; status: "ok" | "strained" | "failing" } {
  if (gap <= 0) return { text: `${money(-gap)} under budget`, status: "ok" };
  if (gap <= 3000) return { text: `${money(gap)} over budget`, status: "strained" };
  return { text: `${money(gap)} over budget`, status: "failing" };
}

// A single plan-option column.
function OptionColumn({
  opt,
  featured,
  mult,
  budgetTarget,
  index,
}: {
  opt: PlanOption;
  featured: boolean;
  mult: Record<string, number>;
  budgetTarget: number;
  index: number;
}) {
  const reduced = usePrefersReducedMotion();
  const custom = useMemo(
    () => recompute(opt.line_items, mult, budgetTarget),
    [opt.line_items, mult, budgetTarget]
  );
  const customized = custom.total !== custom.base;
  const catering = cateringTotal(opt.line_items);
  const gap = gapLine(custom.gap ?? 0);
  const accent = TIER_ACCENT[opt.tier] ?? "var(--red)";

  return (
    <motion.div
      initial={{ opacity: 0, y: reduced ? 0 : 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduced ? 0 : 0.3, delay: reduced ? 0 : index * 0.07 }}
      className="relative flex flex-col rounded-2xl"
      style={{
        background: "var(--card)",
        border: featured ? "1.5px solid var(--red)" : "1px solid var(--border)",
        boxShadow: featured ? "var(--shadow-lg)" : "var(--shadow-sm)",
        padding: 24,
      }}
    >
      {featured ? (
        <span
          className="absolute -top-3 left-6 rounded-full px-3 py-1 text-xs font-semibold text-white"
          style={{ background: "var(--red)" }}
        >
          Recommended
        </span>
      ) : null}

      <div className="flex items-baseline justify-between">
        <h3 style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.02em" }}>{opt.name}</h3>
        <span className="caps-label" style={{ color: accent }}>{opt.tier}</span>
      </div>
      <p className="mt-1 text-sm" style={{ color: "var(--muted)", minHeight: 40 }}>
        {TIER_BLURB[opt.tier] ?? opt.tradeoffs}
      </p>

      {/* Headline cost */}
      <div className="mt-4">
        <p className="display-number" style={{ color: "var(--text)" }}>
          <span style={{ fontSize: "0.6em", verticalAlign: "0.1em" }}>$</span>
          <CountUp value={custom.total} />
        </p>
        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
          {customized ? (
            <>customized · base {money(custom.base)}</>
          ) : (
            <>p50 · {money(opt.total_p10)}–{money(opt.total_p90)}</>
          )}
        </p>
      </div>

      {/* Budget fit */}
      <div className="mt-3 flex items-center gap-2">
        <StatusPill status={gap.status} />
        <span className="text-sm tnum" style={{ color: "var(--text)" }}>{gap.text}</span>
      </div>

      <div className="mt-4 h-px w-full" style={{ background: "var(--border)" }} />

      {/* Key figures */}
      <dl className="mt-4 space-y-2 text-sm">
        <Row label="Per attendee" value={money(opt.cost_per_attendee)} />
        <Row label="Catering (menu)" value={money(catering)} />
        <Row label="Sponsorship gap" value={money(opt.sponsorship_gap)} />
      </dl>

      {/* Line-item breakdown (zebra) */}
      <div className="mt-5">
        <p className="caps-label mb-2">Where it goes</p>
        <div className="overflow-hidden rounded-lg" style={{ border: "1px solid var(--border)" }}>
          {custom.adjusted.map((li, i) => (
            <div
              key={li.name}
              className="flex items-center justify-between px-3 py-1.5 text-sm"
              style={{ background: i % 2 ? "var(--card-alt)" : "var(--card)" }}
            >
              <span style={{ color: "var(--muted)" }} className="truncate pr-2">
                {li.name}
                {li.mult !== 1 ? (
                  <span style={{ color: "var(--red-text)" }}> ·{li.mult}×</span>
                ) : null}
              </span>
              <span className="tnum">{money(li.adjusted)}</span>
            </div>
          ))}
        </div>
      </div>

      <p className="mt-4 text-xs" style={{ color: "var(--muted)" }}>
        SIMULATED · Monte Carlo over turnout × placeholder rate cards. Sliders scale the
        p50 client-side.
      </p>
    </motion.div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <dt style={{ color: "var(--muted)" }}>{label}</dt>
      <dd className="tnum font-medium">{value}</dd>
    </div>
  );
}

// The slider panel: per-category multipliers + an overall budget target.
function CustomizePanel({
  mult,
  setMult,
  budgetTarget,
  setBudgetTarget,
  defaultBudget,
}: {
  mult: Record<string, number>;
  setMult: (m: Record<string, number>) => void;
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
      style={{ background: "var(--card)", border: "1px solid var(--border)", boxShadow: "var(--shadow-sm)", padding: 24 }}
    >
      <div className="flex items-center justify-between">
        <div>
          <h3 style={{ fontSize: 17, fontWeight: 700 }}>Customize</h3>
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            Tune each category and your budget target. All three plans update live.
          </p>
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
      <div className="mt-5">
        <div className="flex items-center justify-between">
          <label htmlFor="budget-target" className="caps-label">Budget target</label>
          <span className="tnum text-sm font-semibold">{money(budgetTarget)}</span>
        </div>
        <input
          id="budget-target"
          type="range"
          className="rb-range mt-2"
          min={5000}
          max={60000}
          step={500}
          value={budgetTarget}
          onChange={(e) => setBudgetTarget(Number(e.target.value))}
        />
      </div>

      {/* Category multipliers */}
      <div className="mt-5 grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
        {CATEGORIES.map((cat) => {
          const v = mult[cat] ?? 1;
          return (
            <div key={cat}>
              <div className="flex items-center justify-between">
                <label htmlFor={`m-${cat}`} className="caps-label">{cat}</label>
                <span
                  className="tnum text-sm"
                  style={{ color: v === 1 ? "var(--muted)" : "var(--red-text)", fontWeight: 600 }}
                >
                  {v.toFixed(2)}×
                </span>
              </div>
              <input
                id={`m-${cat}`}
                type="range"
                className="rb-range mt-2"
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

export function Compare({ options }: { options: PlanOption[] }) {
  const defaultBudget = options[0]?.budget_usd ?? 15000;
  const [budgetTarget, setBudgetTarget] = useState(defaultBudget);
  const [mult, setMult] = useState<Record<string, number>>(
    Object.fromEntries(CATEGORIES.map((c) => [c, 1]))
  );

  if (!options?.length) return null;

  return (
    <section className="space-y-5">
      <div>
        <h2 className="hero-title" style={{ fontSize: 28 }}>Three ways to run it</h2>
        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
          Lean, Balanced and Premium — same venue and schedule, different catering and staffing.
        </p>
      </div>

      <CustomizePanel
        mult={mult}
        setMult={setMult}
        budgetTarget={budgetTarget}
        setBudgetTarget={setBudgetTarget}
        defaultBudget={defaultBudget}
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {options.map((opt, i) => (
          <OptionColumn
            key={opt.tier}
            opt={opt}
            featured={opt.tier === "balanced"}
            mult={mult}
            budgetTarget={budgetTarget}
            index={i}
          />
        ))}
      </div>
    </section>
  );
}
