"""Globo ilustrativo do protótipo, independente de serviços de mapas."""

import json
from pathlib import Path


def globe_html(latitude, longitude, location):
    template = Path(__file__).with_name("globe.html").read_text(encoding="utf-8")
    # O JSON fica em um script: neutralizar '<' evita encerrar a tag com texto de entrada.
    payload = json.dumps({"latitude": latitude, "longitude": longitude, "location": location})
    return template.replace("__LOCATION_DATA__", payload.replace("<", "\\u003c"))
