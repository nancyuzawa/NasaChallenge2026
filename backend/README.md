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

Import local FIRMS downloads from the project root:

```powershell
python backend/scripts/import_firms.py --start-year 2006 --end-year 2006
```

The importer recursively finds `sensor_YEAR_country.csv` files under
`backend/data/raw`, including nested extraction folders such as `modis/2006/2006`.
It writes CSV chunks to `backend/data/processed/<sensor>/<year>/<country>/`,
preserving input columns and adding `sensor` and `source_file`. Acquisition times
are padded to four digits. It validates coordinates, dates, and times; it does
not compute spatial grid cells or generate Parquet files. Existing country
directories are skipped to preserve previously processed data.

Use `--dry-run` to list inputs without writing, `--chunk-size` to change the
100,000-row chunk size, or `--raw-dir` / `--output-dir` to use other directories.
The script uses only Python's standard library and does not download data.

