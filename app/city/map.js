// Walk Through Time, city page: The map: MapLibre layers for buildings (coloured by era), roads, water, parks, areas and pins.
import { AREA_TYPES, BASICS, CITY_ID, ERAS, FADE, LAND, PIN_LAYERS, mix, store, tok } from './util.js';
import { S } from './state.js';
import { marksBuildings } from './data.js';
import { turnNeedle } from './sheet.js';
import { selectBuilding, showArea, showBasic, showLand, showPin, showRoute } from './cards.js';
import { drawPins } from './places.js';

export function isDark(){
  const t = document.documentElement.dataset.theme;
  return t === 'dark' || (t !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
}

// ================= Map =================
// era colour by year, faded towards the background by how precise the date is (as colourFor)
export function eraColour(){
  const step = t => ['step', ['get', 'y'], mix(ERAS[0][3], tok('--bg'), t), ...ERAS.slice(1).flatMap(e => [e[0], mix(e[3], tok('--bg'), t)])];
  return ['case', ['!', ['has', 'y']], tok('--unknown'),
    ['match', ['coalesce', ['get', 'f'], 'exact'], ...['approx', 'century', 'area'].flatMap(f => [f, step(FADE[f])]), step(0)]];
}
export function buildingColour(){
  const base = ['case', ['boolean', ['feature-state', 'sel'], false], tok('--sel'),
    ['boolean', ['feature-state', 'hl'], false], tok('--hl'), eraColour()];
  if (S.places) return ['case', ['boolean', ['feature-state', 'sel'], false], tok('--sel'),
    ['boolean', ['feature-state', 'hl'], false], tok('--hl'), tok('--ghost')];   // only this person's places stand out
  const keys = [...S.active].filter(marksBuildings);
  if (!keys.length) return base;
  const inLayer = ['any', ...keys.map(k => ['in', ',' + k + ',', ['coalesce', ['get', 'L'], '']])];
  // in a ticked layer: era colour when dated, a strong neutral when not (plain grey would vanish into the faded rest)
  return ['case', ['boolean', ['feature-state', 'sel'], false], tok('--sel'),
    ['boolean', ['feature-state', 'hl'], false], tok('--hl'),
    inLayer, ['case', ['has', 'y'], eraColour(), tok('--marked')], tok('--ghost')];
}
export const pinColour = () => ['match', ['get', 'layer'], ...PIN_LAYERS.flatMap(L => [L, tok('--p-' + L)]), tok('--marked')];
export const basicColour = () => ['match', ['get', 't'], ...BASICS.flatMap(k => [k, tok('--b-' + k)]), tok('--muted')];
export const landColour = () => ['match', ['get', 't'], ...LAND.flatMap(t => [t, tok('--l-' + t)]), tok('--muted')];
export const natureColour = () => ['match', ['get', 't'], ...AREA_TYPES.flatMap(t => [t, tok('--n-' + t)]), tok('--n-reserve')];

export function drawMap(){
  return new Promise(resolve => {
    const b = S.city.bbox;
    S.map = new maplibregl.Map({
      container:'map', ...S.city.home, maxPitch:75,
      // room around the city, so a phone can zoom out to the whole city and its surroundings (zoom 10)
      maxBounds:[[b.w - 0.15, b.s - 0.12], [b.e + 0.15, b.n + 0.12]],
      minZoom:10,                  // the whole city; the tiles start at zoom 10
      attributionControl:false,
      style:{ version:8, sources:{}, layers:[{ id:'bg', type:'background', paint:{ 'background-color': tok('--bg') } }],
        light:{ anchor:'map', position:[1.4, 210, 35], intensity: isDark() ? 0.35 : 0.45 } }
    });
    S.map.addControl(new maplibregl.AttributionControl({ compact:true, customAttribution:
      '© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors · Historic England (OGL) · Natural England (OGL) · Wikidata (CC0) · Wikipedia (CC BY-SA)'
      + (S.data.ground ? ' · Ground: ' + S.data.ground.credit + ' (OGL)' : '') }), 'bottom-right');

    S.map.on('load', () => {
      S.map.addSource('osm', { type:'raster', tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize:256, maxzoom:19 });
      S.map.addLayer({ id:'osm', type:'raster', source:'osm', layout:{ visibility:'none' }, paint:{ 'raster-opacity':0.75, 'raster-saturation':-0.6 } });
      const key = store.get('mtKey'); if (key) addNls(key);
      // the city's tiles (outlines of buildings, roads, water, parks), or the old single file's GeoJSON
      const T = S.data.tiles, tileUrl = T && new URL(`../data/${CITY_ID}/tiles/{z}/{x}/{y}.pbf?v=${S.data.build}`, location.href).href
        .replace(/^https?:/, window.DecompressionStream ? 'gzt:' : location.protocol).replace('%7Bz%7D', '{z}').replace('%7Bx%7D', '{x}').replace('%7By%7D', '{y}');
      const src = (name, extra = {}) => T ? { source:'city', 'source-layer':name, ...extra } : { source:name, ...extra };
      if (T) S.map.addSource('city', { type:'vector', tiles:[tileUrl], minzoom:T.minzoom, maxzoom:T.maxzoom });
      else ['parks', 'water', 'roads'].forEach(k => S.map.addSource(k, { type:'geojson', data:S.data[k] }));
      S.map.addLayer({ id:'parks', type:'fill', ...src('parks'), paint:{ 'fill-color':tok('--park') } });
      S.map.addLayer({ id:'water', type:'fill', ...src('water'), filter:['==', ['geometry-type'], 'Polygon'], paint:{ 'fill-color':tok('--water') } });
      S.map.addLayer({ id:'waterline', type:'line', ...src('water'), filter:['==', ['geometry-type'], 'LineString'],
        paint:{ 'line-color':tok('--water'), 'line-width':['interpolate', ['linear'], ['zoom'], 13, 2, 17, 10] } });
      S.map.addLayer({ id:'roads', type:'line', ...src('roads'), layout:{ 'line-cap':'round', 'line-join':'round' },
        paint:{ 'line-color':tok('--road'), 'line-width':['interpolate', ['linear'], ['zoom'], 13, ['match', ['get','k'], 'major', 1.5, 0.4], 18, ['match', ['get','k'], 'major', 14, 3]] } });
      addGround();

      if (T) addLand(src);
      // areas (nature, conservation): from the tiles, or the older data file's GeoJSON
      const areaSrc = T && S.data.areas ? src('areas') : { source:'nature' };
      if (!(T && S.data.areas)) S.map.addSource('nature', { type:'geojson', data: S.data.nature || { type:'FeatureCollection', features:[] } });
      S.map.addLayer({ id:'nature-fill', type:'fill', ...areaSrc, layout:{ visibility:'none' },
        paint:{ 'fill-color':natureColour(), 'fill-opacity':0.32 } });
      S.map.addLayer({ id:'nature-line', type:'line', ...areaSrc, layout:{ visibility:'none' },
        paint:{ 'line-color':natureColour(), 'line-width':2, 'line-dasharray':[2, 1] } });

      // walking routes: from the tiles, or the older data file's GeoJSON
      const routeSrc = T && Array.isArray(S.data.routes) ? src('routes') : { source:'routes' };
      if (!(T && Array.isArray(S.data.routes))) S.map.addSource('routes', { type:'geojson', data: S.data.routes || { type:'FeatureCollection', features:[] } });
      S.map.addLayer({ id:'routes', type:'line', ...routeSrc, layout:{ visibility:'none', 'line-cap':'round', 'line-join':'round' },
        paint:{ 'line-color':tok('--route'), 'line-width':['interpolate', ['linear'], ['zoom'], 11, 2, 17, 5], 'line-dasharray':[1.6, 1.2] } });

      if (T) S.map.addSource('b', { type:'vector', tiles:[tileUrl], minzoom:T.minzoom, maxzoom:T.maxzoom });
      else S.map.addSource('b', { type:'geojson', data:{ type:'FeatureCollection', features: S.features } });
      S.map.addLayer({ id:'b', type:'fill-extrusion', source:'b', ...(T ? { 'source-layer':'b' } : {}), paint:{
        'fill-extrusion-color':buildingColour(),
        'fill-extrusion-height':['get', 'h'], 'fill-extrusion-base':['coalesce', ['get', 'base'], 0], 'fill-extrusion-opacity':0.95,
        'fill-extrusion-vertical-gradient':true } });

      S.map.addSource('storypins', { type:'geojson', data: S.data.pins || { type:'FeatureCollection', features:[] } });
      S.map.addLayer({ id:'storypins', type:'circle', source:'storypins', layout:{ visibility:'none' }, paint:{
        'circle-radius':['interpolate', ['linear'], ['zoom'], 13, 4, 18, 9], 'circle-color':pinColour(),
        'circle-stroke-color':tok('--on-strong'), 'circle-stroke-width':2, 'circle-pitch-alignment':'map' } });
      // toilets, drinking water and benches: close up only (the tiles have them from zoom 14)
      const basicSrc = T ? src('basics') : { source:'basics' };
      if (!T) S.map.addSource('basics', { type:'geojson', data: S.data.basics || { type:'FeatureCollection', features:[] } });
      S.map.addLayer({ id:'basics', type:'circle', ...basicSrc, minzoom:15, layout:{ visibility:'none' }, paint:{
        'circle-radius':['interpolate', ['linear'], ['zoom'], 15, 3.5, 19, 8], 'circle-color':basicColour(),
        'circle-stroke-color':tok('--on-strong'), 'circle-stroke-width':1.5, 'circle-pitch-alignment':'map' } });
      S.map.addSource('places', { type:'geojson', data:{ type:'FeatureCollection', features:[] },
        cluster:true, clusterRadius:44, clusterMaxZoom:18 });
      // invisible layer: keeps the clustered source loaded so the HTML pins can read it
      S.map.addLayer({ id:'places-probe', type:'circle', source:'places', paint:{ 'circle-radius':1, 'circle-opacity':0 } });
      S.map.on('moveend', drawPins); S.map.on('sourcedata', e => { if (e.sourceId === 'places' && e.isSourceLoaded) drawPins(); });

      S.map.on('click', e => {
        if (e.originalEvent && e.originalEvent.target.closest('.pin')) return;
        const pinHit = S.map.getLayoutProperty('storypins', 'visibility') === 'visible'
          && S.map.queryRenderedFeatures([[e.point.x - 8, e.point.y - 8], [e.point.x + 8, e.point.y + 8]], { layers:['storypins'] })[0];
        if (pinHit) return showPin(pinHit.properties);
        const near = (id, r) => S.map.getLayoutProperty(id, 'visibility') === 'visible'
          && S.map.queryRenderedFeatures([[e.point.x - r, e.point.y - r], [e.point.x + r, e.point.y + r]], { layers:[id] })[0];
        const basic = near('basics', 8);
        if (basic) return showBasic(basic.properties);
        const route = near('routes', 6);
        if (route) return showRoute(route.properties.i);
        const land = S.map.getLayer('land-pt') && ['land-pt', 'land-open', 'land-gone', 'land-line', 'land-under']
          .map(id => near(id, 7)).find(Boolean);
        if (land) return showLand(land.properties);
        const hit = S.map.queryRenderedFeatures(e.point, { layers:['b'] })[0];
        if (hit) return selectBuilding(hit.id, [e.lngLat.lng, e.lngLat.lat]);
        const area = S.map.getLayer('nature-fill') && S.map.getLayoutProperty('nature-fill', 'visibility') === 'visible'
          && S.map.queryRenderedFeatures(e.point, { layers:['nature-fill'] })[0];
        if (area) return showArea((S.data.areas && S.data.areas[area.properties.i]) || area.properties);   // some areas are only in the tiles
        const ground = S.map.getLayer('land-fill') && S.map.getLayoutProperty('land-fill', 'visibility') === 'visible'
          && S.map.queryRenderedFeatures(e.point, { layers:['land-fill'] })[0];
        if (ground) showLand(ground.properties);
      });
      // start the credits folded behind their (i) button: on a phone they would cover the map
      document.querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show');
      S.map.on('rotate', turnNeedle); turnNeedle();
      S.map.on('mouseenter', 'b', () => S.map.getCanvas().style.cursor = 'pointer');
      S.map.on('mouseleave', 'b', () => S.map.getCanvas().style.cursor = '');
      resolve();
    });
  });
}

export function addNls(key){
  if (S.map.getLayer('nls')) S.map.removeLayer('nls');
  if (S.map.getSource('nls')) S.map.removeSource('nls');
  S.map.addSource('nls', { type:'raster', url:`https://api.maptiler.com/tiles/uk-osgb10k1888/tiles.json?key=${encodeURIComponent(key)}`, tileSize:256 });
  S.map.addLayer({ id:'nls', type:'raster', source:'nls', layout:{ visibility:'none' }, paint:{ 'raster-opacity':0.85 } }, S.map.getLayer('parks') ? 'parks' : undefined);
}

// ================= the land: brooks, woods, old railways and canals, historic sites… (pipeline/s06_land.py) =========
// One tile layer, drawn as several map layers: areas, their edges, lines, culverted brooks (dotted), points close up,
// and the old railways and canals twice: solid in the years they were in use, dashed once closed (setLand).
const LINES = ['rail', 'canal'];
const LAND_BASE = {
  'land-fill': ['==', ['geometry-type'], 'Polygon'],
  'land-edge': ['==', ['geometry-type'], 'Polygon'],
  'land-line': ['all', ['==', ['geometry-type'], 'LineString'], ['!', ['in', ['get', 't'], ['literal', LINES]]], ['!', ['has', 'u']]],
  'land-under': ['all', ['==', ['geometry-type'], 'LineString'], ['has', 'u']],
  'land-open': ['all', ['==', ['geometry-type'], 'LineString'], ['in', ['get', 't'], ['literal', LINES]]],
  'land-gone': ['all', ['==', ['geometry-type'], 'LineString'], ['in', ['get', 't'], ['literal', LINES]]],
  'land-pt': ['==', ['geometry-type'], 'Point'],
};
function addLand(src){
  const width = (a, b) => ['interpolate', ['linear'], ['zoom'], 11, a, 17, b];
  const hidden = { visibility:'none' };
  S.map.addLayer({ id:'land-fill', type:'fill', ...src('land'), layout:hidden, paint:{ 'fill-color':landColour(),
    'fill-opacity':['match', ['get', 't'], 'wood', 0.42, 'pond', 0.6, 'oldsite', 0.22, 0.32] } });
  S.map.addLayer({ id:'land-edge', type:'line', ...src('land'), layout:hidden, paint:{ 'line-color':landColour(),
    'line-width':['match', ['get', 't'], 'oldsite', 1.8, 0.8], 'line-opacity':0.8 } });
  S.map.addLayer({ id:'land-line', type:'line', ...src('land'), layout:{ ...hidden, 'line-cap':'round', 'line-join':'round' },
    paint:{ 'line-color':landColour(), 'line-width':['interpolate', ['linear'], ['zoom'],
      11, ['match', ['get', 't'], 'brook', 1, 1.5], 17, ['match', ['get', 't'], 'brook', 3.5, 4]] } });
  S.map.addLayer({ id:'land-under', type:'line', ...src('land'), layout:{ ...hidden, 'line-cap':'round' },
    paint:{ 'line-color':landColour(), 'line-width':width(1, 3), 'line-dasharray':[0.4, 2] } });
  S.map.addLayer({ id:'land-gone', type:'line', ...src('land'), layout:hidden,
    paint:{ 'line-color':landColour(), 'line-width':width(2, 5), 'line-dasharray':[2, 1.4] } });
  S.map.addLayer({ id:'land-open', type:'line', ...src('land'), layout:{ ...hidden, 'line-cap':'round', 'line-join':'round' },
    paint:{ 'line-color':landColour(), 'line-width':width(2.5, 6) } });
  S.map.addLayer({ id:'land-pt', type:'circle', ...src('land'), minzoom:13, layout:hidden, paint:{
    'circle-radius':['interpolate', ['linear'], ['zoom'], 13, 3, 18, 7], 'circle-color':landColour(),
    'circle-stroke-color':tok('--on-strong'), 'circle-stroke-width':1.5, 'circle-pitch-alignment':'map' } });
}
// the ticked kinds, and the year on the slider: a railway or canal is drawn from the year it opened, solid until
// it closed and dashed after (one with no closing year: dashed, as it is gone now)
export function setLand(types, Y){
  if (!S.map || !S.map.getLayer('land-fill')) return;
  const opened = ['any', ['!', ['has', 'y0']], ['<=', ['get', 'y0'], Y]];
  const inUse = ['all', ['has', 'y1'], ['>', ['get', 'y1'], Y]];
  const when = { 'land-open': ['all', opened, inUse], 'land-gone': ['all', opened, ['!', inUse]] };
  for (const [id, base] of Object.entries(LAND_BASE)) {
    S.map.setLayoutProperty(id, 'visibility', types.length ? 'visible' : 'none');
    S.map.setFilter(id, ['all', base, ['in', ['get', 't'], ['literal', types.length ? types : ['none']]], when[id] || true]);
  }
}

// ================= the ground: hills from the Environment Agency's survey (pipeline/s10_ground.py) =================
// Two sources over the same tiles, as MapLibre advises: one raises the map (terrain), one shades it (hillshade).
function addGround(){
  const G = S.data.ground;
  if (!G) return;
  const url = new URL(`../data/${CITY_ID}/ground/{z}/{x}/{y}.png?v=${S.data.build}`, location.href).href
    .replace('%7Bz%7D', '{z}').replace('%7Bx%7D', '{x}').replace('%7By%7D', '{y}');
  const dem = { type:'raster-dem', tiles:[url], tileSize:G.tileSize || 256, encoding:G.encoding || 'terrarium',
    minzoom:G.minzoom, maxzoom:G.maxzoom, bounds:G.bounds };
  S.map.addSource('ground', dem);
  S.map.addSource('groundShade', { ...dem });
  const dark = isDark();
  // light: dark brown shadows; dark: the shadows drawn whitish, as dark shading cannot be seen on a dark map
  S.map.addLayer({ id:'hillshade', type:'hillshade', source:'groundShade', paint:{
    'hillshade-exaggeration':['interpolate', ['linear'], ['zoom'], 11, 0.75, 16, 0.5],
    'hillshade-shadow-color': dark ? 'rgba(255,250,240,0.55)' : 'rgba(45,30,15,0.62)',
    'hillshade-highlight-color': dark ? 'rgba(0,0,0,0)' : 'rgba(255,255,255,0.3)',
    'hillshade-accent-color': dark ? 'rgba(255,250,240,0.28)' : 'rgba(45,30,15,0.32)',
    'hillshade-illumination-direction':315 } });
  setHills(store.get('hills') !== 'off');
}
export function setHills(on){
  if (!S.map || !S.map.getSource('ground')) return;
  S.map.setTerrain(on ? { source:'ground', exaggeration:1 } : null);
  S.map.setLayoutProperty('hillshade', 'visibility', on ? 'visible' : 'none');
}

