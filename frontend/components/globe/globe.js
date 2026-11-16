/* Local WebGL renderer. Selection events are the only messages sent to Python. */
(() => {
  const host = document.getElementById('globe');
  const loading = document.getElementById('loading');
  let globe, countries = [], selection, signature, hotspotSignature, hotspotData = {points: [], total: 0, shown: 0}, frameStyle = null;
  const sensorColor = point => point.sensor === 'MODIS' ? '#ff3b30' : '#ffd166';
  const post = (type, data = {}) => window.parent.postMessage({isStreamlitMessage: true, type, ...data}, '*');
  const safeLabel = text => { const label = document.createElement('span'); label.textContent = text; return label; };
  const send = (kind, id) => post('streamlit:setComponentValue', {dataType: 'json', value: {kind, id, event_id: crypto.randomUUID()}});

  function applySelection(next) {
    selection = next;
    const key = JSON.stringify(next);
    if (signature === key || !globe) return;
    signature = key;
    const boundary = next.boundary;
    globe.polygonsData(boundary ? [...countries, boundary] : countries);
    globe.polygonAltitude(c => c.properties.kind === 'selected-state' ? .007 : .005);
    const hasState = next.state && next.state !== 'All regions';
    globe.polygonCapColor(c => c.properties.kind === 'selected-state'
      ? '#57c9c0' : !hasState && c.properties.iso === next.country_iso ? '#57c9c0' : '#d4eede');
    globe.polygonStrokeColor(c => c.properties.kind === 'selected-state' ? '#e0ffff' : '#548c94');
    const polygons = boundary
      ? (boundary.geometry.type === 'MultiPolygon' ? boundary.geometry.coordinates : [boundary.geometry.coordinates])
      : [];
    globe.pathsData(polygons.flatMap(polygon => polygon.map(ring => ({points: ring}))));
    globe.pointColor(sensorColor);
    globe.pointRadius(.11);
    globe.pointOfView({lat: next.latitude, lng: next.longitude, altitude: next.state && next.state !== 'All regions' ? .65 : 1.65}, 600);
    document.getElementById('coordinates').textContent = `Lat: ${next.latitude.toFixed(4)} / Lon: ${next.longitude.toFixed(4)}`;
  }

  function applyHotspots(next) {
    hotspotData = next || {points: [], total: 0, shown: 0};
    if (!globe) return;
    const key = JSON.stringify(hotspotData);
    if (key === hotspotSignature) return;
    hotspotSignature = key;
    const markers = (hotspotData.points || []).filter(point => point.sensor === 'MODIS' || point.sensor === 'VIIRS');
    globe.pointsData(markers);
    const note = document.getElementById('hotspot-status');
    const count = hotspotData.shown || 0;
    note.textContent = count
      ? `${count.toLocaleString()} sensor locations${hotspotData.limited ? ` of ${hotspotData.total.toLocaleString()} (display sample)` : ''} · ${hotspotData.start} to ${hotspotData.end}`
      : 'No observations in the selected region / period';
  }

  function resize() {
    if (globe && host.clientWidth && host.clientHeight) globe.width(host.clientWidth).height(host.clientHeight);
  }

  async function initialize() {
    try {
      const response = await fetch('countries.json');
      if (!response.ok) throw new Error('Geographic data could not be loaded.');
      countries = (await response.json()).features;
      globe = new Globe(host, {rendererConfig: {antialias: true, alpha: false}})
        .backgroundColor('#09163b')
        .showAtmosphere(true).atmosphereColor('#5cc9dd').atmosphereAltitude(.1)
        .polygonsData(countries).polygonGeoJsonGeometry(c => c.geometry)
        .polygonAltitude(.005).polygonCapColor(() => '#d4eede').polygonSideColor(() => '#78aaa6')
        .polygonStrokeColor(() => '#548c94').polygonsTransitionDuration(0)
        .polygonLabel(() => '')
        .onPolygonClick(c => { if (c.properties.kind !== 'selected-state') send('country', c.properties.iso); })
        .pathsData([]).pathPoints('points').pathPointLat(p => p[1]).pathPointLng(p => p[0])
        .pathPointAlt(.009).pathColor(() => '#c5ffff').pathStroke(2.5).pathTransitionDuration(0)
        .pointsData([]).pointLat('latitude').pointLng('longitude')
        .pointAltitude(.012).pointResolution(4).pointRadius(.11)
        .pointColor(sensorColor).pointsTransitionDuration(0)
        .pointLabel(c => safeLabel(`${c.sensor} · ${c.latitude.toFixed(4)}, ${c.longitude.toFixed(4)}`));
      globe.globeMaterial().color.set('#2197b0');
      globe.globeMaterial().shininess = 12;
      globe.controls().enablePan = false;
      globe.controls().minDistance = 110;
      globe.controls().maxDistance = 650;
      globe.controls().enableDamping = true;
      globe.controls().dampingFactor = .12;
      globe.renderer().setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
      resize();
      if (selection) applySelection(selection);
      applyHotspots(hotspotData);
      loading.hidden = true;
      // Public renderer instance also permits inspection of camera movement in integration checks.
      window.firewatchGlobe = globe;
    } catch (error) {
      const message = String(error && error.message || error);
      loading.hidden = false;
      loading.textContent = /webgl|webglrenderer|graphics context/i.test(message)
        ? 'WebGL could not start. Enable hardware acceleration, reload, or use Filter.'
        : 'The map could not start. Reload the page or use Filter to choose a location.';
      console.error('Globe initialization failed:', error);
    }
  }

  const zoom = direction => {
    if (!globe) return;
    const view = globe.pointOfView();
    globe.pointOfView({altitude: Math.max(.15, Math.min(5, view.altitude * direction))}, 220);
  };
  document.getElementById('zoom-in').onclick = () => zoom(.75);
  document.getElementById('zoom-out').onclick = () => zoom(1.35);
  document.getElementById('reset').onclick = () => {
    if (globe && selection) globe.pointOfView({lat: selection.latitude, lng: selection.longitude, altitude: 1.8}, 500);
  };
  host.addEventListener('keydown', e => {
    if (!globe) return;
    const view = globe.pointOfView();
    if (e.key === '+' || e.key === '=') zoom(.75);
    else if (e.key === '-') zoom(1.35);
    else if (['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)) {
      e.preventDefault();
      globe.pointOfView({lat: Math.max(-85,Math.min(85,view.lat + (e.key==='ArrowUp'?10:e.key==='ArrowDown'?-10:0))), lng: view.lng + (e.key==='ArrowLeft'?-10:e.key==='ArrowRight'?10:0)}, 160);
    }
  });
  function restoreFrame() {
    if (frameStyle === null) return;
    window.frameElement.style.cssText = frameStyle; frameStyle = null;
  }
  document.getElementById('fullscreen').onclick = async () => {
    if (frameStyle !== null) return restoreFrame();
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.getElementById('map').requestFullscreen();
    } catch {
      const frame = window.frameElement;
      frameStyle = frame.style.cssText;
      Object.entries({position:'fixed',inset:'0',width:'100vw',height:'100dvh','z-index':'2147483647'}).forEach(([p,v]) => frame.style.setProperty(p,v,'important'));
    }
  };
  document.addEventListener('keydown', e => { if (e.key === 'Escape') restoreFrame(); });
  window.addEventListener('message', event => {
    if (event.source === window.parent && event.data.type === 'streamlit:render') {
      applySelection(event.data.args.selection);
      applyHotspots(event.data.args.hotspots);
    }
  });
  new ResizeObserver(resize).observe(host);
  post('streamlit:componentReady', {apiVersion: 1});
  post('streamlit:setFrameHeight', {height: 480});
  initialize();
})();
