"""Publish bounded parts under sensor/year/country, preserving provenance."""
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
import hashlib
import os
import re
import unicodedata

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

LAYOUT_VERSION = 2
COLUMNS = ["sensor", "satellite", "acq_date", "acq_time", "latitude", "longitude",
           "confidence", "frp", "cell_x", "cell_y", "source_file"]
SCHEMA = pa.schema([
    (name, pa.float64() if name in ("latitude", "longitude", "frp") else
     pa.int64() if name in ("cell_x", "cell_y") else pa.string())
    for name in COLUMNS
])


def source_id(source_key):
    return hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:20]


def country_from_source(source_key):
    """Prefer a ZIP member's FIRMS name, then its directories, then the archive."""
    for source in reversed(source_key.replace("\\", "/").split("::")):
        path = PurePosixPath(source)
        match = re.match(
            r"^(?:modis|viirs[^_]*)_\d{4}_(.+?)\.(?:csv(?:\.gz|\.zip)?|zip)$",
            path.name, re.IGNORECASE,
        )
        country = match.group(1) if match else None
        if country is None:
            for index, part in enumerate(path.parts[:-1]):
                if re.fullmatch(r"\d{4}", part) and index + 1 < len(path.parts) - 1:
                    country = path.parts[index + 1]
                    break
        if country:
            text = unicodedata.normalize("NFKD", country).encode("ascii", "ignore").decode()
            return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "unknown"
    return "unknown"


def _register_sources(conn, sources):
    with conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS export_sources (
            sensor TEXT NOT NULL, year INTEGER NOT NULL, source_key TEXT NOT NULL,
            country TEXT NOT NULL, PRIMARY KEY(sensor, year, source_key))""")
        conn.execute("""CREATE INDEX IF NOT EXISTS export_country
                        ON export_sources(sensor, year, country)""")
        conn.executemany("INSERT OR REPLACE INTO export_sources VALUES (?, ?, ?, ?)",
                         [(sensor.upper(), year, key, country_from_source(key))
                          for sensor, key, year in sources])


def _export_country(conn, output_dir, sensor, year, country, batch_size, source_keys=None):
    folder = Path(output_dir) / sensor.lower() / str(year) / country
    folder.mkdir(parents=True, exist_ok=True)
    selection = ", ".join("d." + name for name in COLUMNS)
    if source_keys is None:
        source_selection = """SELECT source_key FROM export_sources
                              WHERE sensor = ? AND year = ? AND country = ?"""
        source_params = (sensor.upper(), year, country)
    else:
        source_selection = ", ".join("?" for _ in source_keys)
        source_params = tuple(source_keys)
    cursor = conn.execute(
        f"""SELECT {selection} FROM detections d
            WHERE d.sensor = ? AND d.acq_date >= ? AND d.acq_date < ?
              AND d.source_file IN ({source_selection})
            ORDER BY d.acq_date, d.acq_time, d.source_file,
                     d.satellite, d.latitude, d.longitude""",
        (sensor.upper(), f"{year}-01-01", f"{year + 1}-01-01", *source_params),
    )
    total, pending = 0, []
    try:
        index = 0
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            index += 1
            stem = f"part-{index:03d}"
            frame = pd.DataFrame.from_records(rows, columns=COLUMNS)
            parquet, csv = folder / f"{stem}.parquet", folder / f"{stem}.csv"
            parquet_tmp, csv_tmp = folder / f".{stem}.parquet.tmp", folder / f".{stem}.csv.tmp"
            pending.extend([(parquet_tmp, parquet), (csv_tmp, csv)])
            pq.write_table(pa.Table.from_pandas(frame, schema=SCHEMA, preserve_index=False),
                           parquet_tmp, compression="zstd")
            frame.to_csv(csv_tmp, index=False, encoding="utf-8")
            total += len(rows)
        # Publish only after every part has been written successfully.
        for temporary, target in pending:
            os.replace(temporary, target)
        expected = {target.name for _, target in pending}
        for path in folder.iterdir():
            if re.fullmatch(r"part-\d+\.(?:parquet|csv)", path.name) and path.name not in expected:
                path.unlink()
        # Remove obsolete temporary parts from an interrupted larger export.
        for path in folder.iterdir():
            if re.fullmatch(r"\.part-\d+\.(?:parquet|csv)\.tmp", path.name):
                path.unlink()
        return total
    finally:
        cursor.close()
        for temporary, _ in pending:
            temporary.unlink(missing_ok=True)


def _remove_legacy_exports(output_dir, sensor, year, source_keys):
    folder = Path(output_dir) / sensor.lower() / f"year={year}"
    for key in source_keys:
        for extension in ("csv", "parquet"):
            (folder / f"part-{source_id(key)}.{extension}").unlink(missing_ok=True)
    if folder.is_dir() and not any(folder.iterdir()):
        folder.rmdir()


def export_source(sqlite_conn, output_dir, sensor, year, source_key, batch_size=50_000):
    """Rebuild the country's parts, including other registered sources in it."""
    if batch_size <= 0:
        raise ValueError("batch_size precisa ser positivo.")
    country = country_from_source(source_key)
    _register_sources(sqlite_conn, [(sensor, source_key, year)])
    total = _export_country(sqlite_conn, output_dir, sensor, year, country, batch_size)
    _remove_legacy_exports(output_dir, sensor, year, [source_key])
    return total


def export_existing(sqlite_conn, output_dir, start_year=2020, end_year=2025, match=None):
    """Reorganize existing SQLite data without reading raw files."""
    # Read one consistent snapshot without changing schema or journal mode.
    owns_transaction = not sqlite_conn.in_transaction
    if owns_transaction:
        sqlite_conn.execute("BEGIN")
    try:
        sources = sqlite_conn.execute(
            """SELECT DISTINCT sensor, source_file, CAST(substr(acq_date, 1, 4) AS INTEGER)
               FROM detections WHERE acq_date >= ? AND acq_date < ?""",
            (f"{start_year}-01-01", f"{end_year + 1}-01-01"),
        ).fetchall()
        groups = {}
        for sensor, key, year in sources:
            groups.setdefault((sensor, year, country_from_source(key)), []).append(key)
        published = 0
        for (sensor, year, country), keys in sorted(groups.items()):
            if match and not any(fnmatch(key.split("::")[0].split("/")[-1], match) for key in keys):
                continue
            print(f"[exportando] {sensor.lower()}/{year}/{country}", flush=True)
            total = _export_country(sqlite_conn, output_dir, sensor, year, country, 50_000,
                                    source_keys=keys)
            _remove_legacy_exports(output_dir, sensor, year, keys)
            published += 1
            print(f"[exportado] {sensor.lower()}/{year}/{country}: {total:,} registros", flush=True)
        if not published:
            print("Nenhum dado processado encontrado para o periodo/filtro informado. "
                  "Para ler os arquivos de raw, execute sem --export-only.", flush=True)
        return published
    finally:
        if owns_transaction:
            sqlite_conn.rollback()
