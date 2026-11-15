"""Séries demonstrativas por cidade, restritas ao ano de referência de 2025."""

from calendar import month_name, monthrange
from datetime import date
from functools import lru_cache
from hashlib import sha256

import numpy as np

from locations import CITY_RECORDS

MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
TREND_2025 = [48, 35, 82, 104, 104, 108, 143, 129, 386, 109, 184, 293]


@lru_cache(maxsize=256)
def _city_profile(city_id):
    """Amostra sintética estável; não representa medições de satélite."""
    if city_id == "BRA:Campinas":
        values = np.array(TREND_2025, dtype=float)
        mask = np.arange(12) != 8
        values[mask] *= (1284 - 386) / values[mask].sum()
        result = np.rint(values).astype(int)
        result[0] += 1284 - int(result.sum())
        return tuple(int(n) for n in result)
    seed = int.from_bytes(sha256(city_id.encode("utf-8")).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    values = np.array(TREND_2025) * rng.uniform(.2, 1.8) * rng.uniform(.65, 1.35, 12)
    return tuple(int(round(n)) for n in values)


def _selected_cities(filters):
    if not filters:
        return [c for c in CITY_RECORDS if c["id"] == "BRA:Campinas"]
    cities = [c for c in CITY_RECORDS if c["country"] == filters["country"]]
    if filters.get("city"):
        return [c for c in cities if c["city"] == filters["city"]]
    if filters.get("state") not in (None, "", "All regions"):
        cities = [c for c in cities if c["state"] == filters["state"]]
        # Coordenadas manuais restringem a amostra local a um raio aproximado de 100 km.
        cities = [c for c in cities if
                  (c["latitude"] - filters["latitude"]) ** 2 +
                  ((c["longitude"] - filters["longitude"]) * np.cos(np.radians(filters["latitude"]))) ** 2 <= .9 ** 2]
    return cities


def dashboard_series(period, filters=None):
    start, end = period
    values = np.zeros(12)
    for city in _selected_cities(filters):
        values += _city_profile(city["id"])
    for month in range(1, 13):
        month_start = date(2025, month, 1)
        month_end = date(2025, month, monthrange(2025, month)[1])
        overlap = max(0, (min(end, month_end) - max(start, month_start)).days + 1)
        values[month - 1] *= overlap / month_end.day
    return [int(round(n)) for n in values]


def dashboard_metrics(period, filters=None):
    start, end = period
    series = dashboard_series(period, filters)
    total = sum(series)
    peak = max(range(12), key=series.__getitem__)
    historical = round(total / 1.256)
    return {
        "hotspots": total, "growth": 18.5 if total else 0,
        "peak_month": month_name[peak + 1] if total else "—", "peak_count": series[peak],
        "historical_growth": round((total / historical - 1) * 100, 1) if historical else 0,
        "current_period": total, "historical_average": historical,
        "period_label": f"{start:%d/%m/%Y} a {end:%d/%m/%Y}",
    }
