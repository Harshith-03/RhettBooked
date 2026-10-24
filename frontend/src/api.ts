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

export { API_URL };
