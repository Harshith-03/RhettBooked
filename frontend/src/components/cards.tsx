import type { Plan, Tile } from "../types";
import {
  CountUp,
  Drawer,
  SectionCard,
  Stat,
  StatusPill,
  money,
} from "./ui";

function tileByName(plan: Plan, name: string): Tile | undefined {
  return plan.tiles.find((t) => t.name === name);
}

function readinessStatus(r: number | null): string {
  if (r === null) return "coming soon";
  if (r >= 80) return "ok";
  if (r >= 50) return "strained";
  return "failing";
}

// --- Summary card: 4 columns (2x2 under 640px).
export function SummaryCard({ plan }: { plan: Plan }) {
  const s = plan.summary;
  return (
    <SectionCard>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat
          label="Recommended venue"
          value={s.recommended_building ?? "-"}
          sub={venueName(plan)}
        />
        <Stat
          label="Final cost (p50)"
          value={<CountUp value={s.cost_p50} suffix="" />}
          sub={`${money(s.cost_p10)} - ${money(s.cost_p90)} · ${money(s.cost_per_attendee)}/attendee`}
        />
        <div>
          <p className="caps-label">Readiness</p>
          <p className="big-number mt-1" style={{ color: "var(--red-text)" }}>
            <CountUp value={s.readiness ?? 0} />
            <span style={{ fontSize: 16 }}>/100</span>
          </p>
          <p className="mt-1">
            <StatusPill status={readinessStatus(s.readiness)} />
          </p>
        </div>
        <Stat
          label="Top risk"
          value={<span style={{ fontSize: 16, fontWeight: 600 }}>{s.top_risks[0] ?? "None flagged"}</span>}
        />
      </div>
    </SectionCard>
  );
}

function venueName(plan: Plan): string {
  const opts = (plan.venue?.options as any[]) ?? [];
  const rec = opts.find((o) => o.feasible) ?? opts[0];
  const first = rec?.assignments?.[0];
  return first?.room_name ? `${rec.building_code}` : rec?.building_code ?? "";
}

// --- Venue + Getting there two-up.
export function TwoUp({ plan }: { plan: Plan }) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <VenueCard plan={plan} />
      <GettingThereCard plan={plan} />
    </div>
  );
}

function VenueCard({ plan }: { plan: Plan }) {
  const tile = tileByName(plan, "Venue");
  const opts = (plan.venue?.options as any[]) ?? [];
  const rec = opts.find((o) => o.feasible) ?? opts[0];
  const consumption = (tile?.details?.consumption as any) ?? null;
  const measured = rec?.measured_share ?? 0;
  const blocks = rec?.assignments?.length ?? 0;
  return (
    <SectionCard>
      <h3 className="mb-2 font-semibold" style={{ fontSize: 17 }}>Venue</h3>
      <p className="text-sm" style={{ color: "var(--muted)" }}>
        {rec?.building_code ?? "-"} fits all {blocks} schedule blocks.
      </p>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <Stat label="Avg utilization" value={`${Math.round((rec?.avg_utilization ?? 0) * 100)}%`} />
        <Stat label="Room cost / hr" value={money(rec?.total_cost ?? 0)} />
        <Stat label="Real BU space data" value={`${Math.round(measured * 100)}%`} />
      </div>
      <Drawer>
        {rec?.assignments?.length ? (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="caps-label">
                <th className="pb-1">Block</th>
                <th className="pb-1">Room</th>
                <th className="pb-1 text-right">Cap</th>
                <th className="pb-1 text-right">Util</th>
              </tr>
            </thead>
            <tbody>
              {rec.assignments.map((a: any, i: number) => (
                <tr key={i} style={{ borderTop: "1px solid var(--border)" }}>
                  <td className="py-1">{a.block}</td>
                  <td className="py-1">{a.room_name}</td>
                  <td className="py-1 text-right">{a.capacity}</td>
                  <td className="py-1 text-right">{Math.round((a.utilization ?? 0) * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
        {tile?.action_items?.length ? (
          <div className="mt-3">
            <p className="caps-label">Do now</p>
            <ul className="mt-1 list-disc pl-4 text-sm">
              {tile.action_items.map((a, i) => <li key={i}>{a}</li>)}
            </ul>
          </div>
        ) : null}
        {consumption ? <ConsumptionTable c={consumption} /> : null}
      </Drawer>
    </SectionCard>
  );
}

const CONSUMPTION_ROWS: [string, string][] = [
  ["peak_devices", "Peak devices"],
  ["peak_mbps", "Peak Mbps"],
  ["total_gb", "Total GB"],
  ["peak_circuits", "Peak circuits"],
  ["total_kwh", "Total kWh"],
];

export function ConsumptionTable({ c }: { c: any }) {
  if (!c) return null;
  return (
    <div className="mt-3">
      <p className="caps-label">Wi-Fi &amp; power (consumption, no $ cost)</p>
      <table className="mt-1 w-full text-left text-sm">
        <thead>
          <tr className="caps-label">
            <th className="pb-1">Metric</th>
            <th className="pb-1 text-right">p10</th>
            <th className="pb-1 text-right">p50</th>
            <th className="pb-1 text-right">p90</th>
          </tr>
        </thead>
        <tbody>
          {CONSUMPTION_ROWS.filter(([k]) => c[k]).map(([k, label]) => (
            <tr key={k} style={{ borderTop: "1px solid var(--border)" }}>
              <td className="py-1">{label}</td>
              <td className="py-1 text-right">{Math.round(c[k].p10)}</td>
              <td className="py-1 text-right">{Math.round(c[k].p50)}</td>
              <td className="py-1 text-right">{Math.round(c[k].p90)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GettingThereCard({ plan }: { plan: Plan }) {
  const d = (tileByName(plan, "Getting There")?.details as any) ?? {};
  const stops = (d.stops as any[]) ?? [];
  const planned = ((d.planned_disruptions as any[]) ?? []).filter((p) => p.overlaps_event);
  const parking = (d.parking as any[]) ?? [];
  const nearest = stops[0];
  return (
    <SectionCard>
      <h3 className="mb-2 font-semibold" style={{ fontSize: 17 }}>Getting there</h3>
      {planned.length ? (
        <p className="text-sm" style={{ color: "var(--red-text)" }}>
          {planned[0].label}
        </p>
      ) : (
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          No planned MBTA disruptions for these dates.
        </p>
      )}
      {nearest ? (
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Stat label="Nearest stop" value={<span style={{ fontSize: 16, fontWeight: 600 }}>{nearest.name}</span>}
            sub={`${nearest.walk_min ?? "?"} min · ${nearest.accessible ? "step-free" : "not step-free"}`} />
          <Stat label="Parking options" value={parking.length} sub={parking[0]?.name ?? ""} />
        </div>
      ) : null}
      <Drawer>
        <p className="caps-label">Nearest stops</p>
        <ul className="mb-3 mt-1 space-y-1 text-sm">
          {stops.slice(0, 5).map((s: any, i: number) => (
            <li key={i} className="flex items-center justify-between">
              <span>{s.name} <span className="text-xs" style={{ color: "var(--muted)" }}>{(s.lines ?? []).join(", ")}</span></span>
              <span className="flex items-center gap-2 text-xs">
                {s.walk_min != null ? <span>{s.walk_min} min</span> : null}
                <StatusPill status={s.accessible ? "ok" : "strained"} />
              </span>
            </li>
          ))}
        </ul>
        {(d.accessibility_flags as string[] | undefined)?.length ? (
          <p className="mb-3 text-xs" style={{ color: "var(--warn-text)" }}>
            Accessibility: {(d.accessibility_flags as string[]).join("; ")}
          </p>
        ) : null}
        {parking.length ? (
          <>
            <p className="caps-label">Parking</p>
            <ul className="mt-1 space-y-0.5 text-sm">
              {parking.slice(0, 4).map((p: any, i: number) => (
                <li key={i} className="flex items-center justify-between">
                  <span>{p.name}</span>
                  <span className="text-xs" style={{ color: "var(--muted)" }}>{p.type}{p.public_or_visitor === "yes" ? " · visitor" : ""}</span>
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </Drawer>
    </SectionCard>
  );
}
