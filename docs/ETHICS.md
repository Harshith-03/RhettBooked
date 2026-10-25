# Ethics

RhettBooked is a planning aid, not an authority. These are the standing commitments
the system is built to honor.

## Data provenance
Every number carries a label: MEASURED (from real BU/MBTA/Bluebikes data), ASSUMED
(a documented planning prior), PLACEHOLDER (illustrative, not official), or
SIMULATED (a model output). Real data always wins over placeholder data. The Trust
view and `GET /provenance` expose the label mix so no figure is taken on faith.

## Privacy
Uploaded registration data passes through the scrubber first: emails, BU IDs,
MAC/BSSID, and phone numbers are redacted, and personal data survives only as
aggregate counts with cells under five people suppressed. The scrubber's regex
detection does not catch names; NER via Presidio is the planned deepening.
Deterministic HMAC tokenization with a separate vault supports re-linking under
audit without storing raw identifiers.

## People recommendations
Judge and speaker suggestions use only public scholarly metadata (OpenAlex): name,
institution, work titles, citation counts, and topics. The system never stores
contact details and never infers gender, race, or other demographics. An
institution-diversity check keeps the list from being dominated by one place.

## Model honesty
The LLM only parses the brief and explains results; it never invents numbers. The
template and RAG explainers cite source ids and surface only figures that appear in
the tool outputs. Caveats (one month of Bluebikes data, citywide/older Numina,
placeholder rate cards, unconfirmed overnight/AV) are stated, not hidden.

## Cost realism and in-kind resources
The budget rate cards are PLACEHOLDER figures tuned for a recognised BU **student**
event, not corporate quotes. Resources BU provides at no cash charge for registered
student events — the venue room, campus Wi-Fi, building power, AV support, BUPD
coverage, and custodial — are shown as **$0, labelled "ASSUMED - BU resource (no
charge)"** (listed under `bu_in_kind` in `data/placeholder/rate_cards.yaml`). Their
in-kind nature is displayed, not silently dropped, so the lower total (~$5k–$10k for
a 300-person overnight hackathon) is explainable rather than optimistic. Catering is
the dominant cash line; prizes and swag are modest and typically sponsor-funded.

## Research-agent caterers
When live web research is unavailable (no key or rate-limited), the Food & Water card
shows a small set of **curated real** Boston-area caterers with real public links,
labelled PLACEHOLDER / "curated" — never presented as live-researched results, and
never with fabricated prices. People suggestions remain OpenAlex-only (public
scholarly metadata), with no curated-person fallback.
