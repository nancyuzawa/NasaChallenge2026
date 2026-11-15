"""DuckDB queries over published sensor/year/country Parquet parts."""
from pathlib import Path
import re

import duckdb
import pandas as pd

from .fire_store import grid

DAILY_SQL = """
    SELECT acq_date, sensor, COUNT(*) AS cells, SUM(n)::BIGINT AS detections
    FROM (
        SELECT acq_date, sensor, cell_x, cell_y, COUNT(*) AS n
        FROM (
            SELECT DISTINCT sensor, satellite, acq_date, acq_time,
                            latitude, longitude, cell_x, cell_y
            FROM detections WHERE {where}
        ) points
        GROUP BY acq_date, sensor, cell_x, cell_y
    ) occupied
    GROUP BY acq_date, sensor ORDER BY acq_date, sensor
"""


def parquet_files(root, start_year=None, end_year=None, countries=None):
    """Ignore CSVs, legacy exports and temporary/incomplete part filenames."""
    root = Path(root)
    paths = []
    for sensor in ("modis", "viirs"):
        for path in (root / sensor).glob("[0-9][0-9][0-9][0-9]/*/part-*.parquet"):
            if not re.fullmatch(r"part-\d+\.parquet", path.name):
                continue
            if countries is not None and path.parent.name not in countries:
                continue
            year = int(path.parent.parent.name)
            if start_year is not None and year < start_year:
                continue
            if end_year is not None and year > end_year:
                continue
            if path.is_file():
                paths.append(path)
    return sorted(paths)


def parquet_signature(root):
    result = []
    for path in parquet_files(root):
        stat = path.stat()
        result.append((str(path.resolve()), stat.st_mtime_ns, stat.st_size))
    return tuple(result)


def open_parquets(root, start_year=None, end_year=None, countries=None):
    paths = parquet_files(root, start_year, end_year, countries)
    conn = duckdb.connect(":memory:")
    try:
        if paths:
            conn.from_parquet([str(path.resolve()) for path in paths],
                              union_by_name=True, hive_partitioning=False).create_view("detections")
        else:
            # An empty requested period is empty data, never the synthetic sample.
            conn.execute("""CREATE VIEW detections AS SELECT
                NULL::VARCHAR AS sensor, NULL::VARCHAR AS satellite,
                NULL::VARCHAR AS acq_date, NULL::VARCHAR AS acq_time,
                NULL::DOUBLE AS latitude, NULL::DOUBLE AS longitude,
                NULL::VARCHAR AS confidence, NULL::DOUBLE AS frp,
                NULL::BIGINT AS cell_x, NULL::BIGINT AS cell_y,
                NULL::VARCHAR AS source_file WHERE FALSE""")
        return conn
    except BaseException:
        conn.close()
        raise


def open_sample(path):
    frame = pd.read_csv(path, dtype={"acq_time": str, "confidence": str, "satellite": str})
    frame["acq_time"] = frame.acq_time.str.zfill(4)
    cells = [grid(lat, lon) for lat, lon in zip(frame.latitude, frame.longitude)]
    frame["cell_x"] = [cell[0] for cell in cells]
    frame["cell_y"] = [cell[1] for cell in cells]
    frame["source_file"] = "synthetic_sample"
    conn = duckdb.connect(":memory:")
    conn.register("detections", frame)
    return conn


def daily_aggregation(conn, where="TRUE", params=None):
    """Deduplicate observations before counting occupied cells and detections."""
    return conn.execute(DAILY_SQL.format(where=where), params or []).fetchdf()


def export_observations(conn, period, where="TRUE", params=None, limit=100_000):
    start, end = period
    if start > end:
        raise ValueError("A data inicial deve anteceder a final.")
    params = list(params or []) + [start.isoformat(), end.isoformat()]
    selection = f"""SELECT sensor,satellite,acq_date,acq_time,latitude,longitude,
        MAX(confidence) AS confidence,MAX(frp) AS frp,MIN(source_file) AS source_file
        FROM detections WHERE ({where}) AND acq_date BETWEEN ? AND ?
        GROUP BY sensor,satellite,acq_date,acq_time,latitude,longitude"""
    # Fetch at most limit+1 rows, avoiding an unrestricted DataFrame allocation.
    frame = conn.execute(
        f"SELECT * FROM ({selection}) rows ORDER BY acq_date,acq_time LIMIT ?",
        params + [limit + 1],
    ).fetchdf()
    if len(frame) > limit:
        raise ValueError(f"Mais de {limit:,} deteccoes: reduza a regiao ou o periodo para exportar.")
    return frame.to_csv(index=False).encode("utf-8-sig")


def harmonize_monthly(daily, period):
    """MODIS reference; VIIRS ratio fitted on earlier overlap months only."""
    start, end = period
    if start > end:
        raise ValueError("A data inicial deve anteceder a final.")
    columns = ["month", "activity", "detections", "method", "calibrated"]
    daily = daily.copy()
    if daily.empty:
        return pd.DataFrame(columns=columns), daily
    daily["month"] = daily.acq_date.str[:7]
    overlap = daily[daily.acq_date < end.replace(day=1).isoformat()].pivot_table(
        index="month", columns="sensor", values="cells", aggfunc="sum")
    if "MODIS" in overlap and "VIIRS" in overlap:
        paired = overlap.dropna(subset=["MODIS", "VIIRS"])
        paired = paired[(paired.MODIS > 0) & (paired.VIIRS > 0)]
    else:
        paired = pd.DataFrame()
    factor = float((paired.MODIS / paired.VIIRS).median()) if len(paired) >= 3 else None
    selected = daily[daily.acq_date.between(start.isoformat(), end.isoformat())]
    monthly = selected.pivot_table(index="month", columns="sensor", values="cells", aggfunc="sum")
    totals = selected.groupby("month").detections.sum()
    rows = []
    for month, row in monthly.iterrows():
        modis, viirs = row.get("MODIS", float("nan")), row.get("VIIRS", float("nan"))
        reference = pd.notna(modis)
        rows.append({"month": month, "activity": float(modis if reference else viirs*(factor if factor is not None else 1)),
                     "detections": int(totals[month]), "method": "MODIS reference" if reference else "VIIRS calibrated" if factor is not None else "VIIRS provisional",
                     "calibrated": bool(reference or factor is not None)})
    result = pd.DataFrame(rows, columns=columns)
    result.attrs.update(calibration_factor=factor, overlap_months=len(paired))
    return result, daily
