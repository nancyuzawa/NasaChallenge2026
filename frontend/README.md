# Firewatch frontend

Python and Streamlit prototype with Welcome, Map, Activity, and Reports pages. The interface is in English.

## Run locally

From the project root:

```powershell
python run.py
```

The launcher creates
`frontend/.venv` if needed, installs `requirements.txt`, and starts Streamlit
with that environment's Python. No environment activation or PowerShell
execution policy changes are needed. Installation uses trusted Windows
certificates to validate HTTPS.

Use `python run.py --check` to verify imports and dependency compatibility
without starting the application. Run the launcher again after changing
`requirements.txt`, or use `python run.py --install` to explicitly reinstall.
Declare every external frontend dependency in that file.

## VS Code

Open the `NasaChallenge2026` root folder. Press F5 with the existing
`Firewatch: iniciar Streamlit` configuration. Select
`frontend/.venv/Scripts/python.exe` in **Python: Select Interpreter** if
necessary. Running `frontend/app.py` or any script under `frontend/pages/`
directly with Python also uses the project launcher and opens the complete
application from Welcome. Navigate to Map, Activity, or Reports using the
sidebar. The page files are `1_Dashboard.py`, `2_Activity.py`, and `3_Reports.py`.

## Navigation and filters

The entry page follows `midias/prototype/0.Welcome.png`: choose a country
and press **Confirm**. Home is the entry page; the sidebar contains only
Map, Activity, and Reports.

The dashboard follows `midias/prototype/1. Dashboard.png`, initially
showing January through December 2025. **Filter** provides country,
state/province, coordinates, and date controls. The pin badge on the right
shows the country selected on the map.
**Reset** restores Campinas and 2025. All selectors support text search and
partial name matching. Opening a selector clears its search text; leaving
without choosing another option restores the committed selection.
Drag to rotate; click a country or city to update the
location while preserving the date interval. The catalog is local and
does not include every city. Activity and Reports share this location.

## Activity calendar and satellite sources

The second menu item follows `midias/prototype/2. Report.png`: daily
heatmap, legend, searchable month/year controls, annual comparison, peak
periods, and yearly summaries. Calendar month/year and annual comparison
year/range controls are independent.

The calendar has plain month labels, with its legend aligned beside the
sensor and period controls, as in `midias/prototype/2. Report.png`.
Select a specific month to display its centered heatmap and the
**See more details** button at the bottom right, as in
`midias/prototype/2.a. Calendar - Month.png`. The button opens **Month Details**
for the selected month and year. The details screen shows daily bars, the monthly
total, the share of the annual total, and change from the previous month
(including December of the previous year when available). Month/year and
sensor controls update these values. Confidence is unavailable in the demo
dataset. **Back** restores the calendar and comparison controls, preserving
the location and current sensor selection.

The **MODIS** and **VIIRS** pills filter the entire Activity page:

- No selection: both sources combined.
- One selected source: only that source.
- Both selected: both sources combined.

The calendar, legend, annual chart, peak periods, growth, and yearly totals
all reflect the selected sources. Clearing the selection restores combined
data without changing location or date controls.

In demo mode (without published Parquets), data is synthetic. The 2023-2025 scenarios derive from 2025 city
samples. MODIS/VIIRS assignments are simulated, not satellite measurements.
Source counts add up exactly to each day's combined total; daily counts
match monthly and yearly sums. Earlier years are not historical
observations. Rules are in `activity_data.py`, markup in `activity_ui.py`,
and styles in `activity.css`.

The floating location button follows
`midias/prototype/Components/Button.png`: black background, bold white location
text on the left, and an outlined pin on the right. Activity and Month Details
initially show only the pin; hovering or keyboard focus slides the name into view
to the left. The label includes the city and full region name when available,
followed by the country. The button returns to the map with the location preserved.
The map's country badge uses the same colors, icon placement and 12px corner
radius, with the country always visible. Long labels are truncated to fit the
viewport; the tooltip contains the full name. Reduced motion preferences disable
the slide animation.

## Data and layout

### Historical Analysis (Reports)

Reports implements `midias/prototype/4. Historical comparison and identification of anomalies.png`
and its `4.a` and `4.b` variants. Use the side arrows or the three dots to switch
between historical indicators, anomaly identification with a monthly chart, and
the detection record. The record shows ten rows per page, newest first.
**Export all data** downloads every detection in the current selection as CSV,
including rows beyond the visible page. The CSV identifies its data as synthetic.

Country and state initially follow the map. Reports then retains its own filters;
changing the map's administrative area initializes them again. Reports aggregates
all catalog cities in the selected state or country, without restricting the
sample to the map's current city or coordinates. Available years are 2023–2025.
Changing country, state or year resets record pagination and updates every slide
and the export together.

The historical baseline is the monthly mean of available years strictly before
the selected year. Anomalies are monthly deviations of at least 20% in either
direction; activity against a zero baseline is identified as new activity without
a percentage. The largest deviation is the largest absolute monthly percentage.
2023 has no earlier baseline and shows N/A. Empty areas show no records.
The synthetic historical series currently differ only by annual scale, so their
anomalies mostly have the same direction and similar percentages.

Records preserve the Activity dataset's daily, monthly, yearly and MODIS/VIIRS
counts per city. Times are simulated within each day (UTC), and coordinates are
city centers. Satellite, confidence, radiative power and day/night are unavailable
and shown as N/A, with empty CSV fields. These are demonstration records, not
satellite observations. Logic is in `reports_data.py`, rendering in `reports_ui.py`
and `pages/3_Reports.py`, and styling in `reports.css`.

Dashboard samples in `data.py` are synthetic and limited to 2025. Country
totals aggregate available cities; they are not national estimates.
In demo mode, dates outside 2025 and areas without samples show zero.
With published Parquets, Dashboard, Activity, and Reports use the local Python
analysis code in `backend/src`; no separate backend API server is required.

See `components/globe/README.md` for map assets, geographic sources, and
licensing. Shared styles are in `styles.css`. Panels adapt to the window;
narrow screens place the map above the indicators. All calendar days stay
inside their panel when resizing. The sidebar uses `midias/logo/Logo.svg`.
Requires Streamlit 1.67+ layout features.

Run tests from the project root:

```powershell
frontend\.venv\Scripts\python.exe -m unittest discover -s frontend/tests -v
```


## DuckDB in Dashboard and Activity

The `/Dashboard` and `/Activity` pages query Parquets published in
`backend/data/processed/{modis,viirs}/year/country/part-NNN.parquet`.
The `processed_data.py` and `processed_activity.py` adapters use
`backend/src/firms_analysis.py`. Reports queries Parquets through
`processed_reports.py` and `dashboard_data.py`. The synthetic data
descriptions above refer to demo mode.
Queries neither import nor modify files in `raw`.

```powershell
$env:FIREWATCH_DATA = (Resolve-Path 'backend/data/processed').Path
python run.py
```

The variable is optional when using the default directory. The launcher installs
DuckDB and pandas according to `requirements.txt`. Dashboard displays the total
original detection count and the harmonized activity series in cell-days; Activity
uses cell-days in the calendar, annual comparison, and monthly details. A selected
sensor uses its own cells. In the calendar and monthly details, selecting both
adds the two sensors' cell-days for each day, including overlapping months.
The annual comparison uses MODIS as the reference and adjusts VIIRS when three
previous overlapping months are available. Otherwise, VIIRS remains provisional.
Sources are deduplicated before aggregation. Days and months without observations
remain missing (gray in the calendar), because missing records do not prove zero fire.
The annual comparison omits percentages without comparable coverage/calibration.

Activity's year list comes from the published directories. The cache is invalidated
by part path, size, and mtime; refresh the page after new publications.
Without published Parquets, these two pages use the identified demo mode.
With Parquets, selections without records remain empty and do not use synthetic data.

### Dashboard: summaries and loading

Dashboard uses `dashboard_data.py` to select files based on Parquet latitude/longitude
statistics and skip years after the end of the selection.
Earlier years remain available for calibration and historical comparison.
Files without statistics remain in the query, and the exact geographic filter
still applies to the points. Country directories do not replace that filter.

The selection's daily aggregate is reused in memory and saved in
`processed/.dashboard_cache/`, outside observation partitions. The key includes
relevant files, size, mtime, filters, and geometry; changes invalidate the summary.
The first query must generate the summary, and subsequent queries can reuse it,
including after restarting the application. Read-only storage still allows
the in-memory cache. Summaries are disposable and do not need to be versioned.
A spinner with elapsed time is displayed while Dashboard data loads.
This optimization does not change the Activity or Reports adapter.

### Dashboard indicator units

The cards on the right and Dashboard's monthly chart use **hotspots**:
deduplicated detection counts, summed across sensors per day/month.
The peak shows the month name and count in the same unit. Changes and historical
means use these counts and remain unavailable when there are no years with
the same observed months and sensors. This check does not prove complete coverage;
indicators rely on available records. Hotspots do not represent independent fires.
Activity's annual comparison retains the harmonized cell-day series;
the calendar and monthly details sum cell-days from the selected sensors.
