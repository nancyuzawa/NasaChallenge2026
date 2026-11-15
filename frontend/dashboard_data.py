"""Dashboard-specific file pruning and reusable daily aggregate summaries."""
from datetime import date
from calendar import month_name
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import tempfile

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import processed_data as store
import state_boundaries
from src.firms_analysis import parquet_files, daily_aggregation

CACHE_VERSION = 2
DAILY_COLUMNS = ["acq_date", "sensor", "cells", "detections"]


@lru_cache(maxsize=8192)
def _file_bounds(path, size, mtime):
    # Missing statistics never exclude a file. Only metadata is read here.
    with pq.ParquetFile(path) as file:
        meta = file.metadata
        columns = {name: i for i,name in enumerate(meta.schema.names)}
        if not {"latitude", "longitude"}.issubset(columns):
            return None
        if meta.num_row_groups == 0:
            return None
        ranges = {}
        for name in ("latitude", "longitude"):
            statistics = [meta.row_group(i).column(columns[name]).statistics
                          for i in range(meta.num_row_groups)]
            if any(item is None or not item.has_min_max for item in statistics):
                return None
            low = min(float(item.min) for item in statistics)
            high = max(float(item.max) for item in statistics)
            if not np.isfinite([low,high]).all():
                return None
            ranges[name] = low,high
        return (*ranges["latitude"], *ranges["longitude"])


def _geometry_signature():
    paths=[store.ROOT/'frontend/components/globe/countries.json',state_boundaries.PATH]
    return tuple((p.stat().st_size,p.stat().st_mtime_ns) for p in paths)


def _dashboard_spatial(conn,filters):
    if state_boundaries.selected(filters) and not filters.get('bounds') and filters.get('scope') != 'radius':
        shape=state_boundaries.geometry(filters.get('country','Brazil'),filters['state'])
        if shape is None:
            return 'FALSE',[]
        south,north,west,east=state_boundaries.bounds(shape)
        conn.create_function('in_state',lambda lat,lon: pa.array(store._contains_many(shape,lat.to_numpy(),lon.to_numpy())),
                             ['DOUBLE','DOUBLE'],'INTEGER',type='arrow')
        return 'latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ? AND in_state(latitude,longitude)=1',[south,north,west,east]
    return store._spatial(conn,filters)


def _region_bounds(filters):
    if state_boundaries.selected(filters) and not filters.get('bounds') and filters.get('scope') != 'radius':
        shape=state_boundaries.geometry(filters.get('country','Brazil'),filters['state'])
        return state_boundaries.bounds(shape) if shape is not None else (91,90,181,180)
    if filters.get("bounds"):
        south,west,north,east = filters["bounds"]
        return south,north,west,east
    if filters.get("city") or filters.get("state", "All regions") != "All regions" or filters.get("scope") == "radius":
        lat = float(filters.get("latitude", -22.9064))
        delta = float(filters.get("radius_km",100))/110.5
        # Longitude stays unrestricted, including radii across the antimeridian.
        return max(-90,lat-delta),min(90,lat+delta),-180,180
    geometry = store._countries().get(filters.get("country", "Brazil"))
    if geometry is None:
        raise ValueError("Country geometry is unavailable.")
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    points = [point for polygon in polygons for point in polygon[0]]
    return min(p[1] for p in points),max(p[1] for p in points),min(p[0] for p in points),max(p[0] for p in points)


def _candidates(root, filters, end_year):
    south,north,west,east = _region_bounds(filters)
    selected = []
    # Earlier years are retained for calibration and historical comparisons.
    for path in parquet_files(root,end_year=end_year):
        stat = path.stat()
        signature = (str(path.resolve()),stat.st_size,stat.st_mtime_ns)
        bounds = _file_bounds(*signature)
        if bounds is not None:
            lo_lat,hi_lat,lo_lon,hi_lon = bounds
            if hi_lat < south or lo_lat > north or hi_lon < west or lo_lon > east:
                continue
        selected.append(signature)
    return tuple(selected)


@lru_cache(maxsize=64)
def _summary(root, candidates, filter_json, geometry_signature):
    payload = repr((CACHE_VERSION,root,candidates,filter_json,geometry_signature)).encode()
    key = hashlib.sha256(payload).hexdigest()
    folder = Path(root) / ".dashboard_cache"
    target = folder / f"{key}.parquet"
    try:
        frame = pd.read_parquet(target)
        if list(frame.columns) == DAILY_COLUMNS:
            return frame
    except (OSError,pa.ArrowException):
        pass
    if not candidates:
        return pd.DataFrame(columns=DAILY_COLUMNS)
    conn = duckdb.connect(":memory:")
    try:
        conn.from_parquet([item[0] for item in candidates],union_by_name=True,
                          hive_partitioning=False).create_view("detections")
        where,params = _dashboard_spatial(conn,json.loads(filter_json))
        frame = daily_aggregation(conn,where,params)
    finally:
        conn.close()
    # A read-only deployment can still use the in-memory summary cache.
    temporary = None
    try:
        folder.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder,suffix=".tmp",delete=False) as stream:
            temporary = Path(stream.name)
        frame.to_parquet(temporary,index=False)
        os.replace(temporary,target)
    except OSError:
        pass
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return frame


def load_dashboard(period, filters=None):
    start,end = period
    if start > end:
        raise ValueError("The start date must precede the end date.")
    root = store.dataset_path()
    files = parquet_files(root)
    status = dict(demo=not files,files=len(files),path=str(root),
                  label="NASA FIRMS · Parquet / DuckDB" if files else "Synthetic demo data")
    if not files:
        return store.demo.dashboard_metrics(period,filters),store.demo.dashboard_series(period,filters),status
    filters = dict(store.DEFAULT_FILTERS if filters is None else filters)
    filters.pop("period",None)
    if not filters.get("bounds") and not filters.get("city") and filters.get("state","All regions") == "All regions" and filters.get("scope") != "radius":
        filters = dict(country=filters.get("country","Brazil"),state="All regions")
    signature = _geometry_signature()
    candidates = _candidates(root,filters,end.year)
    daily = _summary(str(root),candidates,json.dumps(filters,sort_keys=True),signature).copy()
    monthly = _monthly_hotspots(daily,period)
    values = [None]*12
    for row in monthly.itertuples():
        index = int(row.month[5:])-1
        values[index] = (values[index] or 0)+int(row.detections)
    metrics = _metrics(period,daily,monthly)
    return metrics,values,status


def _monthly_hotspots(daily,period):
    selected=daily[daily.acq_date.between(period[0].isoformat(),period[1].isoformat())].copy()
    selected["month"]=selected.acq_date.str[:7]
    return selected.groupby("month",as_index=False).detections.sum()


def _coverage(daily,period):
    selected=daily[daily.acq_date.between(period[0].isoformat(),period[1].isoformat())]
    # Do not compare years where a sensor or observed month is missing.
    return set(zip(selected.acq_date.str[5:7],selected.sensor))


def _metrics(period,daily,monthly):
    start,end=period
    total=int(monthly.detections.sum())
    coverage=_coverage(daily,period)
    prior=[]
    previous=None
    for year in sorted({int(day[:4]) for day in daily.acq_date if int(day[:4]) < start.year}):
        try:
            earlier=(start.replace(year=year),end.replace(year=year+end.year-start.year))
        except ValueError:
            continue
        if not coverage or _coverage(daily,earlier) != coverage:
            continue
        baseline=_monthly_hotspots(daily,earlier)
        count=int(baseline.detections.sum())
        if count:
            prior.append(count)
            if year == start.year-1:
                previous=count
    historical=float(np.mean(prior)) if prior else None
    change=(total/historical-1)*100 if historical else None
    peak=monthly.loc[monthly.detections.idxmax()] if not monthly.empty else None
    peak_label=month_name[int(peak["month"][5:])] if peak is not None else "—"
    if peak is not None and start.year != end.year:
        peak_label += " " + peak["month"][:4]
    return dict(hotspots=total,growth=round((total/previous-1)*100,1) if previous else None,
                peak_month=peak_label,peak_count=int(peak.detections) if peak is not None else None,
                historical_growth=round(change,1) if change is not None else None,
                current_period=total if not monthly.empty else None,historical_average=historical)


@lru_cache(maxsize=32)
def _map_points(root,candidates,selection_json,period,limit,geometry_signature):
    key=hashlib.sha256(repr((CACHE_VERSION,"map",root,candidates,selection_json,period,limit,geometry_signature)).encode()).hexdigest()
    folder=Path(root)/".dashboard_cache"
    target=folder/f"points-{key}.parquet"
    try:
        return pd.read_parquet(target)
    except (OSError,pa.ArrowException):
        pass
    columns=["sensor","latitude","longitude","total_locations"]
    if not candidates:
        return pd.DataFrame(columns=columns)
    conn=duckdb.connect(':memory:')
    try:
        conn.from_parquet([item[0] for item in candidates],union_by_name=True,hive_partitioning=False).create_view('detections')
        where,params=_dashboard_spatial(conn,json.loads(selection_json))
        frame=conn.execute(f"""WITH locations AS (
            SELECT DISTINCT sensor,latitude,longitude FROM detections
            WHERE ({where}) AND acq_date BETWEEN ? AND ? AND sensor IN ('MODIS','VIIRS')
        ) SELECT sensor,latitude,longitude,COUNT(*) OVER (PARTITION BY sensor) AS total_locations
          FROM locations
          QUALIFY ROW_NUMBER() OVER (PARTITION BY sensor ORDER BY hash(latitude,longitude),latitude,longitude) <= ?
          ORDER BY sensor,latitude,longitude""",params+[period[0],period[1],limit]).fetchdf()
    finally:
        conn.close()
    temporary=None
    try:
        folder.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder,suffix='.tmp',delete=False) as stream:
            temporary=Path(stream.name)
        frame.to_parquet(temporary,index=False)
        os.replace(temporary,target)
    except OSError:
        pass
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return frame


def load_hotspots(period,filters,limit_per_sensor=5000):
    if limit_per_sensor <= 0:
        raise ValueError("Map point limit must be positive.")
    if period[0] > period[1]:
        raise ValueError("The start date must precede the end date.")
    root=store.dataset_path()
    country=filters.get('country','Brazil')
    selection=dict(country=country,state=filters.get('state') or 'All regions')
    candidates=tuple(item for item in _candidates(root,selection,period[1].year)
                     if int(Path(item[0]).parent.parent.name) >= period[0].year)
    frame=_map_points(str(root),candidates,json.dumps(selection,sort_keys=True),tuple(d.isoformat() for d in period),
                      limit_per_sensor,_geometry_signature())
    total=int(frame.groupby('sensor').total_locations.max().sum()) if not frame.empty else 0
    points=frame[['sensor','latitude','longitude']].to_dict('records')
    return dict(points=points,total=total,shown=len(points),limited=len(points)<total,
                country=country,state=selection['state'],
                boundary_available=not state_boundaries.selected(selection) or state_boundaries.geometry(country,selection['state']) is not None,
                start=period[0].isoformat(),end=period[1].isoformat())


@lru_cache(maxsize=64)
def _available_regions(root,candidates,country,period,geometry_signature):
    if not candidates:
        return {}
    key=hashlib.sha256(repr((CACHE_VERSION,'regions',root,candidates,country,period,geometry_signature)).encode()).hexdigest()
    folder=Path(root)/'.dashboard_cache'
    target=folder/f'regions-{key}.json'
    try:
        return json.loads(target.read_text(encoding='utf-8'))
    except (OSError,ValueError):
        pass
    found={}
    conn=duckdb.connect(':memory:')
    try:
        conn.from_parquet([item[0] for item in candidates],union_by_name=True,hive_partitioning=False).create_view('detections')
        for name,shape in sorted(state_boundaries.regions(country).items()):
            south,north,west,east=state_boundaries.bounds(shape)
            conn.create_function('region_has_focus',
                lambda lat,lon: pa.array(store._contains_many(shape,lat.to_numpy(),lon.to_numpy())),
                ['DOUBLE','DOUBLE'],'INTEGER',type='arrow')
            try:
                exists=conn.execute("""SELECT 1 FROM detections
                    WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?
                      AND acq_date BETWEEN ? AND ? AND sensor IN ('MODIS','VIIRS')
                      AND region_has_focus(latitude,longitude)=1 LIMIT 1""",
                    [south,north,west,east,*period]).fetchall()
            finally:
                conn.remove_function('region_has_focus')
            if exists:
                found[name]=((south+north)/2,(west+east)/2)
    finally:
        conn.close()
    temporary=None
    try:
        folder.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder,suffix='.tmp',mode='w',encoding='utf-8',delete=False) as stream:
            temporary=Path(stream.name)
            json.dump(found,stream,ensure_ascii=False)
        os.replace(temporary,target)
    except OSError:
        pass
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return found


def available_regions(country,period):
    if period[0]>period[1]:
        return {}
    root=store.dataset_path()
    selection=dict(country=country,state='All regions')
    candidates=tuple(item for item in _candidates(root,selection,period[1].year)
                     if int(Path(item[0]).parent.parent.name)>=period[0].year)
    return _available_regions(str(root),candidates,country,tuple(d.isoformat() for d in period),_geometry_signature()).copy()
