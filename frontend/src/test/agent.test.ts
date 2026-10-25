import { describe, expect, it } from "vitest";
import { DEMO } from "../demo";
import type { BriefKey } from "../types";

// The agent demo snapshots are full job dicts {status, steps, result}. These
// tests assert the shape the research UI relies on, and the guardrail-visible
// invariant that every rendered caterer carries at least one source URL.
describe("agent demo snapshots", () => {
  (["briefA", "briefB"] as BriefKey[]).forEach((key) => {
    const bundle = DEMO[key] as any;

    it(`${key}: catering snapshot has a result with meals`, () => {
      const result = bundle.agentCatering.result;
      expect(result).toBeTruthy();
      expect(Array.isArray(result.meals)).toBe(true);
      // Fallback (no key) uses the ASSUMED label; live would be RESEARCHED.
      expect(["ASSUMED", "RESEARCHED"]).toContain(result.label);
    });

    it(`${key}: every shown caterer cites a source`, () => {
      const result = bundle.agentCatering.result;
      for (const m of result.meals) {
        for (const c of m.caterers) {
          expect(c.source_urls.length).toBeGreaterThan(0);
          expect(["VERIFIED", "WEB_ONLY"]).toContain(c.verification);
        }
      }
    });

    it(`${key}: people snapshot has judges/speakers/sponsors arrays`, () => {
      const result = bundle.agentPeople.result;
      expect(Array.isArray(result.judges)).toBe(true);
      expect(Array.isArray(result.speakers)).toBe(true);
      expect(Array.isArray(result.sponsors)).toBe(true);
      // OpenAlex judges are real and present even with no key.
      expect(result.judges.length).toBeGreaterThan(0);
      for (const j of result.judges) {
        expect(j.note).toContain("Contact through official channels.");
      }
    });

    it(`${key}: steps are human-readable progress`, () => {
      expect(bundle.agentCatering.steps.length).toBeGreaterThan(0);
    });
  });
});
