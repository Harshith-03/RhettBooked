// Bundled demo snapshots used as an offline fallback when the live API is
// unavailable or slow. Regenerate with: python -m backend.scripts.export_demo

import type { BriefKey, DrillCompare, DrillResult, Plan } from "../types";

import aParse from "./briefA/parse.json";
import aPlan from "./briefA/plan.json";
import aDrill from "./briefA/drill.json";
import aDrillFixes from "./briefA/drill_fixes.json";
import aOptions from "./briefA/options.json";
import aPeople from "./briefA/people.json";
import aSponsors from "./briefA/sponsors.json";
import aTrust from "./briefA/trust.json";

import bParse from "./briefB/parse.json";
import bPlan from "./briefB/plan.json";
import bDrill from "./briefB/drill.json";
import bDrillFixes from "./briefB/drill_fixes.json";
import bOptions from "./briefB/options.json";
import bPeople from "./briefB/people.json";
import bSponsors from "./briefB/sponsors.json";
import bTrust from "./briefB/trust.json";

interface DemoBundle {
  parse: unknown;
  plan: Plan;
  drill: DrillResult;
  drillFixes: DrillCompare;
  options: any;
  people: any;
  sponsors: any;
  trust: any;
}

export const DEMO: Record<BriefKey, DemoBundle> = {
  briefA: {
    parse: aParse,
    plan: aPlan as unknown as Plan,
    drill: aDrill as unknown as DrillResult,
    drillFixes: aDrillFixes as unknown as DrillCompare,
    options: aOptions,
    people: aPeople,
    sponsors: aSponsors,
    trust: aTrust,
  },
  briefB: {
    parse: bParse,
    plan: bPlan as unknown as Plan,
    drill: bDrill as unknown as DrillResult,
    drillFixes: bDrillFixes as unknown as DrillCompare,
    options: bOptions,
    people: bPeople,
    sponsors: bSponsors,
    trust: bTrust,
  },
};

export const BRIEF_TEXT: Record<BriefKey, string> = {
  briefA:
    "300-person overnight AI hackathon at BU, Oct 24-25, students, budget $15k, needs lunch, dinner, midnight snack, breakfast",
  briefB:
    "300-person overnight AI hackathon at BU, Oct 31-Nov 1, 2026, students, budget $15k, needs lunch, dinner, midnight snack, breakfast",
};

// Pick the closest demo bundle for a given free-text brief (used when the live
// API fails on a custom brief): Brief B if the text mentions the Oct 31 window.
export function demoKeyForText(text: string): BriefKey {
  const t = text.toLowerCase();
  if (t.includes("oct 31") || t.includes("nov 1") || t.includes("31-nov")) {
    return "briefB";
  }
  return "briefA";
}
