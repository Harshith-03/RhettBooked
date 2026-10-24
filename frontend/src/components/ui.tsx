import { useState, type ReactNode } from "react";

// Status is conveyed with BOTH colour AND text (accessibility).
const STATUS_STYLES: Record<string, string> = {
  ok: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  strained: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  failing: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

export function StatusPill({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-200";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>
      {status}
    </span>
  );
}

export function Badge({ children, tone = "gray" }: { children: ReactNode; tone?: "gray" | "amber" | "blue" }) {
  const tones: Record<string, string> = {
    gray: "bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-200",
    amber: "bg-amber-200 text-amber-900 dark:bg-amber-800 dark:text-amber-100",
    blue: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800 ${className}`}
    >
      {children}
    </div>
  );
}

// A tile with a one-line status and an expandable details drawer.
export function TileCard({
  title,
  status,
  statusTone,
  children,
}: {
  title: string;
  status: string;
  statusTone?: string;
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Card>
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">{status}</p>
        </div>
        {statusTone ? <StatusPill status={statusTone} /> : null}
      </div>
      {children ? (
        <button
          onClick={() => setOpen((v) => !v)}
          className="mt-3 text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
          aria-expanded={open}
        >
          {open ? "Hide details" : "Show details"}
        </button>
      ) : null}
      {open ? <div className="mt-3 border-t border-gray-100 pt-3 dark:border-gray-700">{children}</div> : null}
    </Card>
  );
}

export function money(n: number): string {
  return `$${Math.round(n).toLocaleString()}`;
}
