# Boston Numina street sensors

Saved 2026-10-18 for Hackachusetts.

Every published Numina count file on Analyze Boston. Each file is one sensor zone in 2020–2021. The live call returns 100 rows from zone 52112. data.csv joins all nine count files. Sensors do not cover the whole city.

Rows in data.csv: 245555

Columns: zone, metric, object, count, time

How to use it

- Spreadsheets: open data.csv in Excel or Google Sheets.
- Fresh copy: run `python fetch.py` or `node fetch.js`. Both call the URL below and save the response.
- The preview on the Hackachusetts site is a few rows of this same table.

Direct request

https://data.boston.gov/api/3/action/datastore_search?resource_id=d6c06150-418d-4705-b0c9-e92afd23ede7&fields=zone_id,metric,objClass,result,time&limit=100

Check the source license before publishing a project.
