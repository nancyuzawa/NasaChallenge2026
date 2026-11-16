/* Strict vendor API regression check; no browser or real datasets required. */
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');
const root = path.resolve(__dirname, '../components/globe');
const vendor = fs.readFileSync(path.join(root, 'vendor/globe.gl.min.js'), 'utf8');
// Linked renderer props are explicitly listed in the bundled library.
const marker = '"pathsData","pathPoints"';
const start = vendor.lastIndexOf(marker);
assert(start >= 0, 'Cannot locate bundled paths API');
const end = vendor.indexOf('].map', start);
const exported = new Set(Array.from(vendor.slice(start,end).matchAll(/"([A-Za-z][A-Za-z0-9]*)"/g), m => m[1]));
assert(exported.has('pathTransitionDuration'));
assert(!exported.has('pathsTransitionDuration'));
const methods = new Set([
  'backgroundColor','showAtmosphere','atmosphereColor','atmosphereAltitude',
  'polygonsData','polygonGeoJsonGeometry','polygonAltitude','polygonCapColor','polygonSideColor',
  'polygonStrokeColor','polygonsTransitionDuration','polygonLabel','onPolygonClick',
  'pointsData','pointLat','pointLng','pointAltitude','pointResolution','pointRadius','pointColor',
  'pointsTransitionDuration','pointLabel','pointOfView','width','height'
]);
const nodes = new Map(), handlers = {}, record = {}, errors = [];
const element = id => {
  if (!nodes.has(id)) nodes.set(id, {clientWidth:600,clientHeight:480,style:{},addEventListener(){}});
  return nodes.get(id);
};
let globe;
globe = new Proxy({}, {get(_, key) {
  if (key === 'globeMaterial') return () => ({color:{set(color){record.ocean=color;}}});
  if (key === 'controls') return () => ({});
  if (key === 'renderer') return () => ({setPixelRatio(){}});
  if (!methods.has(key) && !exported.has(key)) return undefined;
  return (...args) => {record[key]=args[0]; return globe;};
}});
const country = {properties:{iso:'BRA',name:'Brazil'}};
const context = {
  document:{getElementById:element,createElement:()=>({}),addEventListener(){}},
  window:{parent:{postMessage(){}},addEventListener:(name, fn)=>{handlers[name]=fn;}},
  ResizeObserver:class {observe(){}}, Globe:function(){return globe;},
  fetch:async()=>({ok:true,json:async()=>({features:[country]})}),
  console:{error:(...args)=>errors.push(args.join(' '))}
};
vm.runInNewContext(fs.readFileSync(path.join(root,'globe.js'),'utf8'),context);
setImmediate(() => {
  assert.deepStrictEqual(errors, [], 'Initialization failed: '+errors.join('; '));
  assert.strictEqual(element('loading').hidden, true, 'Loading message should disappear');
  assert.strictEqual(record.ocean, '#2197b0', 'Original ocean color must be restored');
  assert.strictEqual(record.pathTransitionDuration, 0);
  const boundary = {properties:{kind:'selected-state',name:'Distrito Federal'},
    geometry:{type:'Polygon',coordinates:[[[0,0],[1,0],[1,1],[0,0]]]}};
  const render = (state, shape) => handlers.message({source:context.window.parent,
    data:{type:'streamlit:render',args:{selection:{country_iso:'BRA',state,boundary:shape,latitude:0,longitude:0},
      hotspots:{points:[{sensor:'MODIS'},{sensor:'VIIRS'}],shown:2,total:2}}}});
  render('Distrito Federal',boundary);
  assert.strictEqual(record.polygonCapColor(country),'#d4eede');
  assert.strictEqual(record.polygonCapColor(boundary),'#57c9c0');
  assert.strictEqual(record.pathsData.length,1);
  assert.strictEqual(record.polygonLabel(boundary),'');
  assert.strictEqual(record.pointColor({sensor:'MODIS'}),'#ff3b30');
  assert.strictEqual(record.pointColor({sensor:'VIIRS'}),'#ffd166');
  render('All regions',null);
  assert.strictEqual(record.polygonCapColor(country),'#57c9c0');
  assert.strictEqual(record.pathsData.length,0);
  console.log('Globe initialization, bundled path API, original palette, selected region and sensors: OK');
});
