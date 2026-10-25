import { useEffect, useState } from "react";
import { fetchPlan } from "./api";
import { BRIEF_TEXT } from "./demo";
import { DrillPanel } from "./components/DrillPanel";
import { Sections } from "./components/Sections";
import { SummaryCard, TwoUp } from "./components/cards";
import { BudgetCard, FoodWaterCard } from "./components/budgetfood";
import {
  Chip,
  PrimaryButton,
  SectionCard,
  Skeleton,
  Stagger,
  StaggerItem,
} from "./components/ui";
import { applyTheme, getInitialTheme, setTheme, type Theme } from "./theme";
import type { BriefKey, Plan, Source } from "./types";

export default function App() {
  const [theme, setThemeState] = useState<Theme>("light");
  const [text, setText] = useState("");
  const [briefKey, setBriefKey] = useState<BriefKey | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [source, setSource] = useState<Source>("live");
  const [loading, setLoading] = useState(false);
  // Researched per-head range discovered by the Food & water caterer research,
  // lifted so the Budget card can offer "Use researched prices".
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
    const { data, source } = await fetchPlan(inputText, key);
    setPlan(data);
    setSource(source);
    setLoading(false);
  }

  function useExample(key: BriefKey) {
    const t = BRIEF_TEXT[key];
    setText(t);
    setBriefKey(key);
    void runPlan(t, key);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter builds the plan (Shift+Enter inserts a newline).
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void runPlan(text, briefKey);
    }
  }

  return (
    <div style={{ minHeight: "100%", background: "var(--bg)", color: "var(--text)" }}>
      <Header theme={theme} onToggle={toggleTheme} source={source} onNewPlan={() => setPlan(null)} />

      <div className="mx-auto w-full" style={{ maxWidth: 800, padding: 24 }}>
        <div className="space-y-4">
          {/* Describe your event */}
          <SectionCard>
            <label htmlFor="brief" className="caps-label">Describe your event</label>
            <textarea
              id="brief"
              value={text}
              onChange={(e) => { setText(e.target.value); setBriefKey(null); }}
              onKeyDown={onKeyDown}
              rows={3}
              placeholder="e.g. 300-person overnight AI hackathon at BU, Oct 24-25, students, budget $15k, needs lunch, dinner, midnight snack, breakfast"
              className="mt-2 w-full rounded-lg p-3 text-sm"
              style={{ border: "1px solid var(--border)", background: "var(--card)", color: "var(--text)" }}
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <PrimaryButton onClick={() => void runPlan(text, briefKey)} disabled={loading || !text.trim()}>
                {loading ? "Planning..." : "Build plan"}
              </PrimaryButton>
              <Chip label="Brief A · Oct 24-25" active={briefKey === "briefA"} onClick={() => useExample("briefA")} />
              <Chip label="Brief B · Oct 31-Nov 1" active={briefKey === "briefB"} onClick={() => useExample("briefB")} />
            </div>
          </SectionCard>

          {loading && !plan ? (
            <div className="space-y-4">
              <Skeleton height={100} />
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Skeleton height={160} />
                <Skeleton height={160} />
              </div>
              <Skeleton height={220} />
            </div>
          ) : plan ? (
            <Stagger key={`${briefKey}-${source}`}>
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
          ) : (
            <SectionCard>
              <p className="text-sm" style={{ color: "var(--muted)" }}>
                Enter a brief or pick an example to generate a plan.
              </p>
            </SectionCard>
          )}
        </div>
      </div>
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
      style={{
        background: "var(--header-bg)",
        borderBottom: "3px solid var(--header-border)",
      }}
    >
      <div className="mx-auto flex w-full items-center justify-between" style={{ maxWidth: 800, padding: "12px 24px" }}>
        <div className="flex items-center gap-3">
          <div
            className="flex items-center justify-center overflow-hidden rounded-full"
            style={{ width: 36, height: 36, background: "#ffffff" }}
          >
            <img
              src="/logo.png"
              alt="EventTwin logo"
              width={36}
              height={36}
              style={{ width: 36, height: 36, objectFit: "contain" }}
            />
          </div>
          <div>
            <div style={{ color: "#ffffff", fontWeight: 700, fontSize: 18, lineHeight: 1 }}>EventTwin</div>
            <div style={{ color: "#ffffff", opacity: 0.85, fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase" }}>
              BU Event Planner
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {source === "demo" ? (
            <span
              className="rounded-full px-2 py-0.5"
              style={{ background: "#9ca3af", color: "#ffffff", fontSize: 11, fontWeight: 600 }}
            >
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
