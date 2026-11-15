"""Catálogo local de países e cidades compartilhado pelo mapa e pelos filtros."""

import json
from pathlib import Path


ASSETS = Path(__file__).with_name("components") / "globe"
COUNTRIES = {f["properties"]["iso"]: f["properties"] for f in json.loads((ASSETS / "countries.json").read_text(encoding="utf-8"))["features"]}
CITY_RECORDS = json.loads((ASSETS / "cities.json").read_text(encoding="utf-8"))
CITY_BY_ID = {city["id"]: city for city in CITY_RECORDS}
STATE_CODES = {"São Paulo": "SP", "Amazonas": "AM", "Mato Grosso": "MT", "Pará": "PA", "Rondônia": "RO", "Rio de Janeiro": "RJ"}
REGIONS = {c["name"]: {"All regions": (c["lat"], c["lng"])} for c in sorted(COUNTRIES.values(), key=lambda c: c["name"])}
for city in CITY_RECORDS:
    if city["state"]:
        REGIONS[city["country"]].setdefault(city["state"], (city["latitude"], city["longitude"]))
CITIES = {
    f"{c['city']} - {STATE_CODES.get(c['state'], c['state']) or c['country']}, {c['country']}":
    (c["country"], c["state"], c["city"], c["latitude"], c["longitude"])
    for c in sorted(CITY_RECORDS, key=lambda c: (c["city"] != "Campinas", c["city"]))
}


def selection_filters(event, current):
    """Valida a seleção do componente e mantém o período e os demais filtros."""
    if not isinstance(event, dict):
        return None
    if event.get("kind") == "city" and event.get("id") in CITY_BY_ID:
        city = CITY_BY_ID[event["id"]]
        return {**current, **{k: city[k] for k in ("country", "state", "city", "latitude", "longitude")}}
    if event.get("kind") == "country" and event.get("id") in COUNTRIES:
        country = COUNTRIES[event["id"]]
        return {**current, "country": country["name"], "state": "All regions", "city": None,
                "latitude": country["lat"], "longitude": country["lng"]}
    return None
