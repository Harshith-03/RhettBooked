// API client with an 8-second timeout and a bundled-demo fallback.
//
// The backend base URL comes from import.meta.env.VITE_API_URL (default
// http://localhost:8000). No URLs are hard-coded. If a request fails or takes
// longer than 8 s, the matching saved demo snapshot is returned and the result
// is tagged source: "demo" so the UI can show a "Demo snapshot" badge.

import { DEMO, demoKeyForText } from "./demo";
import type {
  BriefKey,
  DrillCompare,
  DrillResult,
  Fetched,
  Plan,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TIMEOUT_MS = 8000;

async function post<T>(path: string, body: unknown): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

// Resolve which demo bundle to use: an explicit example key, else infer from text.
function demoBundle(briefKey: BriefKey | null, text: string) {
  return DEMO[briefKey ?? demoKeyForText(text)];
}

export async function fetchPlan(
  text: string,
  briefKey: BriefKey | null
): Promise<Fetched<Plan>> {
  try {
    const data = await post<Plan>("/plan", { text, draws: 500 });
    return { data, source: "live" };
  } catch {
    return { data: demoBundle(briefKey, text).plan, source: "demo" };
  }
}

export async function fetchDrill(
  text: string,
  briefKey: BriefKey | null
): Promise<Fetched<DrillResult>> {
  try {
    const data = await post<DrillResult>("/drill/run", { text });
    return { data, source: "live" };
  } catch {
    return { data: demoBundle(briefKey, text).drill, source: "demo" };
  }
}

export async function fetchExplanation(
  text: string,
  briefKey: BriefKey | null
): Promise<Fetched<string>> {
  try {
    const data = await post<{ explanation: string }>("/explain", { text, draws: 500 });
    return { data: data.explanation, source: "live" };
  } catch {
    // Derive a short grounded sentence from the demo plan summary.
    const s = demoBundle(briefKey, text).plan.summary;
    const risks = s.top_risks.length ? ` Top risks: ${s.top_risks.join("; ")}.` : "";
    return {
      data:
        `Recommended venue: ${s.recommended_building}. ` +
        `Estimated cost $${s.cost_p10.toLocaleString()} to $${s.cost_p90.toLocaleString()} ` +
        `(p50 $${s.cost_p50.toLocaleString()}). Drill readiness: ${s.readiness}/100.${risks}`,
      source: "demo",
    };
  }
}

export async function fetchDrillCompare(
  text: string,
  briefKey: BriefKey | null,
  appliedFixes: Record<string, unknown>
): Promise<Fetched<DrillCompare>> {
  try {
    const data = await post<DrillCompare>("/drill/compare", {
      text,
      applied_fixes: appliedFixes,
    });
    return { data, source: "live" };
  } catch {
    return { data: demoBundle(briefKey, text).drillFixes, source: "demo" };
  }
}

export async function fetchExtra(
  kind: "plan/options" | "people" | "sponsors" | "trust",
  text: string,
  briefKey: BriefKey | null
): Promise<Fetched<any>> {
  const demoField = kind === "plan/options" ? "options" : kind;
  try {
    const data = await post<any>(`/${kind}`, { text, draws: 500 });
    return { data, source: "live" };
  } catch {
    return { data: (demoBundle(briefKey, text) as any)[demoField], source: "demo" };
  }
}

// Run a research job: start it, poll /agent/jobs/{id}, stream steps via onStep.
// On any failure (no backend, no key path still returns via backend; network
// error here) falls back to the bundled agent demo snapshot's result.
export async function runResearch(
  task: "catering" | "people",
  text: string,
  briefKey: BriefKey | null,
  onStep: (steps: string[]) => void
): Promise<Fetched<any>> {
  const demoField = task === "catering" ? "agentCatering" : "agentPeople";
  try {
    const start = await post<{ job_id: string }>("/agent/research", { text, task });
    const jobId = start.job_id;
    for (let i = 0; i < 120; i++) {
      const res = await fetch(`${API_URL}/agent/jobs/${jobId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const job = await res.json();
      onStep(job.steps ?? []);
      if (job.status === "done") return { data: job.result, source: "live" };
      if (job.status === "error") throw new Error(job.error ?? "job error");
      await new Promise((r) => setTimeout(r, 500));
    }
    throw new Error("job timed out");
  } catch {
    const demo = (demoBundle(briefKey, text) as any)[demoField];
    // The demo snapshot is the full job dict ({status, steps, result}).
    onStep(demo?.steps ?? ["Loaded demo snapshot"]);
    return { data: demo?.result ?? null, source: "demo" };
  }
}

export { API_URL };
