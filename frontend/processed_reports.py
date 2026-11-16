"""Historical reports over observed FIRMS detections, with bounded table queries."""
from datetime import date
from functools import lru_cache
import csv
import io
import json
from pathlib import Path

import duckdb

import dashboard_data as dashboard
import processed_data as store
import reports_data as demo
import state_boundaries
from locations import REGIONS
from reports_data import ANOMALY_THRESHOLD, PAGE_SIZE, RECORD_COLUMNS, monthly_comparison


def years():
    return store.available_years() or demo.AVAILABLE_YEARS


def regions(country):
    if store.dataset_status()["demo"]:
        return list(REGIONS[country])
    return ["All regions", *sorted(state_boundaries.regions(country))]


def _selection(year, country, state, earlier=False):
    root = store.dataset_path()
    filters = dict(country=country, state=state)
    candidates = dashboard._candidates(root, filters, year)
    if not earlier:
        candidates = tuple(item for item in candidates if int(Path(item[0]).parent.parent.name) == year)
    return str(root), candidates, json.dumps(filters, sort_keys=True), dashboard._geometry_signature()


def historical_summary(year, country, state):
    if store.dataset_status()["demo"]:
        return demo.historical_summary(year, country, state)
    daily = dashboard._summary(*_selection(year, country, state, earlier=True))
    period = (date(year, 1, 1), date(year, 12, 31))
    coverage = dashboard._coverage(daily, period)
    previous_years = tuple(y for y in sorted({int(day[:4]) for day in daily.acq_date}, reverse=True)
                           if y < year and coverage and dashboard._coverage(daily, (date(y, 1, 1), date(y, 12, 31))) == coverage)

    def series(y):
        monthly = dashboard._monthly_hotspots(daily, (date(y, 1, 1), date(y, 12, 31)))
        counts = {int(row.month[5:]): int(row.detections) for row in monthly.itertuples()}
        return tuple(counts.get(month) for month in range(1, 13))

    current = series(year)
    previous = [series(y) for y in previous_years]
    average = tuple(sum(row[i] for row in previous) / len(previous) if current[i] is not None else None
                    for i in range(12)) if previous else None
    months = monthly_comparison(current, average)
    total = sum(value or 0 for value in current)
    historical_total = sum(value or 0 for value in average) if average is not None else None
    deviations = [abs(row["deviation"]) for row in months if row["deviation"] is not None]
    incidents = sorted((row for row in months if row["incident"]),
                       key=lambda row: (row["new_activity"], abs(row["deviation"] or 0)), reverse=True)
    return dict(year=year, current=current, average=average, months=months, total=total,
                historical_total=historical_total, deviation=(total / historical_total - 1) * 100 if historical_total else None,
                largest_deviation=max(deviations, default=None), incidents=incidents, previous_years=previous_years)


def _query(candidates, filter_json):
    conn = duckdb.connect(":memory:")
    try:
        conn.from_parquet([item[0] for item in candidates], union_by_name=True,
                          hive_partitioning=False).create_view("detections")
        where, params = dashboard._dashboard_spatial(conn, json.loads(filter_json))
        # Preserve categorical VIIRS confidence; do not invent a percentage or day/night.
        columns = set(conn.table("detections").columns)
        daynight = "MAX(daynight)" if "daynight" in columns else "NULL::VARCHAR"
        sql = f"""SELECT acq_date || ' ' || substr(lpad(CAST(acq_time AS VARCHAR),4,'0'),1,2)
                    || ':' || substr(lpad(CAST(acq_time AS VARCHAR),4,'0'),3,2) || ':00' AS timestamp,
                    latitude, longitude, satellite, sensor, MAX(confidence) AS confidence,
                    MAX(frp) AS frp, {daynight} AS daynight
                  FROM detections WHERE ({where}) AND acq_date BETWEEN ? AND ?
                  GROUP BY acq_date, acq_time, latitude, longitude, satellite, sensor"""
        return conn, sql, params
    except BaseException:
        conn.close()
        raise


@lru_cache(maxsize=64)
def _record_page(root, candidates, filter_json, geometry_signature, year, page, total):
    if not candidates:
        return demo.record_page((), 0)
    conn, sql, params = _query(candidates, filter_json)
    params += [f"{year}-01-01", f"{year}-12-31"]
    try:
        pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(max(0, page), pages - 1)
        offset = page * PAGE_SIZE
        rows = conn.execute(f"SELECT * FROM ({sql}) records ORDER BY timestamp DESC, latitude DESC, longitude DESC, satellite, sensor LIMIT ? OFFSET ?",
                            params + [PAGE_SIZE, offset]).fetchall()
        return dict(rows=rows, page=page, pages=pages, start=offset + 1 if rows else 0,
                    end=offset + len(rows), total=total)
    finally:
        conn.close()


def record_page(year, country, state, page):
    if store.dataset_status()["demo"]:
        return demo.record_page(demo.detection_records(year, country, state), page)
    return _record_page(*_selection(year, country, state), year, page,
                        historical_summary(year, country, state)["total"])


def records_csv(year, country, state):
    if store.dataset_status()["demo"]:
        return demo.records_csv(year, country, state)
    _, candidates, filters, _ = _selection(year, country, state)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow((*RECORD_COLUMNS, "Country", "State/Province", "Data type"))
    if candidates:
        conn, sql, params = _query(candidates, filters)
        try:
            cursor = conn.execute(f"SELECT * FROM ({sql}) records ORDER BY timestamp DESC, latitude DESC, longitude DESC, satellite, sensor",
                                  params + [f"{year}-01-01", f"{year}-12-31"])
            while rows := cursor.fetchmany(10000):
                writer.writerows((*row, country, state, "NASA FIRMS") for row in rows)
        finally:
            conn.close()
    return output.getvalue().encode("utf-8-sig")
