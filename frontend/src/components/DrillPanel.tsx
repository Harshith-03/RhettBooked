import { useState } from "react";
import { fetchDrill, fetchDrillCompare } from "../api";
import type { BriefKey, DrillCompare, DrillResult, Source } from "../types";
import { Badge, Card, StatusPill } from "./ui";

// A standard fix set offered by the "Apply fixes & re-run" button.
const STD_FIXES = { add_room_capacity: 300, add_power_circuits: 12, shuttle: true };

export function DrillPanel({
  text,
  briefKey,
  onSource,
}: {
  text: string;
  briefKey: BriefKey | null;
  onSource: (s: Source) => void;
}) {
  const [drill, setDrill] = useState<DrillResult | null>(null);
  const [compare, setCompare] = useState<DrillCompare | null>(null);
  const [busy, setBusy] = useState(false);

  async function runDrill() {
    setBusy(true);
    setCompare(null);
    const { data, source } = await fetchDrill(text, briefKey);
    setDrill(data);
    onSource(source);
    setBusy(false);
  }

  async function applyFixes() {
    setBusy(true);
    const { data, source } = await fetchDrillCompare(text, briefKey, STD_FIXES);
    setCompare(data);
    onSource(source);
    setBusy(false);
  }

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Drill</h2>
        <div className="flex gap-2">
          <button
            onClick={runDrill}
            disabled={busy}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {busy ? "Running..." : "Run drill"}
          </button>
          <button
            onClick={applyFixes}
            disabled={busy || !drill}
            className="rounded-lg border border-blue-600 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-50 dark:text-blue-300 dark:hover:bg-gray-700"
          >
            Apply fixes &amp; re-run
          </button>
        </div>
      </div>

      {!drill ? (
        <p className="text-sm text-gray-600 dark:text-gray-300">
          Run the drill to stress-test occupancy, power, and getting-home across 15-minute blocks.
        </p>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Readiness <strong>{drill.readiness}/100</strong>
            </span>
            <StatusPill status={drill.worst_status} />
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {drill.systems.map((s) => (
              <div key={s.system} className="rounded-lg border border-gray-200 p-2 dark:border-gray-700">
                <div className="flex items-center justify-between">
                  <span className="text-sm capitalize">{s.system.replace("_", " ")}</span>
                  <StatusPill status={s.status} />
                </div>
                {s.first_failure_clock ? (
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    First strain {s.first_failure_clock}
                  </p>
                ) : null}
              </div>
            ))}
          </div>

          {drill.planned_disruptions.length ? (
            <div>
              <Badge tone="amber">
                {drill.planned_disruptions[0].label}
              </Badge>
            </div>
          ) : null}

          <FixList title="Do now" items={drill.fixes.do_now} />

          {compare ? (
            <div className="mt-3 rounded-lg border border-gray-200 p-3 dark:border-gray-700">
              <h3 className="mb-2 text-sm font-semibold">Before / after fixes</h3>
              <div className="flex items-center gap-6 text-sm">
                <BeforeAfter label="Before" r={compare.before.readiness} status={compare.before.worst_status} />
                <span aria-hidden className="text-gray-400">&rarr;</span>
                <BeforeAfter label="After" r={compare.after.readiness} status={compare.after.worst_status} />
                <Badge tone={compare.improved ? "blue" : "amber"}>
                  {compare.improved ? "Improved" : "No change"}
                </Badge>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </Card>
  );
}

function FixList({ title, items }: { title: string; items: string[] }) {
  if (!items?.length) return null;
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">{title}</p>
      <ul className="mt-1 list-disc space-y-0.5 pl-4 text-sm text-gray-800 dark:text-gray-200">
        {items.map((f, i) => (
          <li key={i}>{f}</li>
        ))}
      </ul>
    </div>
  );
}

function BeforeAfter({ label, r, status }: { label: string; r: number; status: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
      <p className="flex items-center gap-2 font-semibold">
        {r}/100 <StatusPill status={status} />
      </p>
    </div>
  );
}
