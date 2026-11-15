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
