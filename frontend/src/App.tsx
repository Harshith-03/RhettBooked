import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { fetchOptions, fetchPlan } from "./api";
import { BRIEF_TEXT } from "./demo";
import { Compare } from "./components/Compare";
import { DrillPanel } from "./components/DrillPanel";
import { Sections } from "./components/Sections";
import { SummaryCard, TwoUp } from "./components/cards";
import { BudgetCard, FoodWaterCard } from "./components/budgetfood";
import {
  Chip,
  PrimaryButton,
  Skeleton,
  Stagger,
  StaggerItem,
} from "./components/ui";
import { applyTheme, getInitialTheme, setTheme, usePrefersReducedMotion, type Theme } from "./theme";
import type { BriefKey, OptionsResponse, Plan, Source } from "./types";

// Content is centered with generous side padding but stretches wide so the
// 3-up Compare grid can breathe (Apple-style full-bleed with a max rail).
const MAX_W = 1200;

export default function App() {
  const [theme, setThemeState] = useState<Theme>("light");
  const [text, setText] = useState("");
  const [briefKey, setBriefKey] = useState<BriefKey | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [options, setOptions] = useState<OptionsResponse | null>(null);
  const [source, setSource] = useState<Source>("live");
  const [loading, setLoading] = useState(false);
  const [researched, setResearched] = useState<{ low: number; high: number; n: number } | null>(null);

  useEffect(() => {
    const t = getInitialTheme();
    setThemeState(t);
    applyTheme(t);
  }, []);

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
  }

  return (
    <div style={{ minHeight: "100%", background: "var(--bg)", color: "var(--text)" }}>
      <Header theme={theme} onToggle={toggleTheme} source={source} onNewPlan={newPlan} />

      <main className="mx-auto w-full px-5 sm:px-8" style={{ maxWidth: MAX_W, paddingTop: 32, paddingBottom: 64 }}>
        {!plan ? <Hero /> : null}

        {/* Intake */}
        <IntakeCard
          text={text}
          setText={(t) => { setText(t); setBriefKey(null); }}
          onKeyDown={onKeyDown}
          onBuild={() => void runPlan(text, briefKey)}
          loading={loading}
          briefKey={briefKey}
          onExample={useExample}
        />

        <div style={{ height: 24 }} />

        {loading && !plan ? (
          <LoadingSkeleton />
        ) : plan ? (
          <Stagger key={`${briefKey}-${source}`}>
            {options?.options?.length ? (
              <StaggerItem><Compare options={options.options} /></StaggerItem>
            ) : null}
            <StaggerItem><Divider label="The recommended plan in detail" /></StaggerItem>
            <StaggerItem><SummaryCard plan={plan} /></StaggerItem>
            <StaggerItem><TwoUp plan={plan} /></StaggerItem>
            <StaggerItem><BudgetCard plan={plan} researched={researched} /></StaggerItem>
            <StaggerItem>
              <FoodWaterCard
                plan={plan}
                text={text}
                briefKey={briefKey}
                onSource={setSource}
                onResearchedPrices={setResearched}
              />
            </StaggerItem>
            <StaggerItem>
              <Sections text={text} briefKey={briefKey} plan={plan} onSource={setSource} />
            </StaggerItem>
            <StaggerItem><DrillPanel text={text} briefKey={briefKey} onSource={setSource} /></StaggerItem>
          </Stagger>
        ) : null}
      </main>
    </div>
  );
}

function Hero() {
  const reduced = usePrefersReducedMotion();
  return (
    <motion.div
      initial={{ opacity: 0, y: reduced ? 0 : 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduced ? 0 : 0.4 }}
      className="mb-8 text-center"
    >
      <h1 className="hero-title mx-auto" style={{ maxWidth: 820 }}>
        Describe your event.
        <br />
        <span style={{ color: "var(--red-text)" }}>Get a plan that holds up.</span>
      </h1>
      <p className="mx-auto mt-4 text-base sm:text-lg" style={{ maxWidth: 560, color: "var(--muted)" }}>
        One sentence in, a complete BU event plan out — venue, budget, food, transit and a
        stress-test. Three budgets, side by side.
      </p>
    </motion.div>
  );
}

function IntakeCard({
  text,
  setText,
  onKeyDown,
  onBuild,
  loading,
  briefKey,
  onExample,
}: {
  text: string;
  setText: (t: string) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onBuild: () => void;
  loading: boolean;
  briefKey: BriefKey | null;
  onExample: (k: BriefKey) => void;
}) {
  return (
    <div
      className="rounded-2xl"
      style={{ background: "var(--card)", border: "1px solid var(--border)", boxShadow: "var(--shadow-md)", padding: 24 }}
    >
      <label htmlFor="brief" className="caps-label">Describe your event</label>
      <textarea
        id="brief"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        rows={3}
        placeholder="e.g. 300-person overnight AI hackathon at BU, Oct 24-25, students, budget $15k, needs lunch, dinner, midnight snack, breakfast"
        className="mt-2 w-full rounded-xl p-4 text-base"
        style={{ border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", resize: "vertical" }}
      />
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <PrimaryButton onClick={onBuild} disabled={loading || !text.trim()}>
          {loading ? "Planning…" : "Build plan"}
        </PrimaryButton>
        <span className="text-xs" style={{ color: "var(--muted)" }}>or try</span>
        <Chip label="Brief A · Oct 24-25" active={briefKey === "briefA"} onClick={() => onExample("briefA")} />
        <Chip label="Brief B · Oct 31-Nov 1" active={briefKey === "briefB"} onClick={() => onExample("briefB")} />
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Skeleton height={320} />
        <Skeleton height={320} />
        <Skeleton height={320} />
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
    <div className="flex items-center gap-4 pt-2">
      <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.02em" }}>{label}</span>
      <span className="h-px flex-1" style={{ background: "var(--border)" }} />
    </div>
  );
}

function Header({
  theme,
  onToggle,
  source,
  onNewPlan,
}: {
  theme: Theme;
  onToggle: () => void;
  source: Source;
  onNewPlan: () => void;
}) {
  return (
    <header
      className="rb-header"
      style={{
        background: "var(--header-bg)",
        borderBottom: "3px solid var(--header-border)",
      }}
    >
      <div className="mx-auto flex w-full items-center justify-between px-5 py-3 sm:px-8" style={{ maxWidth: MAX_W }}>
        <div className="flex items-center gap-3">
          <div
            className="flex items-center justify-center overflow-hidden rounded-full"
            style={{ width: 36, height: 36, background: "#ffffff" }}
          >
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
          {source === "demo" ? (
            <span className="rounded-full px-2 py-0.5" style={{ background: "#9ca3af", color: "#ffffff", fontSize: 11, fontWeight: 600 }}>
              Demo snapshot
            </span>
          ) : null}
          <button
            onClick={onToggle}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            title="Toggle theme"
            style={{ color: "#ffffff", fontSize: 18, lineHeight: 1 }}
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
          <button
            onClick={onNewPlan}
            className="rounded-full px-3 py-1 text-sm font-medium"
            style={{ border: "1px solid #ffffff", color: "#ffffff" }}
          >
            New plan
          </button>
        </div>
      </div>
    </header>
  );
}
