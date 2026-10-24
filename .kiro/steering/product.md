# EventTwin

An event-planning digital twin for Boston University. An admin describes an event in plain language

(type, size, dates, audience, budget, needs). EventTwin produces ONE organized plan:

  1. Venue & rooms   2. Tech (Wi-Fi, data, power)   3. Food & water   4. Getting there (MBTA, Bluebikes,

  parking, late-night safety)   5. People (judges, speakers, sponsors)   6. Budget (cost range + sponsor gap)

  7. Drill (stress test on the digital twin, with fixes and re-run)

It also offers 3 plan options (Lean / Balanced / Premium) side by side.

Design rule: NOT overwhelming. Show a summary first (recommended building, cost range, readiness score,

top 3 risks), then 7 tiles, each opening into detail. Raw evidence is collapsed by default.

Judging (DS+X): Impact 25, Data Science 25, Technical 20, Design 10, Ethics 10, Presentation 10.

"Calling an LLM or API is not data science." Models produce every number; the LLM only parses the brief

and explains results.

Principles:

1. Every number is labelled MEASURED, ASSUMED, PLACEHOLDER, or SIMULATED, with its source.

2. The BU building/room data is a PLACEHOLDER dataset (names are real BU buildings; floors, rooms,

   capacities and rates are illustrative). Say so in the UI.

3. All uploaded or scraped data passes through the privacy scrubber first. Dietary and accessibility

   needs are only ever stored as aggregate counts.

4. AI is optional: everything works with LLM_PROVIDER=none (rule-based parser and templates).

5. People recommendations show only public names, institutions, topics and public profile links. No

   contact scraping, and no inferring of gender, race or other attributes.