import type { Summary } from "../types";
import { Card, money } from "./ui";

function readinessTone(r: number | null): string {
  if (r === null) return "strained";
  if (r >= 80) return "ok";
  if (r >= 50) return "strained";
  return "failing";
}

export function SummaryBar({ summary }: { summary: Summary }) {
  return (
    <Card className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Metric label="Recommended venue" value={summary.recommended_building ?? "-"} />
      <Metric
        label="Cost (p10 - p90)"
        value={`${money(summary.cost_p10)} - ${money(summary.cost_p90)}`}
        sub={`p50 ${money(summary.cost_p50)} - ${money(summary.cost_per_attendee)}/attendee`}
      />
      <Metric
        label="Readiness"
        value={summary.readiness === null ? "-" : `${summary.readiness}/100`}
        tone={readinessTone(summary.readiness)}
      />
      <div>
        <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Top 3 risks</p>
        {summary.top_risks.length ? (
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-sm text-gray-800 dark:text-gray-200">
            {summary.top_risks.slice(0, 3).map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">None flagged</p>
        )}
      </div>
    </Card>
  );
}

function Metric({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: string;
}) {
  const toneColor =
    tone === "ok"
      ? "text-green-700 dark:text-green-300"
      : tone === "failing"
        ? "text-red-700 dark:text-red-300"
        : tone === "strained"
          ? "text-amber-700 dark:text-amber-300"
          : "text-gray-900 dark:text-gray-100";
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${toneColor}`}>{value}</p>
      {sub ? <p className="text-xs text-gray-500 dark:text-gray-400">{sub}</p> : null}
    </div>
  );
}
