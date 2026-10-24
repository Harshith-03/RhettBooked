import type { Plan, Tile } from "../types";
import { Badge, TileCard, money } from "./ui";

export function Tiles({ plan }: { plan: Plan }) {
  const byName = Object.fromEntries(plan.tiles.map((t) => [t.name, t]));
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <VenueTile tile={byName["Venue"]} venue={plan.venue} />
      <BudgetTile plan={plan} tile={byName["Budget"]} />
      <GettingThereTile tile={byName["Getting There"]} />
      <FoodWaterTile tile={byName["Food & Water"]} />
      <DrillSummaryTile tile={byName["Drill"]} />
    </div>
  );
}

function VenueTile({ tile, venue }: { tile?: Tile; venue: Record<string, unknown> }) {
  if (!tile) return null;
  const options = (venue?.options as any[]) ?? [];
  const rec = options.find((o) => o.feasible) ?? options[0];
  const measured = rec?.measured_share ?? 0;
  return (
    <TileCard title="Venue" status={tile.status}>
      {/* Map placeholder slot (map deferred). */}
      <div className="mb-3 flex h-28 items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50 text-xs text-gray-500 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-400">
        Map placeholder (building, rooms, stops) - coming soon
      </div>
      <div className="mb-2">
        <Badge tone={measured >= 0.999 ? "blue" : "amber"}>
          {measured >= 0.999
            ? "100% real BU event-space data"
            : `${Math.round(measured * 100)}% real data - verify placeholders`}
        </Badge>
      </div>
      {rec?.assignments?.length ? (
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-gray-500 dark:text-gray-400">
            <tr>
              <th className="pb-1">Block</th>
              <th className="pb-1">Room</th>
              <th className="pb-1 text-right">Cap</th>
              <th className="pb-1 text-right">Util</th>
            </tr>
          </thead>
          <tbody>
            {rec.assignments.map((a: any, i: number) => (
              <tr key={i} className="border-t border-gray-100 dark:border-gray-700">
                <td className="py-1">{a.block}</td>
                <td className="py-1">{a.room_name}</td>
                <td className="py-1 text-right">{a.capacity}</td>
                <td className="py-1 text-right">{Math.round((a.utilization ?? 0) * 100)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {tile.action_items?.length ? (
        <div className="mt-3">
          <p className="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Do now</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-sm text-gray-800 dark:text-gray-200">
            {tile.action_items.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </TileCard>
  );
}

function BudgetTile({ plan, tile }: { plan: Plan; tile?: Tile }) {
  if (!tile) return null;
  const b = plan.budget;
  return (
    <TileCard title="Budget" status={tile.status}>
      <p className="mb-2 text-sm text-gray-700 dark:text-gray-300">
        Sponsorship gap: <strong>{money(b.sponsorship_gap)}</strong> (p50 cost minus budget)
      </p>
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase text-gray-500 dark:text-gray-400">
          <tr>
            <th className="pb-1">Line item</th>
            <th className="pb-1 text-right">p10</th>
            <th className="pb-1 text-right">p50</th>
            <th className="pb-1 text-right">p90</th>
          </tr>
        </thead>
        <tbody>
          {b.line_items.map((li, i) => (
            <tr key={i} className="border-t border-gray-100 dark:border-gray-700">
              <td className="py-1">{li.name}</td>
              <td className="py-1 text-right">{money(li.p10)}</td>
              <td className="py-1 text-right">{money(li.p50)}</td>
              <td className="py-1 text-right">{money(li.p90)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TileCard>
  );
}

function GettingThereTile({ tile }: { tile?: Tile }) {
  if (!tile) return null;
  const planned = (tile.details?.planned_disruptions as any[]) ?? [];
  return (
    <TileCard title="Getting There" status={tile.status}>
      {planned.length ? (
        <ul className="space-y-2 text-sm">
          {planned.map((p, i) => (
            <li key={i} className="rounded border border-amber-200 bg-amber-50 p-2 dark:border-amber-800 dark:bg-amber-950">
              <p className="font-medium text-amber-900 dark:text-amber-200">{p.label}</p>
              <p className="text-xs text-amber-800 dark:text-amber-300">
                {p.start_date} to {p.end_date}
                {p.fare_free ? " - fare-free" : ""}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-gray-600 dark:text-gray-300">No planned transit disruptions overlap the event dates.</p>
      )}
    </TileCard>
  );
}

function FoodWaterTile({ tile }: { tile?: Tile }) {
  if (!tile) return null;
  return (
    <TileCard title="Food & Water" status={tile.status}>
      <p className="text-sm text-gray-600 dark:text-gray-300">
        BU dining halls open during each meal window are preferred, then nearby restaurants. Full plan arrives in a later task.
      </p>
    </TileCard>
  );
}

function DrillSummaryTile({ tile }: { tile?: Tile }) {
  if (!tile) return null;
  const systems = (tile.details?.systems as any[]) ?? [];
  const risks = (tile.details?.top_risks as string[]) ?? [];
  return (
    <TileCard title="Drill" status={tile.status}>
      {systems.length ? (
        <ul className="space-y-1 text-sm">
          {systems.map((s, i) => (
            <li key={i} className="flex items-center justify-between">
              <span className="capitalize">{String(s.system).replace("_", " ")}</span>
              <span className="text-gray-600 dark:text-gray-300">
                {s.status}
                {s.first_failure_clock ? ` from ${s.first_failure_clock}` : ""}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      {risks.length ? (
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
          Run the drill below to apply fixes and compare.
        </p>
      ) : null}
    </TileCard>
  );
}
