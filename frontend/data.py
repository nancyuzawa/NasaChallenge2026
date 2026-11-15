"""Dados demonstrativos do protótipo, até a API de hotspots estar disponível."""

from calendar import month_name
from datetime import date

import numpy as np

MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
TREND_2025 = [48, 35, 82, 104, 104, 108, 143, 129, 386, 109, 184, 293]


def dashboard_metrics(period):
    start, end = period
    days = max((end - start).days + 1, 1)
    full_days = 365
    scale = min(days / full_days, 1.65)
    hotspots = round(1284 * scale)
    month_index = max(range(len(TREND_2025)), key=TREND_2025.__getitem__) if start.year <= 2025 <= end.year else max(0, end.month - 1)
    peak_count = round(TREND_2025[month_index] * min(scale, 1))
    return {
        "hotspots": hotspots,
        "growth": round(18.5 * min(scale, 1.2), 1),
        "peak_month": month_name[month_index + 1],
        "peak_count": peak_count,
        "historical_growth": round(25.6 * min(scale, 1.2), 1),
        "current_period": round(314 * scale),
        "historical_average": 250,
        "period_label": f"{start:%d/%m/%Y} a {end:%d/%m/%Y}",
    }


def make_hotspots(latitude, longitude):
    """Cria uma nuvem estável de pontos apenas para compor o mapa de demonstração."""
    rng = np.random.default_rng(42)
    count = 30
    return {
        "latitude": np.clip(latitude + rng.normal(0, 3.2, count), -55, 15),
        "longitude": np.clip(longitude + rng.normal(0, 4.0, count), -82, -33),
    }
