# MBTA service alerts

Saved 2026-10-18 for Hackachusetts.

The live call returns the 50 most recent alerts as JSON. data.csv is a flat table of alerts saved on the snapshot date.

Rows in data.csv: 130

Columns: updated, effect, severity, routes, header

How to use it

- Spreadsheets: open data.csv in Excel or Google Sheets.
- Fresh copy: run `python fetch.py` or `node fetch.js`. Both call the URL below and save the response.
- The preview on the Hackachusetts site is a few rows of this same table.

Direct request

https://api-v3.mbta.com/alerts?page%5Blimit%5D=50

Check the source license before publishing a project.
