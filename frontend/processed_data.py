"""Parquet analysis used only by Dashboard and Activity; Reports keeps its adapter."""
from datetime import date
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pyarrow as pa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from src.firms_analysis import parquet_files, parquet_signature, open_parquets, daily_aggregation, harmonize_monthly
import data as demo

DEFAULT_FILTERS = dict(country="Brazil", state="São Paulo", city="Campinas", latitude=-22.9064, longitude=-47.0616)


def dataset_path():
    return Path(os.environ.get("FIREWATCH_DATA") or ROOT / "backend/data/processed").expanduser().resolve()


def dataset_status():
    count = len(parquet_files(dataset_path()))
    return dict(demo=not count, files=count, path=str(dataset_path()),
                label="Synthetic demo data" if not count else "NASA FIRMS · Parquet / DuckDB")


def available_years():
    return tuple(sorted({int(p.parent.parent.name) for p in parquet_files(dataset_path())}, reverse=True))


@lru_cache(maxsize=1)
def _countries():
    content = json.loads((ROOT / "frontend/components/globe/countries.json").read_text(encoding="utf-8"))
    return {f["properties"]["name"]: f["geometry"] for f in content["features"]}


def _ring(lon, lat, ring):
    inside = False
    for a, b in zip(ring, ring[1:] + ring[:1]):
        if (a[1] > lat) != (b[1] > lat) and lon < (b[0]-a[0])*(lat-a[1])/(b[1]-a[1])+a[0]:
            inside = not inside
    return inside


def _contains(geometry, lat, lon):
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    return int(any(_ring(lon,lat,p[0]) and not any(_ring(lon,lat,h) for h in p[1:]) for p in polygons))


def _contains_many(geometry, lat, lon):
    """Same ray-casting/boundary convention as _contains, in NumPy batches."""
    def ring_mask(ring, y, x):
        inside = np.zeros(len(y), dtype=bool)
        for a,b in zip(ring,ring[1:]+ring[:1]):
            if a[1] == b[1]:
                continue
            crossing = (a[1] > y) != (b[1] > y)
            inside ^= crossing & (x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])
        return inside
    result = np.zeros(len(lat), dtype=bool)
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    for polygon in polygons:
        outer = polygon[0]
        xs,ys = zip(*[(p[0],p[1]) for p in outer])
        indices = np.flatnonzero((lon>=min(xs)) & (lon<=max(xs)) & (lat>=min(ys)) & (lat<=max(ys)) & ~result)
        if not len(indices):
            continue
        y,x = lat[indices],lon[indices]
        mask = ring_mask(outer,y,x)
        for hole in polygon[1:]:
            mask &= ~ring_mask(hole,y,x)
        result[indices] |= mask
    return result.astype(np.int32)


def _spatial(conn, filters):
    if filters.get("bounds"):
        south, west, north, east = filters["bounds"]
        return "latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?", [south,north,west,east]
    if filters.get("city") or filters.get("state", "All regions") != "All regions" or filters.get("scope") == "radius":
        lat, lon = float(filters.get("latitude", -22.9064)), float(filters.get("longitude", -47.0616))
        radius = float(filters.get("radius_km", 100))
        if radius <= 0:
            raise ValueError("Radius must be positive.")
        delta = radius / 110.5
        # Evaluate radius arithmetic inside DuckDB, without per-row Python calls.
        where = """latitude BETWEEN ? AND ? AND
            12742.0176 * asin(sqrt(least(1.0,
                pow(sin(radians(latitude-?)/2),2) +
                cos(radians(latitude))*cos(radians(?))*pow(sin(radians(longitude-?)/2),2)
            ))) <= ?"""
        return where, [max(-90,lat-delta),min(90,lat+delta),lat,lat,lon,radius]
    geometry = _countries().get(filters.get("country", "Brazil"))
    if geometry is None:
        raise ValueError("Country geometry is unavailable.")
    conn.create_function("in_country",
        lambda lat,lon: pa.array(_contains_many(geometry,lat.to_numpy(),lon.to_numpy())),
        ["DOUBLE","DOUBLE"], "INTEGER", type="arrow")
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    points = [point for polygon in polygons for point in polygon[0]]
    return "latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ? AND in_country(latitude,longitude)=1", [min(p[1] for p in points),max(p[1] for p in points),min(p[0] for p in points),max(p[0] for p in points)]


@lru_cache(maxsize=32)
def _daily(root, signature, filter_json):
    conn = open_parquets(root)
    try:
        where, params = _spatial(conn, json.loads(filter_json))
        return daily_aggregation(conn, where, params)
    finally:
        conn.close()


def daily_data(filters=None, sensors=None):
    filters = dict(DEFAULT_FILTERS if filters is None else filters)
    filters.pop("period", None)
    if not filters.get("bounds") and not filters.get("city") and filters.get("state", "All regions") == "All regions" and filters.get("scope") != "radius":
        # Coordinates inherited from an earlier city do not affect a country query.
        filters = {"country": filters.get("country", "Brazil"), "state": "All regions"}
    result = _daily(str(dataset_path()), parquet_signature(dataset_path()), json.dumps(filters, sort_keys=True)).copy()
    if sensors is not None:
        result = result[result.sensor.isin(sensors)].copy()
    return result


def monthly_analysis(period, filters=None, sensors=None):
    return harmonize_monthly(daily_data(filters, sensors), period)


def dashboard_series(period, filters=None):
    if dataset_status()["demo"]:
        return demo.dashboard_series(period, filters)
    monthly, _ = monthly_analysis(period, filters)
    values = [None]*12
    for row in monthly.itertuples():
        index = int(row.month[5:])-1
        values[index] = (values[index] or 0) + row.activity
    return values


def dashboard_metrics(period, filters=None):
    if dataset_status()["demo"]:
        return demo.dashboard_metrics(period, filters)
    start, end = period
    monthly, daily = monthly_analysis(period, filters)
    prior = []
    for year in sorted({int(day[:4]) for day in daily.acq_date if int(day[:4]) < start.year}):
        try:
            earlier = (start.replace(year=year), end.replace(year=year + end.year-start.year))
        except ValueError:
            continue
        baseline, _ = harmonize_monthly(daily, earlier)
        if not baseline.empty and baseline.calibrated.all() and set(baseline.month.str[5:]) == set(monthly.month.str[5:]):
            prior.append(float(baseline.activity.sum()))
    current = float(monthly.activity.sum()) if not monthly.empty else None
    historical = float(np.mean(prior)) if prior else None
    change = (current/historical-1)*100 if current is not None and historical and monthly.calibrated.all() else None
    peak = monthly.loc[monthly.activity.idxmax()] if not monthly.empty else None
    return dict(hotspots=int(monthly.detections.sum()), growth=None,
                peak_month=str(peak["month"]) if peak is not None else "—",
                peak_count=float(peak.activity) if peak is not None else None,
                historical_growth=round(change,1) if change is not None else None,
                current_period=current, historical_average=historical,
                calibrated=bool(not monthly.empty and monthly.calibrated.all()))
