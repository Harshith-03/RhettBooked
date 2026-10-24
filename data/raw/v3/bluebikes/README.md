# Bluebikes station-to-station counts, November 2024

Saved 2026-10-18 for Hackachusetts.

Every trip in the official November 2024 Bluebikes file, aggregated to a start station and an end station. member_trips and casual_trips use the file's member_casual field. The live link is the month zip of individual trips. data.csv is the station-pair counts so the starter stays small.

Rows in data.csv: 63063

Columns: start_station, end_station, trips, member_trips, casual_trips

How to use it

- Spreadsheets: open data.csv in Excel or Google Sheets.
- Fresh copy: run `python fetch.py` or `node fetch.js`. Both call the URL below and save the response.
- The preview on the Hackachusetts site is a few rows of this same table.

Direct request

https://s3.amazonaws.com/hubway-data/202411-bluebikes-tripdata.zip

Check the source license before publishing a project.
