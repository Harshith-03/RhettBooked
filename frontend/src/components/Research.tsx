import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { runResearch } from "../api";
import type { BriefKey, Source } from "../types";

const DISCLAIMER =
  "Found by AI web research. Every result links its sources. Verify before contacting or booking.";

// Progress list with animated step ticks.
function Steps({ steps, running }: { steps: string[]; running: boolean }) {
  return (
    <ul className="my-2 space-y-1 text-sm">
      <AnimatePresence initial={false}>
        {steps.map((s, i) => (
          <motion.li
            key={i}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2 }}
            className="flex items-center gap-2 text-gray-600 dark:text-gray-300"
          >
            <span aria-hidden className="text-green-600">
              {running && i === steps.length - 1 ? "…" : "✓"}
            </span>
            {s}
          </motion.li>
        ))}
      </AnimatePresence>
    </ul>
  );
}

function VerificationPill({ v }: { v: string }) {
  const verified = v === "VERIFIED";
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
        verified
          ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
          : "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200"
      }`}
    >
      {verified ? "✓ Verified (OSM)" : "! Web-only · verify"}
    </span>
  );
}

function Sources({ urls }: { urls: string[] }) {
  const [open, setOpen] = useState(false);
  if (!urls?.length) return null;
  return (
    <div className="mt-1">
      <button onClick={() => setOpen((v) => !v)} className="text-xs text-blue-600 hover:underline dark:text-blue-400">
        {open ? "Hide sources" : `Sources (${urls.length})`}
      </button>
      {open ? (
        <ul className="mt-1 space-y-0.5">
          {urls.map((u, i) => (
            <li key={i} className="truncate text-xs">
              <a href={u} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline dark:text-blue-400">
                {u}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function fadeUp(i: number) {
  return {
    initial: { opacity: 0, y: 8 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.25, delay: i * 0.05 },
  };
}

// --- Caterers (Food & water) ---
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
    <div className="mt-3 border-t border-gray-100 pt-3 dark:border-gray-700">
      <button
        onClick={run}
        disabled={busy}
        className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
      >
        {busy ? "Researching…" : "Find real caterers"}
      </button>
      {steps.length ? <Steps steps={steps} running={busy} /> : null}
      {result?.fallback_reason ? (
        <p className="mt-1 text-xs italic text-amber-700 dark:text-amber-300">
          Showing estimates: {result.fallback_reason}
        </p>
      ) : null}
      {result?.meals?.map((m: any) => (
        <div key={m.meal} className="mt-3">
          <p className="text-xs font-semibold uppercase capitalize text-gray-500 dark:text-gray-400">{m.meal}</p>
          <div className="mt-1 space-y-2">
            {m.caterers.map((c: any, i: number) => (
              <motion.div
                key={i}
                {...fadeUp(i)}
                className="rounded border border-gray-100 p-2 text-sm dark:border-gray-700"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{c.name}</span>
                  <VerificationPill v={c.verification} />
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {c.distance_m} m{c.cuisine ? ` · ${c.cuisine}` : ""}
                  {c.price_per_head_low != null
                    ? ` · $${c.price_per_head_low}-${c.price_per_head_high}/head (${c.price_note})`
                    : ""}
                </p>
                {c.dietary?.length ? (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {c.dietary.map((d: string) => (
                      <span key={d} className="rounded-full border border-gray-300 px-2 py-0.5 text-xs dark:border-gray-600">{d}</span>
                    ))}
                  </div>
                ) : null}
                {c.catering_url ? (
                  <a href={c.catering_url} target="_blank" rel="noreferrer" className="mt-1 inline-block text-xs text-blue-600 hover:underline dark:text-blue-400">
                    Catering page →
                  </a>
                ) : null}
                <Sources urls={c.source_urls} />
              </motion.div>
            ))}
            {m.caterers.length === 0 ? (
              <p className="text-xs text-gray-500 dark:text-gray-400">No cited caterers; showing the estimate above.</p>
            ) : null}
          </div>
        </div>
      ))}
      {result ? <p className="mt-2 text-xs text-gray-400">{DISCLAIMER}</p> : null}
    </div>
  );
}

// --- People & sponsors ---
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
    <div className="mt-3 border-t border-gray-100 pt-3 dark:border-gray-700">
      <button
        onClick={run}
        disabled={busy}
        className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
      >
        {busy ? "Researching…" : "Research speakers, judges & sponsors"}
      </button>
      {steps.length ? <Steps steps={steps} running={busy} /> : null}
      {result?.fallback_reason ? (
        <p className="mt-1 text-xs italic text-amber-700 dark:text-amber-300">{result.fallback_reason}</p>
      ) : null}
      {groups.map(([label, list]) => (
        <div key={label} className="mt-3">
          <p className="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">{label}</p>
          <div className="mt-1 space-y-2">
            {list.map((p: any, i: number) => (
              <motion.div key={i} {...fadeUp(i)} className="rounded border border-gray-100 p-2 text-sm dark:border-gray-700">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{p.name}</span>
                  {p.research_data ? (
                    <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                      Research data
                    </span>
                  ) : null}
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {[p.role, p.organization].filter(Boolean).join(" · ")}
                </p>
                {p.relevance ? <p className="text-xs">{p.relevance}</p> : null}
                {p.profile_url ? (
                  <a href={p.profile_url} target="_blank" rel="noreferrer" className="text-xs text-blue-600 hover:underline dark:text-blue-400">
                    Profile →
                  </a>
                ) : null}
                <Sources urls={p.source_urls} />
                {p.note ? <p className="mt-1 text-xs text-gray-400">{p.note}</p> : null}
              </motion.div>
            ))}
            {list.length === 0 ? <p className="text-xs text-gray-500 dark:text-gray-400">None found.</p> : null}
          </div>
        </div>
      ))}
      {result ? <p className="mt-2 text-xs text-gray-400">{DISCLAIMER}</p> : null}
    </div>
  );
}
