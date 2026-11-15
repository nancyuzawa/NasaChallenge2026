"""Dados sintéticos do calendário e da comparação anual de atividade."""

from calendar import monthrange
from datetime import date, timedelta
from hashlib import sha256

import numpy as np

from data import dashboard_series


AVAILABLE_YEARS = (2025, 2024, 2023)
MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
YEAR_FACTORS = {2025: 1.0, 2024: .88, 2023: .78}
SERIES_COLORS = ("#ff832b", "#5999fb", "#b5b2ca")
HEAT_COLORS = ("#e7f4e9", "#a8d5a7", "#62b767", "#ffb648", "#f57400", "#c52429")
SENSORS = ("MODIS", "VIIRS")


def _annual_totals(year, filters=None):
    """Anos anteriores são cenários de demonstração derivados da amostra de 2025."""
    if year not in AVAILABLE_YEARS:
        raise ValueError("No demonstration data for this year.")
    reference = dashboard_series((date(2025, 1, 1), date(2025, 12, 31)), filters)
    return [round(value * YEAR_FACTORS[year]) for value in reference]


def _selected_sensors(sensors):
    selected = set(sensors or SENSORS)
    if not selected.issubset(SENSORS):
        raise ValueError("Unknown sensor. Choose MODIS or VIIRS.")
    return selected


def daily_activity(year, filters=None, sensors=None):
    """Distribui cada total mensal em dias, preservando exatamente as somas."""
    selected = _selected_sensors(sensors)
    monthly = _annual_totals(year, filters)
    location = tuple((filters or {}).get(key) for key in ("country", "state", "city", "latitude", "longitude"))
    seed = int.from_bytes(sha256(repr((year, location)).encode()).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    result = {}
    for month, total in enumerate(monthly, 1):
        days = monthrange(year, month)[1]
        weights = rng.gamma(1.4, 1.0, days)
        counts = rng.multinomial(total, weights / weights.sum())
        result.update({date(year, month, day): int(count) for day, count in enumerate(counts, 1)})
    if selected == set(SENSORS):
        return result
    # Synthetic source assignments partition the existing demo totals exactly.
    source_rng = np.random.default_rng(seed ^ 0x4D4F444953)
    modis = {day: int(source_rng.binomial(count, .42)) for day, count in result.items()}
    return modis if "MODIS" in selected else {day: count - modis[day] for day, count in result.items()}


def annual_series(year, filters=None, sensors=None):
    if _selected_sensors(sensors) == set(SENSORS):
        return _annual_totals(year, filters)
    daily = daily_activity(year, filters, sensors)
    return [sum(count for day, count in daily.items() if day.month == month) for month in range(1, 13)]


def calendar_cells(year, month=0, filters=None, sensors=None):
    if month not in range(13):
        raise ValueError("Invalid month.")
    counts = daily_activity(year, filters, sensors)
    start = date(year, month or 1, 1)
    end = date(year, month, monthrange(year, month)[1]) if month else date(year, 12, 31)
    origin = start - timedelta(days=(start.weekday() + 1) % 7)
    return [{"date": day, "count": count, "week": (day - origin).days // 7,
             "weekday": (day.weekday() + 1) % 7}
            for day, count in counts.items() if start <= day <= end]


def heat_legend(counts):
    maximum = max(counts, default=0)
    step = max(1, (maximum + 5) // 6)
    return [{"color": color, "low": 0 if level == 0 else level * step + 1,
             "high": (level + 1) * step, "step": step}
            for level, color in enumerate(HEAT_COLORS)]


def annual_summary(year, filters=None, sensors=None):
    values = annual_series(year, filters, sensors)
    total = sum(values)
    previous = sum(annual_series(year - 1, filters, sensors)) if year - 1 in AVAILABLE_YEARS else None
    start = max(range(10), key=lambda index: sum(values[index:index + 3]))
    return {"year": year, "series": values, "total": total,
            "growth": round((total / previous - 1) * 100, 1) if previous else None,
            "peak_period": f"{MONTH_NAMES[start]} to {MONTH_NAMES[start + 2]}" if total else "No activity"}


def month_summary(year, month, filters=None, sensors=None):
    """Detalhes consistentes com as somas do calendário e da análise anual."""
    if month not in range(1, 13):
        raise ValueError("Invalid month.")
    daily = daily_activity(year, filters, sensors)
    days = [(day, count) for day, count in daily.items() if day.month == month]
    total = sum(count for _, count in days)
    annual_total = sum(daily.values())
    if month > 1:
        previous = sum(count for day, count in daily.items() if day.month == month - 1)
    elif year - 1 in AVAILABLE_YEARS:
        previous = annual_series(year - 1, filters, sensors)[-1]
    else:
        previous = None
    return {"year": year, "month": month, "days": days, "total": total,
            "annual_share": round(total / annual_total * 100, 1) if annual_total else 0,
            "growth": round((total / previous - 1) * 100, 1) if previous else None,
            "confidence": None}
