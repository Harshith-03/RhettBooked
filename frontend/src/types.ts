// Shared response shapes (a loose subset of the backend payloads the UI reads).

export interface ProvenanceRow {
  output_key: string;
  label: "MEASURED" | "ASSUMED" | "PLACEHOLDER" | "SIMULATED" | "RESEARCHED";
  source: string;
  value_summary: string;
}

export interface Summary {
  recommended_building: string | null;
  cost_p10: number;
  cost_p50: number;
  cost_p90: number;
  cost_per_attendee: number;
  sponsorship_gap: number;
  turnout_p50: number;
  turnout_p90: number;
  readiness: number | null;
  top_risks: string[];
}

export interface Tile {
  name: string;
  status: string;
  details: Record<string, unknown>;
  action_items: string[];
}

export interface Plan {
  summary: Summary;
  venue: Record<string, unknown>;
  budget: {
    total_p10: number;
    total_p50: number;
    total_p90: number;
    cost_per_attendee: number;
    sponsorship_gap: number;
    line_items: { name: string; p10: number; p50: number; p90: number }[];
  };
  attendance: Record<string, unknown>;
  tiles: Tile[];
  provenance: ProvenanceRow[];
}

export interface DrillSystem {
  system: string;
  status: "ok" | "strained" | "failing";
  first_failure_clock: string | null;
  note: string;
  fixes: Record<string, string>;
}

export interface DrillResult {
  readiness: number;
  worst_status: string;
  systems: DrillSystem[];
  top_risks: string[];
  fixes: { do_now: string[]; plan_for: string[]; improve_later: string[] };
  disruptions: string[];
  planned_disruptions: {
    lines: string[];
    start_date: string | null;
    end_date: string | null;
    shuttle_note: string | null;
    fare_free: boolean;
    label: string;
  }[];
}

export interface DrillCompare {
  before: { readiness: number; worst_status: string; top_risks: string[] };
  after: { readiness: number; worst_status: string; top_risks: string[] };
  improved: boolean;
}

export type BriefKey = "briefA" | "briefB";

// Whether a response came from the live API or a bundled demo snapshot.
export type Source = "live" | "demo";

export interface Fetched<T> {
  data: T;
  source: Source;
}

// --- Research agent (agent-research spec) ---
export interface Caterer {
  name: string;
  address: string;
  distance_m: number;
  cuisine: string;
  price_per_head_low: number | null;
  price_per_head_high: number | null;
  price_note: string;
  dietary: string[];
  catering_url: string;
  why_fits: string;
  verification: "VERIFIED" | "WEB_ONLY" | "CURATED";
  source_urls: string[];
}

export interface LineItem {
  name: string;
  p10: number;
  p50: number;
  p90: number;
}

// A Lean/Balanced/Premium plan option from /plan/options (enriched with the
// per-tier line-item breakdown so the Compare columns differ by budget + menu).
export interface PlanOption {
  name: string;
  tier: "lean" | "balanced" | "premium";
  total_p10: number;
  total_p50: number;
  total_p90: number;
  cost_per_attendee: number;
  sponsorship_gap: number;
  tradeoffs: string;
  line_items: LineItem[];
  budget_usd: number | null;
}

export interface OptionsResponse {
  options: PlanOption[];
}

export interface CateringResult {
  label: string;
  meals: { meal: string; caterers: Caterer[] }[];
  verified_count: number;
  researched_per_head: { low: number; high: number; n: number } | null;
  fallback_reason: string | null;
}

export interface ResearchPerson {
  name: string;
  role: string;
  organization: string;
  profile_url: string;
  relevance: string;
  source_urls: string[];
  research_data: boolean;
  note: string;
}

export interface PeopleResearchResult {
  label: string;
  judges: ResearchPerson[];
  speakers: ResearchPerson[];
  sponsors: ResearchPerson[];
  fallback_reason: string | null;
}

export interface AgentJob {
  job_id: string;
  task: "catering" | "people";
  status: "running" | "done" | "error";
  steps: string[];
  result: CateringResult | PeopleResearchResult | null;
  error: string | null;
}
