import { useEffect, useRef, useState } from "react";
import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import { fetchOptions, fetchPlan } from "./api";
import { BRIEF_TEXT } from "./demo";
import { Compare } from "./components/Compare";
import { CustomizeCard, type Multipliers } from "./components/Customize";
import { DrillPanel } from "./components/DrillPanel";
import { Sections } from "./components/Sections";
import { SummaryCard, TwoUp } from "./components/cards";
import { BudgetCard, FoodWaterCard } from "./components/budgetfood";
import { Chip, PrimaryButton, Reveal, Skeleton } from "./components/ui";
import { CATEGORIES } from "./lib/budget";
import { applyTheme, getInitialTheme, setTheme, usePrefersReducedMotion, type Theme } from "./theme";
import type { BriefKey, OptionsResponse, Plan, Source } from "./types";

export default function App() {
  const [theme, setThemeState] = useState<Theme>("light");
  const [text, setText] = useState("");
  const [briefKey, setBriefKey] = useState<BriefKey | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [options, setOptions] = useState<OptionsResponse | null>(null);
  const [source, setSource] = useState<Source>("live");
  const [loading, setLoading] = useState(false);
  const [researched, setResearched] = useState<{ low: number; high: number; n: number } | null>(null);

  // Lifted customization state so the right-rail Customize card drives Compare.
  const [mult, setMult] = useState<Multipliers>(
    Object.fromEntries(CATEGORIES.map((c) => [c, 1]))
  );
  const [budgetTarget, setBudgetTarget] = useState<number>(15000);

  useEffect(() => {
    const t = getInitialTheme();
    setThemeState(t);
    applyTheme(t);
  }, []);

  // When the first plan arrives, seed the budget target from the brief.
  useEffect(() => {
    const b = options?.options?.[0]?.budget_usd;
    if (b) setBudgetTarget(b);
  }, [options]);

  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setThemeState(next);
    setTheme(next);
  }

  async function runPlan(inputText: string, key: BriefKey | null) {
    if (!inputText.trim()) return;
    setLoading(true);
    setResearched(null);
    const [planRes, optRes] = await Promise.all([
      fetchPlan(inputText, key),
      fetchOptions(inputText, key),
    ]);
    setPlan(planRes.data);
    setOptions(optRes.data);
    setSource(planRes.source === "demo" || optRes.source === "demo" ? "demo" : "live");
    setLoading(false);
  }

  function useExample(key: BriefKey) {
    const t = BRIEF_TEXT[key];
    setText(t);
    setBriefKey(key);
    void runPlan(t, key);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void runPlan(text, briefKey);
    }
  }

  function newPlan() {
    setPlan(null);
    setOptions(null);
    setText("");
    setBriefKey(null);
    setMult(Object.fromEntries(CATEGORIES.map((c) => [c, 1])));
  }

  const built = Boolean(plan);

  return (
    <div style={{ minHeight: "100%", background: "var(--bg)", color: "var(--text)" }}>
      <AmbientBackground />
      <Header theme={theme} onToggle={toggleTheme} source={source} onNewPlan={newPlan} built={built} />

      <LayoutGroup>
        {!built ? (
          // ---------- Centered hero state ----------
          <main className="relative mx-auto w-full px-5 sm:px-8" style={{ maxWidth: 760, paddingTop: 72, paddingBottom: 64 }}>
            <Hero />
            <motion.div layoutId="intake-card" layout>
              <IntakeCard
                text={text}
                setText={(t) => { setText(t); setBriefKey(null); }}
                onKeyDown={onKeyDown}
                onBuild={() => void runPlan(text, briefKey)}
                loading={loading}
                briefKey={briefKey}
                onExample={useExample}
                compact={false}
              />
            </motion.div>
          </main>
        ) : (
          // ---------- VS Code-style docked shell: scrolling main pane + fixed side panel ----------
          <main className="relative flex w-full flex-col lg:h-[calc(100vh-60px)] lg:flex-row">
            {/* Main pane: fills all width left of the panel, scrolls on its own */}
            <section className="min-w-0 flex-1 lg:overflow-y-auto" style={{ scrollbarGutter: "stable" }}>
              <div className="mx-auto w-full px-6 sm:px-10" style={{ maxWidth: 1180, paddingTop: 28, paddingBottom: 80 }}>
                {loading ? (
                  <LoadingSkeleton />
                ) : plan ? (
                  <div className="space-y-6">
                    {options?.options?.length ? (
                      <Reveal>
                        <Compare options={options.options} mult={mult} budgetTarget={budgetTarget} />
                      </Reveal>
                    ) : null}
                    <Reveal delay={0.05}><Divider label="The recommended plan in detail" /></Reveal>
                    <Reveal delay={0.05}><SummaryCard plan={plan} /></Reveal>
                    <Reveal delay={0.08}><TwoUp plan={plan} /></Reveal>
                    <Reveal delay={0.08}><BudgetCard plan={plan} researched={researched} /></Reveal>
                    <Reveal delay={0.08}>
                      <FoodWaterCard plan={plan} text={text} briefKey={briefKey} onSource={setSource} onResearchedPrices={setResearched} />
                    </Reveal>
                    <Reveal delay={0.08}>
                      <Sections text={text} briefKey={briefKey} plan={plan} onSource={setSource} />
                    </Reveal>
                    <Reveal delay={0.08}><DrillPanel text={text} briefKey={briefKey} onSource={setSource} /></Reveal>
                  </div>
                ) : null}
              </div>
            </section>

            {/* Docked side panel (VS Code secondary sidebar): own surface + hard divider */}
            <motion.aside
              layout
              initial={{ x: 40, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
              className="hidden shrink-0 flex-col lg:flex"
              style={{
                width: 380,
                background: "var(--panel)",
                borderLeft: "1px solid var(--border)",
                boxShadow: "var(--panel-shadow)",
              }}
            >
              {/* Panel header strip */}
              <div
                className="flex items-center justify-between px-4"
                style={{ height: 40, borderBottom: "1px solid var(--border)", flex: "0 0 auto" }}
              >
                <span className="caps-label" style={{ letterSpacing: "0.1em" }}>Plan controls</span>
              </div>

              {/* Scrollable panel body */}
              <div className="flex-1 overflow-y-auto p-4" style={{ scrollbarGutter: "stable" }}>
                <div className="space-y-4">
                  {options?.options?.length ? (
                    <CustomizeCard
                      mult={mult}
                      setMult={setMult}
                      budgetTarget={budgetTarget}
                      setBudgetTarget={setBudgetTarget}
                      defaultBudget={options.options[0]?.budget_usd ?? 15000}
                    />
                  ) : null}
                  <motion.div layoutId="intake-card" layout>
                    <IntakeCard
                      text={text}
                      setText={(t) => { setText(t); setBriefKey(null); }}
                      onKeyDown={onKeyDown}
                      onBuild={() => void runPlan(text, briefKey)}
                      loading={loading}
                      briefKey={briefKey}
                      onExample={useExample}
                      compact
                    />
                  </motion.div>
                </div>
              </div>
            </motion.aside>

            {/* Mobile: panel collapses below as a normal stack (no divider) */}
            <aside className="block w-full lg:hidden">
              <div className="mx-auto w-full px-6 pb-16" style={{ maxWidth: 1180 }}>
                <div className="space-y-4">
                  {options?.options?.length ? (
                    <CustomizeCard
                      mult={mult}
                      setMult={setMult}
                      budgetTarget={budgetTarget}
                      setBudgetTarget={setBudgetTarget}
                      defaultBudget={options.options[0]?.budget_usd ?? 15000}
                    />
                  ) : null}
                </div>
              </div>
            </aside>
          </main>
        )}
      </LayoutGroup>
    </div>
  );
}

// Soft BU-red radial glow behind the hero, fading as you scroll. Pure CSS.
function AmbientBackground() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0"
      style={{
        zIndex: 0,
        background:
          "radial-gradient(900px 420px at 50% -120px, var(--ring), transparent 70%)",
        opacity: 0.9,
      }}
    />
  );
}

function Hero() {
  const reduced = usePrefersReducedMotion();
  return (
    <motion.div
      initial={{ opacity: 0, y: reduced ? 0 : 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduced ? 0 : 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="relative mb-7 text-center"
    >
      <span
        className="mb-4 inline-block rounded-full px-3 py-1 text-xs font-medium"
        style={{ background: "var(--red-soft)", color: "var(--red-text)", border: "1px solid var(--border)" }}
      >
        BU event planning, modelled end to end
      </span>
      <h1 className="hero-title mx-auto" style={{ maxWidth: 680 }}>
        Describe your event.
        <br />
        <span style={{ color: "var(--red-text)" }}>Get a plan that holds up.</span>
      </h1>
      <p className="mx-auto mt-4 text-base sm:text-lg" style={{ maxWidth: 520, color: "var(--muted)" }}>
        One sentence in, a complete plan out — venue, budget, food, transit and a stress-test.
        Three budgets, side by side.
      </p>
    </motion.div>
  );
}

function IntakeCard({
  text, setText, onKeyDown, onBuild, loading, briefKey, onExample, compact,
}: {
  text: string;
  setText: (t: string) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onBuild: () => void;
  loading: boolean;
  briefKey: BriefKey | null;
  onExample: (k: BriefKey) => void;
  compact: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  return (
    <div
      className="rounded-2xl"
      style={{
        background: "var(--card)",
        border: "1px solid var(--border)",
        boxShadow: compact ? "var(--shadow-sm)" : "var(--shadow-lg)",
        padding: compact ? 16 : 24,
      }}
    >
      <div className="flex items-center justify-between">
        <label htmlFor="brief" className="caps-label">
          {compact ? "Your brief" : "Describe your event"}
        </label>
        {compact ? (
          <span className="text-xs" style={{ color: "var(--muted)" }}>edit &amp; rebuild ↻</span>
        ) : null}
      </div>
      <textarea
        id="brief"
        ref={ref}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        rows={compact ? 4 : 3}
        placeholder="e.g. 300-person overnight AI hackathon at BU, Oct 24-25, students, budget $15k, needs lunch, dinner, midnight snack, breakfast"
        className="mt-2 w-full rounded-xl p-3 text-sm"
        style={{ border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", resize: "vertical" }}
      />
      <div className={`mt-3 flex flex-wrap items-center gap-2 ${compact ? "" : "sm:mt-4"}`}>
        <PrimaryButton onClick={onBuild} disabled={loading || !text.trim()}>
          {loading ? "Planning…" : compact ? "Rebuild" : "Build plan"}
        </PrimaryButton>
        {!compact ? <span className="text-xs" style={{ color: "var(--muted)" }}>or try</span> : null}
        <Chip label={compact ? "A" : "Brief A · Oct 24-25"} active={briefKey === "briefA"} onClick={() => onExample("briefA")} />
        <Chip label={compact ? "B" : "Brief B · Oct 31-Nov 1"} active={briefKey === "briefB"} onClick={() => onExample("briefB")} />
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        <Skeleton height={300} />
        <Skeleton height={300} />
        <Skeleton height={300} />
      </div>
      <Skeleton height={120} />
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <Skeleton height={180} />
        <Skeleton height={180} />
      </div>
    </div>
  );
}

function Divider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-4 pt-1">
      <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.02em" }}>{label}</span>
      <span className="h-px flex-1" style={{ background: "var(--border)" }} />
    </div>
  );
}

function Header({
  theme, onToggle, source, onNewPlan, built,
}: {
  theme: Theme;
  onToggle: () => void;
  source: Source;
  onNewPlan: () => void;
  built: boolean;
}) {
  return (
    <header
      className="rb-header"
      style={{ background: "var(--header-bg)", borderBottom: "3px solid var(--header-border)" }}
    >
      <div className="flex w-full items-center justify-between px-5 py-3 sm:px-8">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center overflow-hidden rounded-full" style={{ width: 36, height: 36, background: "#ffffff" }}>
            <img src="/logo.png" alt="RhettBooked logo" width={36} height={36} style={{ width: 36, height: 36, objectFit: "contain" }} />
          </div>
          <div>
            <div style={{ color: "#ffffff", fontWeight: 700, fontSize: 18, lineHeight: 1 }}>RhettBooked</div>
            <div style={{ color: "#ffffff", opacity: 0.85, fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase" }}>
              BU Event Planner
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <AnimatePresence>
            {source === "demo" ? (
              <motion.span
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="rounded-full px-2 py-0.5"
                style={{ background: "#9ca3af", color: "#ffffff", fontSize: 11, fontWeight: 600 }}
              >
                Demo snapshot
              </motion.span>
            ) : null}
          </AnimatePresence>
          <button
            onClick={onToggle}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            title="Toggle theme"
            style={{ color: "#ffffff", fontSize: 18, lineHeight: 1 }}
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
          {built ? (
            <button
              onClick={onNewPlan}
              className="rounded-full px-3 py-1 text-sm font-medium"
              style={{ border: "1px solid #ffffff", color: "#ffffff" }}
            >
              New plan
            </button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
