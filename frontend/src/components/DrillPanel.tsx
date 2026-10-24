import { useState } from "react";
import { fetchDrill, fetchDrillCompare } from "../api";
import type { BriefKey, DrillCompare, DrillResult, Source } from "../types";
import { CountUp, PrimaryButton, SecondaryButton, SectionCard, StatusPill } from "./ui";

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
    <SectionCard>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-semibold" style={{ fontSize: 17 }}>The drill</h3>
        <div className="flex gap-2">
          <PrimaryButton onClick={runDrill} disabled={busy}>
            {busy ? "Running..." : "Run drill"}
          </PrimaryButton>
          <SecondaryButton onClick={applyFixes} disabled={busy || !drill}>
            Apply fixes &amp; re-run
          </SecondaryButton>
        </div>
      </div>

      {!drill ? (
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Run the drill to stress-test occupancy, power, and getting-home across 15-minute blocks.
        </p>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {drill.systems.filter((s) => ["occupancy", "power", "getting_home"].includes(s.system)).map((s) => (
              <div key={s.system} className="rounded-lg p-3" style={{ border: "1px solid var(--border)" }}>
                <div className="flex items-center justify-between">
                  <span className="text-sm capitalize">{s.system.replace("_", " ")}</span>
                  <StatusPill status={s.status} />
                </div>
                {s.first_failure_clock ? (
                  <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>First strain {s.first_failure_clock}</p>
                ) : null}
              </div>
            ))}
          </div>

          {drill.fixes.do_now.length ? (
            <div>
              <p className="caps-label" style={{ color: "var(--red-text)" }}>Do now</p>
              <ul className="mt-1 list-disc pl-4 text-sm">
                {drill.fixes.do_now.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
            </div>
          ) : null}

          {compare ? (
            <div className="flex items-center gap-4 rounded-lg p-3 text-sm" style={{ border: "1px solid var(--border)" }}>
              <div>
                <p className="caps-label">Before</p>
                <p className="flex items-center gap-2 font-semibold">
                  {compare.before.readiness}/100 <StatusPill status={compare.before.worst_status} />
                </p>
              </div>
              <span aria-hidden style={{ color: "var(--muted)" }}>→</span>
              <div>
                <p className="caps-label">After fixes</p>
                <p className="flex items-center gap-2 font-semibold">
                  <CountUp value={compare.after.readiness} />/100 <StatusPill status={compare.after.worst_status} />
                </p>
              </div>
              {compare.after.readiness > compare.before.readiness ? (
                <span className="text-xs font-semibold" style={{ color: "var(--ok-text)" }}>
                  +{compare.after.readiness - compare.before.readiness} points
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
      )}
    </SectionCard>
  );
}
