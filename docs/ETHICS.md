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
