// Walk Through Time, city page: The map: MapLibre layers for buildings (coloured by era), roads, water, parks, areas and pins.
import { AREA_TYPES, CITY_ID, ERAS, FADE, mix, store, tok } from './util.js';
import { S } from './state.js';
import { isArea } from './data.js';
import { turnNeedle } from './sheet.js';
import { selectBuilding, showArea, showPin } from './cards.js';
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
  const keys = [...S.active].filter(k => !isArea(k));
  if (!keys.length) return base;
  const inLayer = ['any', ...keys.map(k => ['in', ',' + k + ',', ['coalesce', ['get', 'L'], '']])];
  // in a ticked layer: era colour when dated, a strong neutral when not (plain grey would vanish into the faded rest)
  return ['case', ['boolean', ['feature-state', 'sel'], false], tok('--sel'),
    ['boolean', ['feature-state', 'hl'], false], tok('--hl'),
    inLayer, ['case', ['has', 'y'], eraColour(), tok('--marked')], tok('--ghost')];
}
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
      '© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors · Historic England (OGL) · Natural England (OGL) · Wikidata (CC0) · Wikipedia (CC BY-SA)' }), 'bottom-right');

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

      // areas (nature, conservation): from the tiles, or the older data file's GeoJSON
      const areaSrc = T && S.data.areas ? src('areas') : { source:'nature' };
      if (!(T && S.data.areas)) S.map.addSource('nature', { type:'geojson', data: S.data.nature || { type:'FeatureCollection', features:[] } });
      S.map.addLayer({ id:'nature-fill', type:'fill', ...areaSrc, layout:{ visibility:'none' },
        paint:{ 'fill-color':natureColour(), 'fill-opacity':0.32 } });
      S.map.addLayer({ id:'nature-line', type:'line', ...areaSrc, layout:{ visibility:'none' },
        paint:{ 'line-color':natureColour(), 'line-width':2, 'line-dasharray':[2, 1] } });

      if (T) S.map.addSource('b', { type:'vector', tiles:[tileUrl], minzoom:T.minzoom, maxzoom:T.maxzoom });
      else S.map.addSource('b', { type:'geojson', data:{ type:'FeatureCollection', features: S.features } });
      S.map.addLayer({ id:'b', type:'fill-extrusion', source:'b', ...(T ? { 'source-layer':'b' } : {}), paint:{
        'fill-extrusion-color':buildingColour(),
        'fill-extrusion-height':['get', 'h'], 'fill-extrusion-base':['coalesce', ['get', 'base'], 0], 'fill-extrusion-opacity':0.95,
        'fill-extrusion-vertical-gradient':true } });

      S.map.addSource('storypins', { type:'geojson', data: S.data.pins || { type:'FeatureCollection', features:[] } });
      S.map.addLayer({ id:'storypins', type:'circle', source:'storypins', layout:{ visibility:'none' }, paint:{
        'circle-radius':['interpolate', ['linear'], ['zoom'], 13, 4, 18, 9], 'circle-color':tok('--marked'),
        'circle-stroke-color':tok('--on-strong'), 'circle-stroke-width':2, 'circle-pitch-alignment':'map' } });
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
        const hit = S.map.queryRenderedFeatures(e.point, { layers:['b'] })[0];
        if (hit) return selectBuilding(hit.id, [e.lngLat.lng, e.lngLat.lat]);
        const area = S.map.getLayer('nature-fill') && S.map.getLayoutProperty('nature-fill', 'visibility') === 'visible'
          && S.map.queryRenderedFeatures(e.point, { layers:['nature-fill'] })[0];
        if (area) showArea((S.data.areas && S.data.areas[area.properties.i]) || area.properties);   // some areas are only in the tiles
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
