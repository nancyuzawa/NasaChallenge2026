"""Local Natural Earth administrative polygons, matched to the region catalog."""
from functools import lru_cache
import json
from pathlib import Path

PATH=Path(__file__).with_name('components')/'globe/states.geojson'


@lru_cache(maxsize=1)
def _load(mtime):
    data=json.loads(PATH.read_text(encoding='utf-8'))
    return {(f['properties']['country'],f['properties']['state']):f['geometry'] for f in data['features']}


def geometry(country,state):
    return _load(PATH.stat().st_mtime_ns).get((country,state))


def bounds(shape):
    polygons=shape['coordinates'] if shape['type']=='MultiPolygon' else [shape['coordinates']]
    points=[p for poly in polygons for p in poly[0]]
    return min(p[1] for p in points),max(p[1] for p in points),min(p[0] for p in points),max(p[0] for p in points)


def selected(filters):
    return filters.get('state') not in (None,'','All regions')


def regions(country):
    return {state:shape for (name,state),shape in _load(PATH.stat().st_mtime_ns).items() if name==country}
