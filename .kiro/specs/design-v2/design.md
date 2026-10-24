# Design: design-v2 (frontend restyle)

## Overview

A presentation-layer rebuild of the one-page app around the BU design tokens in
`.kiro/steering/design.md`. No backend or API changes. State flow is unchanged
(fetch plan + explanation, then lazy-load options/people/sponsors/trust with the
existing demo fallback).

## Token layer

`src/theme.css` defines CSS variables on `:root` and `[data-theme="dark"]` from
the steering tokens. Tailwind is kept for layout utilities, but colours come from
the variables via arbitrary values (e.g. `bg-[var(--card)]`) or small semantic
classes in `theme.css`. Fira Sans is loaded via a Google Fonts `<link>` in
`index.html`.

### Theme controller
`src/theme.ts`: `getInitialTheme()` reads `sessionStorage` then
`prefers-color-scheme`; `setTheme(t)` writes `data-theme` on `<html>` and stores
the choice for the session. A `ThemeToggle` component (sun/moon) sits in the
header.

## Component tree

```
App
  Header            (red bar, logo, title + "BU EVENT PLANNER", ThemeToggle, demo pill, New plan)
  IntakeCard        (textarea + Build plan + Brief A/B chips)
  SummaryCard       (4 columns; readiness red + status pill)
  TwoUp
    VenueCard       (stats + Show details drawer: assignments + consumption)
    GettingThereCard(stats + Show details drawer: stops/accessibility/disruptions/parking)
  BudgetCard        (row-by-row table + final total bar)
  FoodWaterCard     (real meals, open halls, check-hours, cost, lines, water)
  PeopleSponsorsCard(collapsed; judges + sponsor categories)
  OptionsCard       (collapsed; Lean/Balanced/Premium compare)
  DrillCard         (Run drill + Apply fixes & re-run; 3 system cards; DO NOW; before→after)
  TrustExportCard   (collapsed; label mix bar, privacy report, sensitivity, print/CSV)
```

Shared primitives in `src/components/ui.tsx`: `SectionCard` (red top border),
`StatusPill` (ok/strained/failing/coming-soon with icon + text), `Drawer`
(animated height+opacity, rotating arrow), `Stat` (caps label + big tabular
number + muted subline), `CountUp` (animated number), `Chip`, `PrimaryButton`,
`SecondaryButton`, `Skeleton`.

## Motion

framer-motion: a `motion.div` stagger container for page load (fade up 8px, 250ms,
60ms stagger); `AnimatePresence` height/opacity for drawers; a `CountUp` hook
(rAF, 400ms) for big numbers and the drill before→after; CSS transition (200ms)
on the root for theme colour changes. A `usePrefersReducedMotion` hook disables
movement (opacity-only) when requested.

## Budget-sum invariant

`BudgetCard` renders `plan.budget.line_items` (item/basis/p50) and the total bar
from `plan.budget.total_p*`. A frontend test (vitest) asserts
`sum(line_items.p50) === total_p50` for both demo snapshots. The basis text per
item is a small static map keyed by line-item name (purely cosmetic labels; the
numbers are all from the model).

## Data mapping (no placeholders)

- Summary: recommended_building, cost_p50 + range subline, readiness + pill,
  top_risks[0].
- Venue: measured_share, assignments, consumption bands.
- Getting there: nearest stop + disruptions + shuttle + parking.
- Food & water: the real `Food & Water` tile details (meals/halls/water).
- People/sponsors/options/trust: the `/people`, `/sponsors`, `/plan/options`,
  `/trust` payloads (with demo fallback).

## Testing

- vitest + @testing-library: budget rows sum to total (both snapshots); theme
  toggle flips `data-theme`; demo badge shows when source is demo.
- `npm run build` (tsc + vite) is clean.

## Cleanup

Remove the old `Tiles.tsx`, `SummaryBar.tsx`, `Sections.tsx`, `DrillPanel.tsx`
once their content is folded into the new card components, and drop the
blue/gray Tailwind palette usages.
