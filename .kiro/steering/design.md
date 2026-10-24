# EventTwin design system (from docs/design/light.png and dark.png)

Feel: clean, calm, editorial, BU-branded. Smooth, subtle motion. Never flashy.

## Tokens (CSS variables on :root; dark values under [data-theme="dark"])

Light: --bg #F7F6F3, --card #FFFFFF, --card-alt #F7F6F3 (zebra rows), --border #E6E3DE,

--text #1A1A1A, --muted #6B6B6B, --red #CC0000, --red-hover #A30000, --red-soft #FCE8E8,

--ok-bg #E3F4E6, --ok-text #1E7A34, --warn-bg #F6D58E, --warn-text #5A3E00,

--final-bar #1A1A1A (dark total bar in light mode).

Dark: --bg #141414, --card #1E1E1E, --card-alt #252525, --border #2E2E2E, --text #F2F2F2,

--muted #A3A3A3, --red #CC0000, --red-text #FF6B6B (red text on dark), --final-bar #CC0000

(the total bar turns red in dark mode).

## Type

Fira Sans (Google Fonts; weights 400/500/600/700, fallback system-ui, sans-serif).

Small labels: 10-11px, uppercase, letter-spacing 0.08em, --muted.

Card title 17px/600. Big numbers 28-32px/700 with tabular-nums. Body 14px.

## Layout

Max content width 800px, centered, 24px page padding, 16px gaps between cards.

Header: a full-width bar in --red (light mode) / #1E1E1E with a 3px red bottom border (dark mode),

the logo in a white circle, "EventTwin" in bold white with "BU EVENT PLANNER" in tiny caps below,

and an outlined pill "New plan" on the right.

Cards: --card background, 1px --border, radius 12px, padding 20px. Section cards have a 3px --red top

border (rounded with the card).

Summary card: 4 columns (Recommended venue | Final cost (p50) | Readiness | Top risk), each with a tiny

caps label, a big value and a muted subline. Readiness value in red with a status pill.

Two-up row: Venue + Getting there side by side (stack on mobile), each with 2-3 stat columns and a

red "Show details →" link.

Budget table: header row with a red 2px bottom rule, zebra rows, right-aligned costs, then the final

total bar (--final-bar background, white text): label + big p50 on the left; range, per-attendee

cost and the budget over/under line on the right.

## Components

Status pills (small, rounded-full, 11px/600): ok = --ok-bg/--ok-text with "✓ ok"; strained =

--warn-bg/--warn-text with "! strained"; failing = solid --red with white "× failing";

coming soon = grey.

Primary button: solid --red, white text, radius 8px. Secondary: outlined (border --text in light,

white in dark). Chips: outlined pills.

## Motion (smooth, subtle; framer-motion)

- Page load: cards fade up 8px, 250 ms ease-out, staggered 60 ms.

- Building a plan: show skeleton shimmer cards, then cross-fade to the content.

- Numbers count up (400 ms) when a plan arrives or changes.

- "Show details" expands inline with a height + opacity animation (220 ms), and the arrow rotates.

- Drill: "Apply fixes & re-run" animates the readiness before→after (count up + pill colour change).

- Theme toggle: colours transition over 200 ms.

- Buttons/chips: 120 ms hover/press (slight darken, scale 0.98 on press).

- Respect prefers-reduced-motion: disable movement and keep only opacity changes.

## Accessibility

Status is always colour AND text. Visible focus rings (2px --red offset). AA contrast in both themes.

Keyboard: Enter on the textarea + button builds the plan; every drawer is toggleable by keyboard.
