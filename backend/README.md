| Directory | Responsibility |
| --- | --- |
| `api/routes` | Receive requests from the frontend |
| `services` | Run processing and business rules |
| `models` | Represent system entities and, eventually, database tables |
| `schemas` | Define API request and response formats |
| `database` | Manage connections and persistence |
| `core` | Configuration and environment variables |
| `data/raw` | Original files |
| `data/processed` | Standardized and harmonized data |
| `data/aggregated` | Consolidated data for analysis |

## Import local data

From the project root:

```powershell
python run.py --check
frontend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
frontend/.venv/Scripts/python.exe backend/scripts/import_firms.py --chunk-size 100000
python run.py
```

Place CSV, CSV.GZ, or ZIP files in `backend/data/raw/modis/` and
`backend/data/raw/viirs/`, using any year/country directory organization.
To start with real data for Brazil in 2020, using the prepared environment:

```powershell
frontend/.venv/Scripts/python.exe backend/scripts/import_firms.py --match '*Brazil*.csv' --start-year 2020 --end-year 2020
python run.py
```

If the main database is busy with another import, create a separate database:

```powershell
frontend/.venv/Scripts/python.exe backend/scripts/import_firms.py --match '*Brazil*.csv' --start-year 2020 --end-year 2020 --output backend/data/processed/brazil-2020
$env:FIREWATCH_DATA = (Resolve-Path 'backend/data/processed/brazil-2020').Path
python run.py
```

To extend the separate database above through 2025, keep the output argument:

```powershell
frontend/.venv/Scripts/python.exe backend/scripts/import_firms.py --match '*Brazil*.csv' --start-year 2020 --end-year 2025 --output backend/data/processed/brazil-2020
```

Processing visits years in order for both sensors. The outputs are:

```text
backend/data/processed/
  firewatch.sqlite
  modis/2020/brazil/part-001.parquet
  modis/2020/brazil/part-002.parquet
  modis/2020/argentina/part-001.parquet
  modis/2021/brazil/part-001.parquet
  viirs/2020/brazil/part-001.parquet
```

Each country/year contains parts numbered from `part-001`, with up to 50,000
records per part. Matching CSVs are saved alongside the Parquets.
The country is extracted from the FIRMS name, such as `modis_2020_Brazil.csv`
or `viirs-jpss1_2020_Argentina.csv`, including CSVs inside ZIP files.
A country directory in `sensor/year/country/file.csv` is also recognized.
Directory names are lowercase, without accents, with underscores between words;
sources without an identifiable country go into `unknown`. This stage does
not classify countries by coordinates: use sources separated by country.
Sources for the same sensor/year/country share the part sequence, preserving
`source_file`. When a source is updated, the partition is rebuilt and excess
old parts are removed. Temporary files are written before publication;
an interruption during replacement is recovered on the next run.

To import local files and generate the structure above, run from the project root:

```powershell
frontend/.venv/Scripts/python.exe backend/scripts/import_firms.py --start-year 2020 --end-year 2025
```

The script displays the absolute output directory and period before starting.
Directories are created as each source/year finishes; empty directories are not
created in advance. The `firewatch.sqlite` index stays at the root of `processed`
for import checkpoints.

To reorganize an existing processed database without rereading raw CSVs:

```powershell
frontend/.venv/Scripts/python.exe backend/scripts/import_firms.py --export-only --start-year 2020 --end-year 2025
```

`--export-only` queries only records already in SQLite; it does not import
`raw`. A message is displayed if no records exist for the requested period.
This mode opens the database read-only, without changing the journal or creating
tables. If it is locked, the script asks you to wait for the other process and retry.

Use `--output` to select another database, such as `backend/data/processed/brazil-2020`.
Old exports in `year=2020` are removed only after the corresponding parts have
been published in the new layout. Old checkpoints are also updated automatically
when the normal import is repeated.

The frontend queries Parquets with DuckDB without opening raw CSVs.
SQLite is used for importer staging and checkpoints. As soon as a source/year
finishes and publishes its parts, its records become available: refresh the page
and select a period/region with data. The import can continue in another terminal.
The cache considers the path, size, and mtime of each published Parquet part.

If interrupted, repeat the command. Completed sources/years are skipped;
the source/year in progress resumes from the last committed batch. The reader
still has to scan earlier batches in compressed CSVs, but does not insert them again.
If `--chunk-size` changes during a resume, only the incomplete source/year restarts.
A file containing multiple years is read once for each requested year. Prefer annual
files to reduce reading. The year in the path/name is used as a filter: keep it
consistent with the contents; files without a year in their path are checked for each year.

Intermediate data and checkpoints are persisted in SQLite. A changed source/year
is prepared in staging; its previous version remains available until a transactional
swap. If export fails after that swap, the next run retries only the pending
publication. CSV and Parquet files are replaced individually; the export checkpoint
is committed after both.
The importer migrates the existing index schema without deleting previous data.
Old indexes without annual checkpoints are revalidated on the first import.
The legacy `sources` table records the latest run per source; annual checkpoints
and reports are stored in `ingestion_years`. The legacy `daily` table is not
updated: the interface aggregates detections directly from Parquets through DuckDB.

Normalization validates coordinates, dates, and UTC times. Low confidence is preserved.
Duplicates within a source are ignored; overlapping sources retain their provenance,
and the interface deduplicates by sensor, satellite, date, time, latitude, and longitude.
Files with unchanged size and modification time are treated as identical; if you replace
a file while preserving both, change its mtime to force an update.
Sources removed from `raw` remain in the database. To generate an independent database,
use `--output` and configure `FIREWATCH_DATA` in the frontend. Do not run two importers
against the same database at the same time.

This script processes local files; it does not download NASA data. Resuming avoids
reprocessing completed years, and downloaded files remain in `raw`.
Automatic retrieval through the FIRMS API is not included in this version.

## DuckDB analysis and frontend integration

`src/firms_analysis.py` opens Parquets published in
`processed/{modis,viirs}/YYYY/country/part-NNN.parquet` as an in-memory DuckDB view.
No persistent DuckDB database or additional processing of `raw` is required.
CSV files, temporary files, and old `year=YYYY` directories are ignored.
Direct reading uses the API documented in [DuckDB: Parquet](https://duckdb.org/docs/stable/data/parquet/overview).

The query flow is: Parquets -> DuckDB (filters, deduplication, daily aggregation)
-> monthly harmonization in the backend -> small DataFrames for Streamlit.
Detections are deduplicated across parts before occupied cells are counted.
Country, radius, and rectangle filters apply to the original points;
the country directory name does not replace geographic selection.
The region's full history feeds calibration and the baseline.
Detection exports select the years in the requested period and limit output to 100,000 rows.

From the project root, to open the frontend using existing Parquets:

```powershell
$env:FIREWATCH_DATA = (Resolve-Path 'backend/data/processed').Path
python run.py
```

`python run.py` installs declared dependencies, including DuckDB, when necessary.
Without configuration, the default directory is `backend/data/processed`.
Use `FIREWATCH_DATA` to select the Parquet directory.
The current adapter ignores `FIREWATCH_DB`; SQLite is used by the importer.
Without published Parquet parts, the interface identifies its data as synthetic.
If parts exist but there is no data for the region/period, results remain empty;
synthetic samples do not replace those results.
Refresh the page after new parts are published to invalidate the cache.

## Git and deployment without large files

Git ignores `backend/data/raw/`, the local SQLite database, and the Dashboard cache.
Parquets and CSVs in `backend/data/processed/` can be tracked under the current
configuration; check `git status` before publishing large files.
The small sample in `data/sample/hotspots.csv` is **synthetic** and versioned.
To host the application with real data, transfer the Parquet directories through
external storage or a persistent volume, preserving sensor/year/country, and configure
`FIREWATCH_DATA`. The analysis server needs the Parquets; the checkpoint SQLite
database and raw CSVs can remain on the import machine.

## Method and limitations

1. Cylindrical equal-area grid: authalic radius 6371007.181 m,
   standard parallel of 30 degrees, cells measuring 1000 x 1000 m.
2. Aggregation into occupied cells per UTC day and sensor reduces multiple pixels
   and passes, but does not identify independent fire events.
3. For each region and month, MODIS is the reference when records exist.
   Otherwise, VIIRS is multiplied by the median monthly MODIS/VIIRS ratio
   from at least three months preceding the evaluation month.
   Without sufficient overlap, VIIRS remains provisional and no anomaly is calculated.
4. The series displays **equivalent cell-days**, keeping the original detection
   count separate. Do not mix these units.
5. The historical mean uses the same month/days in previous years, excludes
   the evaluated year, and includes only years with comparable records.
   Gaps are not zeros. The annual peak uses only the selected interval.

Without coverage metadata, a month with few records may reflect incomplete data.
The adjustment does not correct for clouds, orbital geometry, or sensitivity;
it does not guarantee MODIS-VIIRS continuity and requires scientific validation
before operational use. Regional ratios may hide seasonal and spatial variation.
No confirmed incidents or reports from field teams are available.

Countries use simplified map polygons; cities and states use a configurable radius
around the reference point, explicitly identified in the UI.
The manual rectangle defines geographic boundaries independently of the country.
Spatial selection applies to original coordinates before grid aggregation.

Queries run locally using DuckDB over Parquet, with cache invalidation based on
path/mtime/size. Regional history is aggregated once per region/database change;
temporal filters operate on that aggregate. The first query of global areas
can still be expensive. Detection CSVs have an explicit limit of 100,000 rows
per download to protect server memory; the monthly summary is separate.
Visualizations can be exported as self-contained HTML or PNG through Plotly.

Official references:

- https://firms.modaps.eosdis.nasa.gov/
- https://firms.modaps.eosdis.nasa.gov/map/
- https://firms.modaps.eosdis.nasa.gov/content/active_fire/

## Verification

```powershell
frontend/.venv/Scripts/python.exe -m unittest discover -s backend/tests
frontend/.venv/Scripts/python.exe -m unittest discover -s frontend/tests
```
