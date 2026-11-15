# Firewatch frontend

Python and Streamlit prototype with Welcome, Map, Activity, and Reports pages. The interface is in English.

## Run locally

From the project root:

```powershell
python run.py
```

On Windows, you can also double-click `iniciar.cmd`. The launcher creates
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
necessary. Running `frontend/app.py` directly also uses the project launcher.

## Navigation and filters

The entry page follows `midias/prototype/0.Welcome.png`: choose a country
and press **Confirm**. Home is the entry page; the sidebar contains only
Map, Activity, and Reports.

The dashboard follows `midias/prototype/1. Dashboard.png`, initially
showing January through December 2025. **Search** selects a reference city;
**Filter** provides country, state/province, coordinates, and date controls.
**Reset** restores Campinas and 2025. All selectors support text search and
partial name matching. **Location**, next to Filter, stays synchronized
with the globe. Drag to rotate; click a country or city to update the
location while preserving the date interval. The catalog is local and
does not include every city. Activity and Reports share this location.

## Activity calendar and satellite sources

The second menu item follows `midias/prototype/2. Report.png`: daily
heatmap, legend, searchable month/year controls, annual comparison, peak
periods, and yearly summaries. Calendar month/year and annual comparison
year/range controls are independent.

The **MODIS** and **VIIRS** pills filter the entire Activity page:

- No selection: both sources combined.
- One selected source: only that source.
- Both selected: both sources combined.

The calendar, legend, annual chart, peak periods, growth, and yearly totals
all reflect the selected sources. Clearing the selection restores combined
data without changing location or date controls.

All data is synthetic. The 2023-2025 scenarios derive from 2025 city
samples. MODIS/VIIRS assignments are simulated, not satellite measurements.
Source counts add up exactly to each day's combined total; daily counts
match monthly and yearly sums. Earlier years are not historical
observations. Rules are in `activity_data.py`, markup in `activity_ui.py`,
and styles in `activity.css`.

The floating location button follows
`midias/prototype/Components/Button.png`: it expands on hover or keyboard
focus, and returns to the map with the location preserved.

## Data and layout

Dashboard samples in `data.py` are synthetic and limited to 2025. Country
totals aggregate available cities; they are not national estimates.
Dates outside 2025 and areas without samples show zero. The backend API
is not connected yet.

See `components/globe/README.md` for map assets, geographic sources, and
licensing. Shared styles are in `styles.css`. Panels adapt to the window;
narrow screens place the map above the indicators. All calendar days stay
inside their panel when resizing. The sidebar uses `midias/logo/Logo.svg`.
Requires Streamlit 1.67+ layout features.

Run tests from the project root:

```powershell
frontend\.venv\Scripts\python.exe -m unittest discover -s frontend/tests -v
```
