import { useEffect, useState } from "react";
import { fetchExtra } from "../api";
import type { BriefKey, Plan, Source } from "../types";
import { Drawer, SectionCard, money } from "./ui";
import { PeopleResearch } from "./Research";

// People & sponsors, Plan options, Trust & export - collapsed by default.
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
    <>
      <PeopleSponsorsCard
        people={people}
        sponsors={sponsors}
        text={text}
        briefKey={briefKey}
        onSource={onSource}
      />
      <OptionsCard options={options} />
      <TrustExportCard trust={trust} plan={plan} />
    </>
  );
}

function PeopleSponsorsCard({
  people,
  sponsors,
  text,
  briefKey,
  onSource,
}: {
  people: any;
  sponsors: any;
  text: string;
  briefKey: BriefKey | null;
  onSource: (s: Source) => void;
}) {
  const judges = people?.people ?? [];
  const cats = sponsors?.categories ?? [];
  return (
    <SectionCard>
      <h3 className="font-semibold" style={{ fontSize: 17 }}>People &amp; sponsors</h3>
      <Drawer label="Show people & sponsors →">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <p className="caps-label">Judges / speakers {people ? `(${people.similarity_method})` : ""}</p>
            <ul className="mt-1 space-y-1 text-sm">
              {judges.slice(0, 6).map((p: any, i: number) => (
                <li key={i}>
                  <a href={p.openalex_url} target="_blank" rel="noreferrer"
                     style={{ color: "var(--red-text)" }} className="hover:underline">
                    {p.name}
                  </a>{" "}
                  <span className="text-xs" style={{ color: "var(--muted)" }}>
                    {p.institution} · {p.citations} cites
                  </span>
                </li>
              ))}
              {judges.length === 0 ? <li className="text-sm" style={{ color: "var(--muted)" }}>No matches.</li> : null}
            </ul>
            <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
              Public OpenAlex data only; no contact or demographic inference.
            </p>
          </div>
          <div>
            <p className="caps-label">Sponsor categories</p>
            {sponsors ? (
              <p className="mt-1 text-sm">
                Suggested ask: <strong>{sponsors.suggested_ask_level}</strong> (gap {money(sponsors.budget_gap)})
              </p>
            ) : null}
            <ul className="mt-1 space-y-1 text-sm">
              {cats.slice(0, 6).map((c: any, i: number) => (
                <li key={i} className="flex items-center justify-between">
                  <span>{c.label}</span>
                  <span className="text-xs" style={{ color: "var(--muted)" }}>{c.typical_range_usd} {c.typical_ask}</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
              Placeholder sponsor archetypes, not real companies.
            </p>
          </div>
        </div>
        <PeopleResearch text={text} briefKey={briefKey} onSource={onSource} />
      </Drawer>
    </SectionCard>
  );
}

function OptionsCard({ options }: { options: any }) {
  const opts = options?.options ?? [];
  return (
    <SectionCard>
      <h3 className="font-semibold" style={{ fontSize: 17 }}>Plan options</h3>
      <Drawer label="Compare Lean / Balanced / Premium →">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {opts.map((o: any) => (
            <div key={o.name} className="rounded-lg p-3" style={{ border: "1px solid var(--border)" }}>
              <p className="font-semibold">{o.name}</p>
              <p className="mt-1 text-sm">{money(o.total_p50)} <span className="text-xs" style={{ color: "var(--muted)" }}>p50</span></p>
              <p className="text-xs" style={{ color: "var(--muted)" }}>{money(o.total_p10)} - {money(o.total_p90)}</p>
              <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>gap {money(o.sponsorship_gap)}</p>
              <p className="mt-2 text-xs">{o.tradeoffs}</p>
            </div>
          ))}
        </div>
      </Drawer>
    </SectionCard>
  );
}

function TrustExportCard({ trust, plan }: { trust: any; plan: Plan }) {
  const counts = trust?.label_counts ?? {};
  const tornado = trust?.sensitivity ?? [];
  const total = (Object.values(counts) as number[]).reduce((a, b) => a + b, 0) || 1;
  const colors: Record<string, string> = {
    MEASURED: "#3b82f6", ASSUMED: "#f59e0b", PLACEHOLDER: "#9ca3af",
    SIMULATED: "#22c55e", RESEARCHED: "#8b5cf6",
  };
  const LABELS = ["MEASURED", "ASSUMED", "PLACEHOLDER", "SIMULATED", "RESEARCHED"];

  function downloadCsv() {
    const rows = [["line_item", "p10", "p50", "p90"]];
    for (const li of plan.budget.line_items) rows.push([li.name, String(li.p10), String(li.p50), String(li.p90)]);
    rows.push(["TOTAL", String(plan.budget.total_p10), String(plan.budget.total_p50), String(plan.budget.total_p90)]);
    const csv = rows.map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url; a.download = "eventtwin_budget.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <SectionCard>
      <h3 className="font-semibold" style={{ fontSize: 17 }}>Trust &amp; export</h3>
      <Drawer label="Show provenance, privacy & export →">
        <p className="caps-label">Provenance label mix</p>
        <div className="mb-2 mt-1 flex h-4 overflow-hidden rounded">
          {LABELS.map((l) => (
            <div key={l} style={{ background: colors[l], width: `${((counts[l] ?? 0) / total) * 100}%` }} title={`${l}: ${counts[l] ?? 0}`} />
          ))}
        </div>
        <div className="mb-3 flex flex-wrap gap-3 text-xs">
          {LABELS.map((l) => (
            <span key={l}>
              <span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: colors[l] }} />
              {l} {counts[l] ?? 0}
            </span>
          ))}
        </div>

        {tornado.length ? (
          <>
            <p className="caps-label">Sensitivity (readiness delta)</p>
            <ul className="mb-3 mt-1 space-y-0.5 text-sm">
              {tornado.map((t: any, i: number) => (
                <li key={i} className="flex items-center justify-between">
                  <span>{t.driver}</span>
                  <span style={{ color: t.delta < 0 ? "var(--red-text)" : "var(--muted)" }}>
                    {t.delta > 0 ? "+" : ""}{t.delta}
                  </span>
                </li>
              ))}
            </ul>
          </>
        ) : null}

        <p className="caps-label">Privacy</p>
        <p className="mb-3 mt-1 text-xs" style={{ color: "var(--muted)" }}>
          Uploaded data is scrubbed (emails, BU IDs, MAC/BSSID, phones); aggregates suppress cells under 5.
          Regex detection does not catch names; NER via Presidio is planned.
        </p>

        <div className="flex flex-wrap gap-2">
          <button onClick={() => window.print()} className="rounded-lg px-3 py-1.5 text-sm font-medium"
                  style={{ border: "1px solid var(--text)" }}>
            Print one-page plan
          </button>
          <button onClick={downloadCsv} className="rounded-lg px-3 py-1.5 text-sm font-medium"
                  style={{ border: "1px solid var(--text)" }}>
            Download budget CSV
          </button>
        </div>
      </Drawer>
    </SectionCard>
  );
}
