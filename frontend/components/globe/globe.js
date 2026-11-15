/* Local WebGL renderer. Selection events are the only messages sent to Python. */
(() => {
  const host = document.getElementById('globe');
  const loading = document.getElementById('loading');
  const citySelect = document.getElementById('city');
  let globe, countries = [], cities = [], selection, signature, frameStyle = null;
  const post = (type, data = {}) => window.parent.postMessage({isStreamlitMessage: true, type, ...data}, '*');
  const safeLabel = text => { const label = document.createElement('span'); label.textContent = text; return label; };
  const send = (kind, id) => post('streamlit:setComponentValue', {dataType: 'json', value: {kind, id, event_id: crypto.randomUUID()}});

  function chooseCity(city) {
    globe.pointOfView({lat: city.latitude, lng: city.longitude, altitude: .65}, 650);
    send('city', city.id);
  }

  function applySelection(next) {
    selection = next;
    const key = JSON.stringify(next);
    if (signature === key || !globe) return;
    signature = key;
    const country = countries.find(c => c.properties.iso === next.country_iso);
    citySelect.replaceChildren();
    const all = new Option(country ? `${country.properties.name} · All cities` : 'Select a country', '');
    citySelect.add(all);
    cities.filter(c => c.country_iso === next.country_iso).sort((a,b) => a.city.localeCompare(b.city)).forEach(c => {
      citySelect.add(new Option(c.city, c.id, false, c.city === next.city));
    });
    globe.polygonCapColor(c => c.properties.iso === next.country_iso ? '#57c9c0' : '#d4eede');
    globe.pointColor(c => c.city === next.city && c.country_iso === next.country_iso ? '#ff482c' : '#ffbb65');
    globe.pointRadius(c => c.city === next.city && c.country_iso === next.country_iso ? .6 : .28);
    globe.pointOfView({lat: next.latitude, lng: next.longitude, altitude: next.city ? 1.8 : 1.65}, 600);
    document.getElementById('coordinates').textContent = `Lat.: ${next.latitude.toFixed(4)} / Long.: ${next.longitude.toFixed(4)}`;
  }

  function resize() {
    if (globe && host.clientWidth && host.clientHeight) globe.width(host.clientWidth).height(host.clientHeight);
  }

  async function initialize() {
    try {
      const responses = await Promise.all([fetch('countries.json'), fetch('cities.json')]);
      if (responses.some(r => !r.ok)) throw new Error('Geographic data could not be loaded.');
      const data = await Promise.all(responses.map(r => r.json()));
      countries = data[0].features; cities = data[1];
      globe = new Globe(host, {rendererConfig: {antialias: true, alpha: false}})
        .backgroundColor('#09163b')
        .showAtmosphere(true).atmosphereColor('#5cc9dd').atmosphereAltitude(.1)
        .polygonsData(countries).polygonGeoJsonGeometry(c => c.geometry)
        .polygonAltitude(.005).polygonCapColor(() => '#d4eede').polygonSideColor(() => '#78aaa6')
        .polygonStrokeColor(() => '#548c94').polygonsTransitionDuration(0)
        .polygonLabel(c => safeLabel(`${c.properties.name} · Click to filter`))
        .onPolygonClick(c => send('country', c.properties.iso))
        .pointsData(cities).pointLat('latitude').pointLng('longitude')
        .pointAltitude(.012).pointRadius(.28).pointColor(() => '#ffbb65').pointsTransitionDuration(0)
        .pointLabel(c => safeLabel(`${c.city}, ${c.country} · Click to filter`))
        .onPointClick(chooseCity);
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
      loading.hidden = true;
      // Public renderer instance also permits inspection of camera movement in integration checks.
      window.firewatchGlobe = globe;
    } catch (error) {
      loading.textContent = '3D could not start. Enable WebGL, or use Search / Filter to choose a location.';
      console.error('Globe initialization failed:', error);
    }
  }

  citySelect.addEventListener('change', () => {
    const city = cities.find(c => c.id === citySelect.value);
    if (city) chooseCity(city);
    else if (selection?.country_iso) send('country', selection.country_iso);
  });
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
    if (event.source === window.parent && event.data.type === 'streamlit:render') applySelection(event.data.args.selection);
  });
  new ResizeObserver(resize).observe(host);
  post('streamlit:componentReady', {apiVersion: 1});
  post('streamlit:setFrameHeight', {height: 480});
  initialize();
})();
