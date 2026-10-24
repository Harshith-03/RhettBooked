// Shared response shapes (a loose subset of the backend payloads the UI reads).

export interface ProvenanceRow {
  output_key: string;
  label: "MEASURED" | "ASSUMED" | "PLACEHOLDER" | "SIMULATED";
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
