import { useState } from "react";
import { API_URL, fetchExplanation, fetchPlan } from "./api";
import { BRIEF_TEXT } from "./demo";
import { DrillPanel } from "./components/DrillPanel";
import { Sections } from "./components/Sections";
import { SummaryBar } from "./components/SummaryBar";
import { Tiles } from "./components/Tiles";
import { Badge, Card } from "./components/ui";
import type { BriefKey, Plan, Source } from "./types";

export default function App() {
  const [text, setText] = useState("");
  const [briefKey, setBriefKey] = useState<BriefKey | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [explanation, setExplanation] = useState<string>("");
  const [source, setSource] = useState<Source>("live");
  const [loading, setLoading] = useState(false);

  async function runPlan(inputText: string, key: BriefKey | null) {
    if (!inputText.trim()) return;
    setLoading(true);
    const [planRes, explainRes] = await Promise.all([
      fetchPlan(inputText, key),
      fetchExplanation(inputText, key),
    ]);
    setPlan(planRes.data);
    setExplanation(explainRes.data);
    setSource(planRes.source === "demo" || explainRes.source === "demo" ? "demo" : "live");
    setLoading(false);
  }

  function useExample(key: BriefKey) {
    const t = BRIEF_TEXT[key];
    setText(t);
    setBriefKey(key);
    void runPlan(t, key);
  }

  return (
    <div className="min-h-full bg-gray-50 text-gray-900 dark:bg-gray-900 dark:text-gray-100">
      <div className="mx-auto max-w-5xl px-4 py-8">
        {/* Header */}
        <header className="mb-6 flex items-end justify-between">
          <div>
            <h1 className="text-2xl font-bold">EventTwin</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Describe your event and get one organized plan.
            </p>
          </div>
          {source === "demo" ? (
            <Badge tone="amber" >
              <span aria-hidden>●</span> Demo snapshot
            </Badge>
          ) : null}
        </header>

        {/* Intake */}
        <Card className="mb-6">
          <label htmlFor="brief" className="mb-2 block text-sm font-medium">
            Describe your event
          </label>
          <textarea
            id="brief"
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setBriefKey(null);
            }}
            rows={3}
            placeholder="e.g. 300-person overnight AI hackathon at BU, Oct 24-25, students, budget $15k, needs lunch, dinner, midnight snack, breakfast"
            className="w-full rounded-lg border border-gray-300 bg-white p-3 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800"
          />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              onClick={() => void runPlan(text, briefKey)}
              disabled={loading || !text.trim()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Planning..." : "Build plan"}
            </button>
            <span className="text-xs text-gray-500 dark:text-gray-400">Examples:</span>
            <ExampleChip label="Brief A (Oct 24-25)" onClick={() => useExample("briefA")} />
            <ExampleChip label="Brief B (Oct 31-Nov 1)" onClick={() => useExample("briefB")} />
          </div>
          <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">API: {API_URL}</p>
        </Card>

        {plan ? (
          <div className="space-y-6">
            <SummaryBar summary={plan.summary} />
            {explanation ? (
              <Card>
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  Summary
                </p>
                <p className="mt-1 text-sm text-gray-800 dark:text-gray-200">{explanation}</p>
              </Card>
            ) : null}
            <Tiles plan={plan} text={text} briefKey={briefKey} onSource={setSource} />
            <DrillPanel text={text} briefKey={briefKey} onSource={setSource} />
            <Sections text={text} briefKey={briefKey} plan={plan} onSource={setSource} />
          </div>
        ) : (
          <Card>
            <p className="text-sm text-gray-600 dark:text-gray-300">
              Enter a brief or pick an example to generate a plan.
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}

function ExampleChip({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="rounded-full border border-gray-300 bg-white px-3 py-1 text-xs font-medium hover:border-blue-500 hover:text-blue-600 dark:border-gray-600 dark:bg-gray-800 dark:hover:text-blue-400"
    >
      {label}
    </button>
  );
}
