# College Scorecard, Massachusetts

Saved 2026-10-18 for Hackachusetts.

Massachusetts institutions from the College Scorecard institution file published 15 Oct 2026. Cost, median debt, earnings 10 years after entry, and completion. PrivacySuppressed stays as published. Earnings are not causal. The live link is the national zip. data.csv is the Massachusetts slice.

Rows in data.csv: 140

Columns: unitid, name, city, control, highest_degree, admission_rate, undergraduates, net_price_public, net_price_private, cost, in_state_tuition, median_debt, earnings_10yr, completion_4yr, completion_under_4yr

How to use it

- Spreadsheets: open data.csv in Excel or Google Sheets.
- Fresh copy: run `python fetch.py` or `node fetch.js`. Both call the URL below and save the response.
- The preview on the Hackachusetts site is a few rows of this same table.

Direct request

https://ed-public-download.scorecard.network/downloads/Most-Recent-Cohorts-Institution_10152026.zip

Check the source license before publishing a project.
