import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { runResearch } from "../api";
import { usePrefersReducedMotion } from "../theme";
import type { BriefKey, Source } from "../types";
import { PrimaryButton, StatusPill, money } from "./ui";

const DISCLAIMER =
  "Found by AI web research. Every result links its sources. Verify before contacting or booking.";

// Progress list with animated step ticks (design-v2 motion).
function Steps({ steps, running }: { steps: string[]; running: boolean }) {
  const reduced = usePrefersReducedMotion();
  return (
    <ul className="my-2 space-y-1 text-sm">
      <AnimatePresence initial={false}>
        {steps.map((s, i) => (
          <motion.li
            key={i}
            initial={{ opacity: 0, x: reduced ? 0 : -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: reduced ? 0 : 0.2 }}
            className="flex items-center gap-2"
            style={{ color: "var(--muted)" }}
          >
            <span aria-hidden style={{ color: "var(--ok-text)" }}>
              {running && i === steps.length - 1 ? "…" : "✓"}
            </span>
            {s}
          </motion.li>
        ))}
      </AnimatePresence>
    </ul>
  );
}

// Verified / Web-only / Curated as a design-v2 status pill (colour AND text).
function VerificationPill({ v }: { v: string }) {
  if (v === "VERIFIED") return <StatusPill status="ok" />;
  if (v === "CURATED") return <StatusPill status="curated" />;
  return <StatusPill status="strained" />;
}

function Chipish({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="rounded-full px-2 py-0.5 text-xs"
      style={{ border: "1px solid var(--border)", color: "var(--text)" }}
    >
      {children}
    </span>
  );
}

function Sources({ urls }: { urls: string[] }) {
  const [open, setOpen] = useState(false);
  if (!urls?.length) return null;
  return (
    <div className="mt-1">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-xs hover:underline"
        style={{ color: "var(--red-text)" }}
      >
        {open ? "Hide sources" : `Sources (${urls.length})`}
      </button>
      {open ? (
        <ul className="mt-1 space-y-0.5">
          {urls.map((u, i) => (
            <li key={i} className="truncate text-xs">
              <a href={u} target="_blank" rel="noreferrer" className="hover:underline" style={{ color: "var(--red-text)" }}>
                {u}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function ResultCard({ i, children }: { i: number; children: React.ReactNode }) {
  const reduced = usePrefersReducedMotion();
  return (
    <motion.div
      initial={{ opacity: 0, y: reduced ? 0 : 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduced ? 0 : 0.25, delay: reduced ? 0 : i * 0.05 }}
      className="rounded-lg p-2 text-sm"
      style={{ border: "1px solid var(--border)" }}
    >
      {children}
    </motion.div>
  );
}

function Disclaimer() {
  return (
    <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
      {DISCLAIMER}
    </p>
  );
}

// --- Caterers (inside the Food & water card) ---
export function CatererResearch({
  text,
  briefKey,
  onSource,
  onResearchedPrices,
}: {
  text: string;
  briefKey: BriefKey | null;
  onSource: (s: Source) => void;
  onResearchedPrices?: (range: { low: number; high: number; n: number } | null) => void;
}) {
  const [steps, setSteps] = useState<string[]>([]);
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setResult(null);
    const { data, source } = await runResearch("catering", text, briefKey, setSteps);
    setResult(data);
    onSource(source);
    onResearchedPrices?.(data?.researched_per_head ?? null);
    setBusy(false);
  }

  return (
    <div className="mt-3 border-t pt-3" style={{ borderColor: "var(--border)" }}>
      <PrimaryButton onClick={run} disabled={busy}>
        {busy ? "Researching…" : "Find real caterers"}
      </PrimaryButton>
      {steps.length ? <Steps steps={steps} running={busy} /> : null}
      {result?.fallback_reason ? (
        <p className="mt-1 text-xs italic" style={{ color: "var(--warn-text)" }}>
          Showing estimates: {result.fallback_reason}
        </p>
      ) : null}
      {result?.meals?.map((m: any) => (
        <div key={m.meal} className="mt-3">
          <p className="caps-label capitalize">{m.meal}</p>
          <div className="mt-1 space-y-2">
            {m.caterers.map((c: any, i: number) => (
              <ResultCard key={i} i={i}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{c.name}</span>
                  <VerificationPill v={c.verification} />
                </div>
                <p className="text-xs" style={{ color: "var(--muted)" }}>
                  {c.distance_m} m{c.cuisine ? ` · ${c.cuisine}` : ""}
                  {c.price_per_head_low != null
                    ? ` · ${money(c.price_per_head_low)}-${money(c.price_per_head_high)}/head (${c.price_note})`
                    : ""}
                </p>
                {c.dietary?.length ? (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {c.dietary.map((d: string) => <Chipish key={d}>{d}</Chipish>)}
                  </div>
                ) : null}
                {c.catering_url ? (
                  <a href={c.catering_url} target="_blank" rel="noreferrer" className="mt-1 inline-block text-xs hover:underline" style={{ color: "var(--red-text)" }}>
                    Catering page →
                  </a>
                ) : null}
                <Sources urls={c.source_urls} />
              </ResultCard>
            ))}
            {m.caterers.length === 0 ? (
              <p className="text-xs" style={{ color: "var(--muted)" }}>No cited caterers; the estimate above stands.</p>
            ) : null}
          </div>
        </div>
      ))}
      {result ? <Disclaimer /> : null}
    </div>
  );
}

// --- People & sponsors (inside the People & sponsors card) ---
export function PeopleResearch({
  text,
  briefKey,
  onSource,
}: {
  text: string;
  briefKey: BriefKey | null;
  onSource: (s: Source) => void;
}) {
  const [steps, setSteps] = useState<string[]>([]);
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setResult(null);
    const { data, source } = await runResearch("people", text, briefKey, setSteps);
    setResult(data);
    onSource(source);
    setBusy(false);
  }

  const groups: [string, any[]][] = result
    ? [
        ["Judges", result.judges ?? []],
        ["Keynote speakers", result.speakers ?? []],
        ["Sponsors", result.sponsors ?? []],
      ]
    : [];

  return (
    <div className="mt-3 border-t pt-3" style={{ borderColor: "var(--border)" }}>
      <PrimaryButton onClick={run} disabled={busy}>
        {busy ? "Researching…" : "Research speakers, judges & sponsors"}
      </PrimaryButton>
      {steps.length ? <Steps steps={steps} running={busy} /> : null}
      {result?.fallback_reason ? (
        <p className="mt-1 text-xs italic" style={{ color: "var(--warn-text)" }}>{result.fallback_reason}</p>
      ) : null}
      {groups.map(([label, list]) => (
        <div key={label} className="mt-3">
          <p className="caps-label">{label}</p>
          <div className="mt-1 space-y-2">
            {list.map((p: any, i: number) => (
              <ResultCard key={i} i={i}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{p.name}</span>
                  {p.research_data ? <StatusPill status="ok" /> : null}
                </div>
                <p className="text-xs" style={{ color: "var(--muted)" }}>
                  {[p.role, p.organization].filter(Boolean).join(" · ")}
                </p>
                {p.relevance ? <p className="text-xs">{p.relevance}</p> : null}
                {p.profile_url ? (
                  <a href={p.profile_url} target="_blank" rel="noreferrer" className="text-xs hover:underline" style={{ color: "var(--red-text)" }}>
                    Profile →
                  </a>
                ) : null}
                <Sources urls={p.source_urls} />
                {p.note ? <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{p.note}</p> : null}
              </ResultCard>
            ))}
            {list.length === 0 ? <p className="text-xs" style={{ color: "var(--muted)" }}>None found.</p> : null}
          </div>
        </div>
      ))}
      {result ? <Disclaimer /> : null}
    </div>
  );
}
