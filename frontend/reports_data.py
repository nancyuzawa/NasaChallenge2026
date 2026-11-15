"""Historical comparisons and detection records from the shared synthetic samples."""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
import csv
import io

from activity_data import AVAILABLE_YEARS, MONTH_NAMES, annual_series, daily_activity
from locations import CITY_RECORDS


ANOMALY_THRESHOLD = 20.0
PAGE_SIZE = 10
RECORD_COLUMNS = (
    "Date and Time (UTC)", "Latitude", "Longitude", "Satellite", "Sensor",
    "Confidence (%)", "Radiative Power (MW)", "Daytime/Nighttime",
)


def area_cities(country, state):
    """Aggregate the catalog's cities in the entire selected administrative area."""
    return [city for city in CITY_RECORDS if city["country"] == country
            and (state == "All regions" or city["state"] == state)]


@lru_cache(maxsize=32)
def area_series(year, country, state):
    values = [0] * 12
    if year not in AVAILABLE_YEARS:
        raise ValueError("No demonstration data for this year.")
    for city in area_cities(country, state):
        values = [a + b for a, b in zip(values, annual_series(year, city))]
    return tuple(values)


def monthly_comparison(current, historical, threshold=ANOMALY_THRESHOLD):
    """Zero baselines have no percentage; new activity is still an incident."""
    rows = []
    for month, value in enumerate(current, 1):
        average = historical[month - 1] if historical is not None else None
        deviation = (value / average - 1) * 100 if average else None
        new_activity = average == 0 and value > 0
        incident = new_activity or (deviation is not None and abs(deviation) >= threshold)
        rows.append({"month": month, "name": MONTH_NAMES[month - 1], "current": value,
                     "average": average, "deviation": deviation, "incident": incident,
                     "new_activity": new_activity})
    return rows


def historical_summary(year, country, state):
    current = area_series(year, country, state)
    previous_years = tuple(y for y in AVAILABLE_YEARS if y < year)
    previous = [area_series(y, country, state) for y in previous_years]
    average = tuple(sum(values) / len(previous) for values in zip(*previous)) if previous else None
    months = monthly_comparison(current, average)
    total = sum(current)
    historical_total = sum(average) if average is not None else None
    deviation = (total / historical_total - 1) * 100 if historical_total else None
    deviations = [abs(row["deviation"]) for row in months if row["deviation"] is not None]
    incidents = sorted((row for row in months if row["incident"]),
                       key=lambda row: (row["new_activity"], abs(row["deviation"] or 0)), reverse=True)
    return {"year": year, "current": current, "average": average, "months": months,
            "total": total, "historical_total": historical_total, "deviation": deviation,
            "largest_deviation": max(deviations, default=None),
            "incidents": incidents, "previous_years": previous_years}


@lru_cache(maxsize=8)
def detection_records(year, country, state):
    """One simulated record per hotspot, preserving daily totals and source counts.

    Coordinates are sample city centers; times are evenly distributed within each
    day. Satellite, confidence, power and day/night are unavailable in these samples.
    """
    records = []
    for city in area_cities(country, state):
        counts = daily_activity(year, city)
        modis = daily_activity(year, city, ["MODIS"])
        for day, count in counts.items():
            midnight = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
            for index in range(count):
                timestamp = midnight + timedelta(seconds=(index + 1) * 86400 // (count + 1))
                records.append((timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                                city["latitude"], city["longitude"], None,
                                "MODIS" if index < modis[day] else "VIIRS", None, None, None))
    return tuple(sorted(records, key=lambda row: (row[0], row[1], row[2]), reverse=True))


def record_page(records, page, page_size=PAGE_SIZE):
    if page_size < 1:
        raise ValueError("Page size must be positive.")
    pages = max(1, (len(records) + page_size - 1) // page_size)
    page = min(max(0, page), pages - 1)
    offset = page * page_size
    visible = records[offset:offset + page_size]
    return {"rows": visible, "page": page, "pages": pages,
            "start": offset + 1 if visible else 0, "end": offset + len(visible), "total": len(records)}


@lru_cache(maxsize=8)
def records_csv(year, country, state):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow((*RECORD_COLUMNS, "Country", "State/Province", "Data type"))
    for row in detection_records(year, country, state):
        writer.writerow((*row, country, state, "Synthetic demonstration"))
    return output.getvalue().encode("utf-8-sig")
