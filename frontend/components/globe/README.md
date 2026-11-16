# Location selection globe

Streamlit v1 component with bidirectional communication. The globe sends only
country/city identifiers and an event identifier. Python validates these against
the local catalog before updating session filters. Rendering assets and geographic
data are served locally; no CDN, external geocoding, or runtime API key is required.

- Renderer: [Globe.gl](https://globe.gl/) **2.46.2**, npm package verified
  against the registry's published SHA-512. Bundle: `vendor/globe.gl.min.js`;
  MIT license: `vendor/globe.gl.LICENSE`.
- Country boundaries: [Natural Earth, admin 0, 110m](https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_admin_0_countries.geojson).
- Reference cities: [Natural Earth, populated places, 110m](https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_populated_places.geojson),
  supplemented with the Brazilian cities already available in the prototype.
- Catalogs contain only the fields used by the application.

Drag to rotate. Click a country's territory to select that country; click a
point to select an available city. The searchable Location field also selects
countries and cities. Arrow keys rotate, `+`/`-` control zoom, and the first
control returns to the selected location. Expand uses the Fullscreen API or
fills the application window when that API is unavailable.

Requires WebGL. If initialization fails, the component displays a message;
Search and Filter remain available for selecting a location.


## MODIS / VIIRS markers

The Dashboard passes published MODIS and VIIRS hotspot coordinates to the globe.
MODIS markers are fire red (#ff3b30); VIIRS markers are golden yellow (#ffd166).
The map legend identifies both sensors. City navigation markers have been removed. Hotspot tooltips
identify the sensor and coordinates. Changing the country or date interval replaces
the sensor markers. The map respects the selected state/province polygon when one is selected. No synthetic fire markers are generated.

The DuckDB query deduplicates coordinates per sensor over the selected interval.
To bound browser rendering and message size, at most 5,000 locations per sensor are
shown, using deterministic hash ordering. The legend reports the display limit when
applied. Dashboard counts continue to use every detection. Point-query results are
cached by source-file signatures, country and period in `.dashboard_cache`.


## State/province boundaries

`states.geojson` bundles matched administrative polygons from Natural Earth Admin 1:
https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-1-states-provinces/
Source: https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_10m_admin_1_states_provinces.geojson
Natural Earth data is public domain. These are cartographic boundaries, not cadastral surveys.
The local asset now includes 4,133 administrative regions across the countries supported
by the application, including all 27 Brazilian states. Historical aliases without a
matching geometry remain unsupported. Unsupported regions display a warning and no points,
never a country-wide or radius substitute. Dashboard map and cards apply state
polygons before grouping or the per-sensor display limit. A country click resets
the selection to all regions. Activity retains its existing spatial adapter.


Dashboard region options are filtered by actual MODIS/VIIRS observations in the draft
date interval. Regions are no longer restricted to states that contain a city in the
navigation catalog. Availability checks use polygon membership and EXISTS, not the
sample of markers shown on the globe. A cache keyed by country, dates, source parts
and geometry version avoids repeating the same checks. Changing dates refreshes
options before Apply; Apply commits the country/state and date selection together.
