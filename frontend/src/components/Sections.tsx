import { useEffect, useState } from "react";
import { fetchExtra } from "../api";
import type { BriefKey, Plan, Source } from "../types";
import { Badge, Card, money } from "./ui";
import { PeopleResearch } from "./Research";

// Compare / People / Sponsors / Trust / Export panels (P1 tasks 17, 18, 19, 21, 23).
export function Sections({
  text,
  briefKey,
  plan,
  onSource,
}: {
  text: string;
  briefKey: BriefKey | null;
  plan: Plan;
  onSource: (s: Source) => void;
}) {
  const [options, setOptions] = useState<any>(null);
  const [people, setPeople] = useState<any>(null);
  const [sponsors, setSponsors] = useState<any>(null);
  const [trust, setTrust] = useState<any>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      const [o, p, s, t] = await Promise.all([
        fetchExtra("plan/options", text, briefKey),
        fetchExtra("people", text, briefKey),
        fetchExtra("sponsors", text, briefKey),
        fetchExtra("trust", text, briefKey),
      ]);
      if (!active) return;
      setOptions(o.data);
      setPeople(p.data);
      setSponsors(s.data);
      setTrust(t.data);
      if ([o, p, s, t].some((r) => r.source === "demo")) onSource("demo");
    })();
    return () => {
      active = false;
    };
  }, [text, briefKey, onSource]);

  return (
    <div className="space-y-6">
      {options ? <ComparePanel options={options} /> : null}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {people ? (
          <PeoplePanel people={people} text={text} briefKey={briefKey} onSource={onSource} />
        ) : null}
        {sponsors ? <SponsorsPanel sponsors={sponsors} /> : null}
      </div>
      {trust ? <TrustPanel trust={trust} /> : null}
      <ExportPanel plan={plan} />
    </div>
  );
}

function ComparePanel({ options }: { options: any }) {
  const opts = options.options ?? [];
  return (
    <Card>
      <h2 className="mb-3 text-lg font-semibold">Compare: Lean / Balanced / Premium</h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {opts.map((o: any) => (
          <div key={o.name} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
            <p className="font-semibold">{o.name}</p>
            <p className="mt-1 text-sm">{money(o.total_p50)} <span className="text-xs text-gray-400">p50</span></p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {money(o.total_p10)} - {money(o.total_p90)}
            </p>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              gap {money(o.sponsorship_gap)}
            </p>
            <p className="mt-2 text-xs text-gray-600 dark:text-gray-300">{o.tradeoffs}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}

function PeoplePanel({
  people,
  text,
  briefKey,
  onSource,
}: {
  people: any;
  text: string;
  briefKey: BriefKey | null;
  onSource: (s: Source) => void;
}) {
  const list = people.people ?? [];
  return (
    <Card>
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-lg font-semibold">People &amp; sponsors</h2>
        <Badge>{people.similarity_method}</Badge>
      </div>
      {list.length ? (
        <ul className="space-y-1 text-sm">
          {list.slice(0, 6).map((p: any, i: number) => (
            <li key={i}>
              <a href={p.openalex_url} target="_blank" rel="noreferrer"
                 className="text-blue-600 hover:underline dark:text-blue-400">
                {p.name}
              </a>{" "}
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {p.institution} - {p.citations} cites
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-gray-500 dark:text-gray-400">No matches.</p>
      )}
      <p className="mt-2 text-xs text-gray-400">
        Public OpenAlex data only; no contact or demographic inference.
      </p>
      <PeopleResearch text={text} briefKey={briefKey} onSource={onSource} />
    </Card>
  );
}

function SponsorsPanel({ sponsors }: { sponsors: any }) {
  const list = sponsors.categories ?? [];
  return (
    <Card>
      <h2 className="mb-2 text-lg font-semibold">Sponsors</h2>
      <p className="mb-2 text-sm text-gray-600 dark:text-gray-300">
        Suggested ask: <strong>{sponsors.suggested_ask_level}</strong> (gap {money(sponsors.budget_gap)})
      </p>
      <ul className="space-y-1 text-sm">
        {list.slice(0, 6).map((c: any, i: number) => (
          <li key={i} className="flex items-center justify-between">
            <span>{c.label}</span>
            <span className="text-xs text-gray-400">{c.typical_range_usd} {c.typical_ask}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-gray-400">Placeholder sponsor archetypes, not real companies.</p>
    </Card>
  );
}

function TrustPanel({ trust }: { trust: any }) {
  const counts = trust.label_counts ?? {};
  const tornado = trust.sensitivity ?? [];
  const total = Object.values(counts).reduce((a: number, b: any) => a + b, 0) || 1;
  const colors: Record<string, string> = {
    MEASURED: "bg-blue-500", ASSUMED: "bg-amber-500",
    PLACEHOLDER: "bg-gray-400", SIMULATED: "bg-green-500", RESEARCHED: "bg-purple-500",
  };
  const LABELS = ["MEASURED", "ASSUMED", "PLACEHOLDER", "SIMULATED", "RESEARCHED"];
  return (
    <Card>
      <h2 className="mb-2 text-lg font-semibold">Trust</h2>
      <p className="mb-1 text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
        Provenance label mix
      </p>
      <div className="mb-2 flex h-4 overflow-hidden rounded">
        {LABELS.map((l) => (
          <div key={l} className={colors[l]} style={{ width: `${((counts[l] ?? 0) / total) * 100}%` }} title={`${l}: ${counts[l] ?? 0}`} />
        ))}
      </div>
      <div className="mb-3 flex flex-wrap gap-2 text-xs">
        {LABELS.map((l) => (
          <span key={l}>
            <span className={`mr-1 inline-block h-2 w-2 rounded-full ${colors[l]}`} />
            {l} {counts[l] ?? 0}
          </span>
        ))}
      </div>
      {tornado.length ? (
        <>
          <p className="mb-1 text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Sensitivity (readiness delta)
          </p>
          <ul className="space-y-0.5 text-sm">
            {tornado.map((t: any, i: number) => (
              <li key={i} className="flex items-center justify-between">
                <span>{t.driver}</span>
                <span className={t.delta < 0 ? "text-red-600 dark:text-red-400" : "text-gray-500"}>
                  {t.delta > 0 ? "+" : ""}{t.delta}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </Card>
  );
}

function ExportPanel({ plan }: { plan: Plan }) {
  function downloadBudgetCsv() {
    const rows = [["line_item", "p10", "p50", "p90"]];
    for (const li of plan.budget.line_items) {
      rows.push([li.name, String(li.p10), String(li.p50), String(li.p90)]);
    }
    rows.push(["TOTAL", String(plan.budget.total_p10), String(plan.budget.total_p50), String(plan.budget.total_p90)]);
    const csv = rows.map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "eventtwin_budget.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Card>
      <h2 className="mb-2 text-lg font-semibold">Export</h2>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => window.print()}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700"
        >
          Print one-page plan
        </button>
        <button
          onClick={downloadBudgetCsv}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700"
        >
          Download budget CSV
        </button>
      </div>
      <p className="mt-2 text-xs text-gray-400">
        Print uses the browser's print-to-PDF; the CSV is the budget line items.
      </p>
    </Card>
  );
}