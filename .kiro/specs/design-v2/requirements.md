# Requirements: design-v2 (frontend restyle)

## Introduction

Restyle the EventTwin frontend to match the attached BU-branded mocks
(`docs/design/eventtwin_lightmode.jpg`, `eventtwin_darkmode.jpg`) and
`.kiro/steering/design.md` exactly. This is a presentation-layer change only: no
backend behaviour or API contract changes. Implemented on branch `design-v2`.

## Requirements

### Requirement 1: Theme system
1. THE SYSTEM SHALL define the design tokens from the steering file as CSS
   variables on `:root`, with dark values under `[data-theme="dark"]`.
2. THE SYSTEM SHALL provide a light/dark toggle in the header (sun/moon icon),
   placed immediately left of the "New plan" pill.
3. THE theme SHALL default to the OS `prefers-color-scheme` and SHALL remember the
   user's explicit choice for the session.
4. THE SYSTEM SHALL load Fira Sans (400/500/600/700) with a `system-ui, sans-serif`
   fallback.
5. THE SYSTEM SHALL use framer-motion for the animations in Requirement 7.

### Requirement 2: Page order and sections
1. THE page SHALL present, top to bottom: Header; Describe your event; Summary
   card; Venue + Getting there (two-up); Budget row-by-row; Food & water; People
   & sponsors; Plan options; The drill; Trust & export.
2. Venue, Getting there each SHALL expose their existing detail (room
   assignments, Wi-Fi/power consumption, stops, accessibility, disruptions,
   parking) via a "Show details" drawer.
3. People & sponsors, Plan options, and Trust & export SHALL be collapsed by
   default.

### Requirement 3: Budget rows
1. THE budget section SHALL render whatever line items the budget model returns,
   each with item / basis / p50 cost.
2. THE line-item p50 costs SHALL sum to the final total shown (verified by a
   frontend test).
3. THE final total bar SHALL use `--final-bar` with white text, showing the p50
   and big value on the left and the range, per-attendee cost, and budget
   over/under on the right.

### Requirement 4: Real data only
1. EVERY value shown SHALL come from real API (or demo-snapshot) data; the UI
   SHALL contain no bracketed placeholders or "coming soon" text for sections
   that have real data (Food & water uses the real food plan).

### Requirement 5: Demo fallback
1. WHEN the live API fails or exceeds the 8 s timeout THE SYSTEM SHALL use the
   bundled demo snapshot AND show a grey "Demo snapshot" pill in the header.

### Requirement 6: Motion and accessibility
1. THE SYSTEM SHALL implement the motion spec (page-load stagger, skeleton →
   cross-fade, number count-up, drawer expand, drill before→after, theme
   transition, button press) from the steering file.
2. THE SYSTEM SHALL respect `prefers-reduced-motion` (opacity only, no movement).
3. Status SHALL be conveyed by colour AND text; focus rings SHALL be visible
   (2px `--red` offset); contrast SHALL meet AA in both themes; the textarea +
   button build the plan by keyboard and every drawer is keyboard-toggleable.

### Requirement 7: Responsive
1. BELOW 640px: the summary becomes 2x2, the two-up cards stack, and the budget
   table scrolls horizontally inside its card.

### Requirement 8: Cleanup
1. Unused old styles/components SHALL be removed; the build SHALL be clean with
   no console errors.
