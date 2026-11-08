// Walk Through Time: city page.
// Loads ../data/<city>.json (built by GitHub Actions). If that file is missing,
// falls back to fetching OpenStreetMap, Historic England and Wikidata live.
(() => {
const CITY_ID = document.body.dataset.city;
const MAX_YEAR = new Date().getFullYear();
const OVERPASS = [
  'https://overpass-api.de/api/interpreter',
  'https://overpass.private.coffee/api/interpreter',
  'https://overpass.kumi.systems/api/interpreter',
];
const NHLE = 'https://services-eu1.arcgis.com/ZOdPfBS3aqqDYPUQ/arcgis/rest/services/National_Heritage_List_for_England_NHLE_v02_VIEW/FeatureServer/0/query';
const WDQS = 'https://query.wikidata.org/sparql';

// Eras: [from, to, label, colour]. Warm = old, cool = new.
const ERAS = [
  [0,    1699, 'before 1700', '#5b1f43'],
  [1700, 1799, '1700s',       '#93283c'],
  [1800, 1839, '1800–39',     '#c4472d'],
  [1840, 1879, '1840–79',     '#e2802b'],
  [1880, 1913, '1880–1913',   '#e9b934'],
  [1914, 1945, '1914–45',     '#9cbf4a'],
  [1946, 1979, '1946–79',     '#3d9c8a'],
  [1980, 1999, '1980–99',     '#3a76b6'],
  [2000, 9999, '2000+',       '#6c5cc6'],
];

const $ = id => document.getElementById(id);
const store = { get(k){ try { return localStorage.getItem(k); } catch { return null; } },
                set(k,v){ try { localStorage.setItem(k,v); } catch {} } };
const tok = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const say = t => { $('status').textContent = t || ''; };
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = n => n.toLocaleString('en-GB');
function progress(p, step){ $('lpct').textContent = Math.round(p) + '%'; if (step) $('lstep').textContent = step; }

async function fetchJSON(url, opts = {}, ms = 60000){
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    const r = await fetch(url, { ...opts, signal: ctrl.signal });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } catch (e) {
    throw new Error(e.name === 'AbortError' ? 'timed out' : e.message);
  } finally { clearTimeout(timer); }
}

// ================= Year parsing (OSM start_date and similar) =================
function parseYear(raw){
  if (raw == null) return null;
  const s = String(raw).trim().toLowerCase();
  let m;
  if ((m = s.match(/(\d{4})\s*(?:\.\.|–|-|to)\s*(\d{4})/))) return { y: Math.round((+m[1] + +m[2]) / 2), a: true };
  if ((m = s.match(/\b(\d{3})0s\b/))) return { y: +(m[1] + '5'), a: true };
  if (!/\d{4}/.test(s)) {
    m = s.match(/\bc\s?(\d{1,2})\b/) || s.match(/\b(\d{1,2})(?:st|nd|rd|th)?\s*c(?:entury)?\b/);
    if (m) {
      const base = (+m[1] - 1) * 100;
      const off = /early|first half/.test(s) ? 20 : /late|second half/.test(s) ? 80 : 50;
      return { y: base + off, a: true };
    }
    return null;
  }
  const y = +s.match(/(\d{4})/)[1];
  if (y < 1000 || y > MAX_YEAR) return null;
  const a = /^(c|ca|circa|about|~|before|after|early|mid|late|pre)/.test(s) || /[?~]/.test(s);
  return { y, a };
}

// ================= Colour =================
function hexToRgb(h){ const n = parseInt(h.slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255]; }
function mix(a, b, t){ const A = hexToRgb(a), B = hexToRgb(b);
  return '#' + A.map((v, i) => Math.round(v + (B[i] - v) * t).toString(16).padStart(2, '0')).join(''); }
const eraOf = y => ERAS.find(e => y >= e[0] && y <= e[1]);
function colourFor(p){
  if (p.y == null) return tok('--unknown');
  const base = eraOf(p.y)[3];
  return p.ya ? mix(base, tok('--bg'), 0.45) : base;   // approximate dates are paler
}

// ================= Geometry helpers =================
function stitchRings(ways){
  const rings = [], open = ways.map(w => w.slice());
  const same = (a, b) => a[0] === b[0] && a[1] === b[1];
  while (open.length) {
    let ring = open.shift(), guard = 0;
    while (!(ring.length > 3 && same(ring[0], ring[ring.length-1])) && guard++ < 500) {
      const end = ring[ring.length-1];
      const i = open.findIndex(w => same(w[0], end) || same(w[w.length-1], end));
      if (i < 0) break;
      let next = open.splice(i, 1)[0];
      if (!same(next[0], end)) next = next.reverse();
      ring = ring.concat(next.slice(1));
    }
    if (ring.length > 3) rings.push(ring);
  }
  return rings;
}
function pointInRing(x, y, ring){
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) inside = !inside;
  }
  return inside;
}
function heightOf(t){
  const h = parseFloat(t.height || t['building:height']);
  if (h > 0 && h < 400) return h;
  const lv = parseFloat(t['building:levels']), rl = parseFloat(t['roof:levels']) || 0;
  if (lv > 0) return lv * 3.2 + rl * 1.6 + 1;
  const k = t.building;
  if (['house','detached','semidetached_house','terrace','residential'].includes(k)) return 8;
  if (['garage','garages','shed','hut','kiosk','roof','carport'].includes(k)) return 3;
  if (['church','chapel'].includes(k)) return 16;
  if (k === 'cathedral') return 28;
  return 10;
}

// ================= Live fallback (same logic as scripts/build_city.py) =================
async function liveData(city){
  const b = city.bbox, bb = `${b.s},${b.w},${b.n},${b.e}`;
  const q = `[out:json][timeout:90];(
    way["building"](${bb}); relation["building"]["type"="multipolygon"](${bb});
    way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|pedestrian|service|footway)$"](${bb});
    way["natural"="water"](${bb}); way["waterway"~"^(canal|river)$"](${bb}); relation["natural"="water"](${bb});
    way["leisure"~"^(park|garden)$"](${bb}); way["landuse"="grass"](${bb});
  ); out tags geom qt;`;
  let osm = null, errs = [];
  for (const url of OVERPASS) {
    progress(10, `requesting buildings from OpenStreetMap (${new URL(url).host})…`);
    try { osm = await fetchJSON(url + '?data=' + encodeURIComponent(q), {}, 90000); break; }
    catch (e) { errs.push(new URL(url).host + ': ' + e.message); }
  }
  if (!osm) throw new Error('OpenStreetMap servers did not respond (' + errs.join('; ') + ')');

  progress(40, 'reading buildings…');
  const buildings = [], roads = [], water = [], parks = [];
  for (const el of osm.elements) {
    const t = el.tags || {};
    if (el.type === 'way' && el.geometry) {
      const c = el.geometry.map(g => [g.lon, g.lat]);
      if (t.building) { if (c.length >= 4) buildings.push({ rings:[c], tags:t, osm:'way/' + el.id }); }
      else if (t.highway) roads.push({ type:'Feature', properties:{ k: ['footway','service','pedestrian'].includes(t.highway) ? 'minor' : 'major' }, geometry:{ type:'LineString', coordinates:c } });
      else if (t.waterway) water.push({ type:'Feature', properties:{}, geometry:{ type:'LineString', coordinates:c } });
      else if (t.natural === 'water' && c.length > 3) water.push({ type:'Feature', properties:{}, geometry:{ type:'Polygon', coordinates:[c] } });
      else if ((t.leisure || t.landuse) && c.length > 3) parks.push({ type:'Feature', properties:{}, geometry:{ type:'Polygon', coordinates:[c] } });
    } else if (el.type === 'relation' && el.members) {
      const rings = stitchRings(el.members.filter(m => m.role === 'outer' && m.geometry).map(m => m.geometry.map(g => [g.lon, g.lat])));
      if (!rings.length) continue;
      if (t.building) buildings.push({ rings, tags:t, osm:'relation/' + el.id });
      else if (t.natural === 'water') rings.forEach(r => water.push({ type:'Feature', properties:{}, geometry:{ type:'Polygon', coordinates:[r] } }));
    }
  }

  progress(50, 'listed buildings from Historic England…');
  let listed = [];
  try {
    const qs = new URLSearchParams({ where:'1=1', geometry:`${b.w},${b.s},${b.e},${b.n}`, geometryType:'esriGeometryEnvelope',
      inSR:'4326', spatialRel:'esriSpatialRelIntersects', outFields:'ListEntry,Name,Grade,hyperlink', outSR:'4326',
      returnGeometry:'true', resultRecordCount:'2000', f:'geojson' });
    const gj = await fetchJSON(NHLE + '?' + qs);
    for (const f of gj.features || []) {
      const g = f.geometry; if (!g) continue;
      (g.type === 'MultiPoint' ? g.coordinates : g.type === 'Point' ? [g.coordinates] : []).forEach(c => listed.push({ x:c[0], y:c[1], p:f.properties }));
    }
  } catch (e) { say('Historic England unavailable: ' + e.message); }

  buildings.forEach(bd => {
    const xs = bd.rings[0].map(c => c[0]), ys = bd.rings[0].map(c => c[1]);
    bd.bb = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]; bd.listed = [];
  });
  for (const pt of listed) {
    const hit = buildings.find(bd => pt.x >= bd.bb[0] && pt.x <= bd.bb[2] && pt.y >= bd.bb[1] && pt.y <= bd.bb[3]
                                  && bd.rings.some(r => pointInRing(pt.x, pt.y, r)));
    if (hit) hit.listed.push(pt.p);
  }

  progress(62, 'dates and stories from Wikidata…');
  const qids = [...new Set(buildings.map(bd => bd.tags.wikidata).filter(q => /^Q\d+$/.test(q || '')))];
  const nhleIds = [...new Set(buildings.flatMap(bd => bd.listed.map(p => String(p.ListEntry))))];
  let wd = new Map();
  try { wd = await loadWikidata(qids, nhleIds); } catch (e) { say('Wikidata unavailable: ' + e.message); }

  const rank = g => g === 'I' ? 3 : g === 'II*' ? 2 : 1;
  const feats = buildings.map(bd => {
    const t = bd.tags;
    const best = bd.listed.slice().sort((a, c) => rank(c.Grade) - rank(a.Grade))[0];
    const info = (t.wikidata && wd.get(t.wikidata)) || (best && wd.get('nhle:' + best.ListEntry)) || null;
    const osmY = parseYear(t.start_date || t['building:start_date'] || t.construction_date || t.year_of_construction);
    const wdY = wdYear(info);
    let yr = null, src = null;
    for (const [c, s] of [[wdY, 'Wikidata'], [osmY, 'OpenStreetMap']]) if (c && !c.a && !yr) { yr = c; src = s; }
    for (const [c, s] of [[wdY, 'Wikidata'], [osmY, 'OpenStreetMap']]) if (c && !yr) { yr = c; src = s; }
    const p = {
      name: t.name || info?.label || best?.Name, y: yr?.y, ya: yr?.a || undefined, ysrc: src || undefined,
      h: heightOf(t), osm: bd.osm, kind: t.building, levels: t['building:levels'],
      grade: best?.Grade, listEntry: best?.ListEntry, listName: best?.Name, listUrl: best?.hyperlink,
      qid: info?.qid || t.wikidata, image: info?.image,
      article: info?.article || (t.wikipedia?.startsWith('en:') ? 'https://en.wikipedia.org/wiki/' + t.wikipedia.slice(3) : undefined),
      architect: info?.architect || t.architect,
    };
    Object.keys(p).forEach(k => p[k] == null && delete p[k]);
    return { type:'Feature', properties:p, geometry: bd.rings.length > 1
      ? { type:'MultiPolygon', coordinates: bd.rings.map(r => [r]) } : { type:'Polygon', coordinates:[bd.rings[0]] } };
  });
  const fc = f => ({ type:'FeatureCollection', features:f });
  return { built:null, buildings:fc(feats), roads:fc(roads), water:fc(water), parks:fc(parks),
    listed:fc(listed.map(p => ({ type:'Feature', properties:{ g:p.p.Grade }, geometry:{ type:'Point', coordinates:[p.x, p.y] } }))) };
}

async function sparql(query){
  const d = await fetchJSON(WDQS, { method:'POST', body:'format=json&query=' + encodeURIComponent(query),
    headers:{ 'Content-Type':'application/x-www-form-urlencoded', 'Accept':'application/sparql-results+json' } });
  return d.results.bindings;
}
const WD_FIELDS = `
  OPTIONAL { ?item p:P571/psv:P571 ?iv . ?iv wikibase:timeValue ?inception ; wikibase:timePrecision ?prec . }
  OPTIONAL { ?item wdt:P18 ?image }
  OPTIONAL { ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?item wdt:P84 ?architect . ?architect rdfs:label ?architectLabel . FILTER(LANG(?architectLabel) = "en") }
  OPTIONAL { ?item rdfs:label ?label . FILTER(LANG(?label) = "en") }`;
async function loadWikidata(qids, nhleIds){
  const out = new Map();
  const take = (rows, keyFn) => rows.forEach(b => {
    const k = keyFn(b), prev = out.get(k) || {};
    const info = { qid: b.item.value.split('/').pop(), label: prev.label || b.label?.value, image: prev.image || b.image?.value,
      article: prev.article || b.article?.value, architect: prev.architect || b.architectLabel?.value,
      inception: prev.inception, prec: prev.prec };
    if (b.inception && (!prev.inception || +b.prec.value > +prev.prec)) { info.inception = b.inception.value; info.prec = +b.prec.value; }
    out.set(k, info);
  });
  const chunk = (a, n) => Array.from({ length: Math.ceil(a.length / n) }, (_, i) => a.slice(i * n, i * n + n));
  for (const c of chunk(qids, 200))
    take(await sparql(`SELECT ?item ?inception ?prec ?image ?article ?architectLabel ?label WHERE { VALUES ?item { ${c.map(q => 'wd:' + q).join(' ')} } ${WD_FIELDS} }`),
      b => b.item.value.split('/').pop());
  for (const c of chunk(nhleIds, 200))
    take(await sparql(`SELECT ?item ?nhle ?inception ?prec ?image ?article ?architectLabel ?label WHERE { VALUES ?nhle { ${c.map(n => '"' + n + '"').join(' ')} } ?item wdt:P1216 ?nhle . ${WD_FIELDS} }`),
      b => 'nhle:' + b.nhle.value);
  return out;
}
function wdYear(info){
  if (!info || !info.inception) return null;
  const m = info.inception.match(/^([+-]?\d+)-/); if (!m) return null;
  const y = parseInt(m[1], 10), p = info.prec;
  if (p >= 9) return { y, a:false };
  if (p === 8) return { y: y + 5, a:true };
  if (p === 7) return { y: (Math.ceil(y / 100) - 1) * 100 + 50, a:true };
  return null;
}

// ================= Main =================
let city, data, features = [], selectedId = null, map, playing = null, stats;

async function main(){
  progress(3, 'loading map data…');
  city = await fetchJSON(`../cities/${CITY_ID}.json`, { cache:'no-cache' }, 20000);
  try {
    data = await fetchJSON(`../data/${CITY_ID}.json`, { cache:'no-cache' }, 60000);
    progress(70, 'colouring by year…');
  } catch {
    data = await liveData(city);   // no prepared data yet: build it in the browser
  }
  features = data.buildings.features;
  if (!features.length) throw new Error('No buildings in the map data');
  let known = 0;
  features.forEach((f, i) => { f.id = i; if (f.properties.y != null) known++; f.properties.c = colourFor(f.properties); });
  stats = { total: features.length, known };

  progress(90, 'drawing the map…');
  await drawMap();
  progress(100);
  $('loader').classList.add('done');
  if (data.built) say('Data updated ' + new Date(data.built).toLocaleDateString('en-GB', { day:'numeric', month:'long', year:'numeric' }));
  updateYear();
}

function isDark(){
  const t = document.documentElement.dataset.theme;
  return t === 'dark' || (t !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
}

function drawMap(){
  return new Promise(resolve => {
    const b = city.bbox;
    map = new maplibregl.Map({
      container:'map', ...city.home, maxPitch:75,
      maxBounds:[[b.w - 0.03, b.s - 0.02], [b.e + 0.03, b.n + 0.02]],
      attributionControl:false,
      style:{ version:8, sources:{}, layers:[{ id:'bg', type:'background', paint:{ 'background-color': tok('--bg') } }],
        light:{ anchor:'map', position:[1.4, 210, 35], intensity: isDark() ? 0.35 : 0.45 } }
    });
    map.addControl(new maplibregl.AttributionControl({ compact:true, customAttribution:
      '© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors · Historic England (OGL) · Wikidata (CC0)' }), 'bottom-right');

    map.on('load', () => {
      map.addSource('osm', { type:'raster', tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize:256, maxzoom:19 });
      map.addLayer({ id:'osm', type:'raster', source:'osm', layout:{ visibility:'none' }, paint:{ 'raster-opacity':0.75, 'raster-saturation':-0.6 } });
      const key = store.get('mtKey'); if (key) addNls(key);
      map.addSource('parks', { type:'geojson', data:data.parks });
      map.addLayer({ id:'parks', type:'fill', source:'parks', paint:{ 'fill-color':tok('--park') } });
      map.addSource('water', { type:'geojson', data:data.water });
      map.addLayer({ id:'water', type:'fill', source:'water', filter:['==', ['geometry-type'], 'Polygon'], paint:{ 'fill-color':tok('--water') } });
      map.addLayer({ id:'waterline', type:'line', source:'water', filter:['==', ['geometry-type'], 'LineString'],
        paint:{ 'line-color':tok('--water'), 'line-width':['interpolate', ['linear'], ['zoom'], 13, 2, 17, 10] } });
      map.addSource('roads', { type:'geojson', data:data.roads });
      map.addLayer({ id:'roads', type:'line', source:'roads', layout:{ 'line-cap':'round', 'line-join':'round' },
        paint:{ 'line-color':tok('--road'), 'line-width':['interpolate', ['linear'], ['zoom'], 13, ['match', ['get','k'], 'major', 1.5, 0.4], 18, ['match', ['get','k'], 'major', 14, 3]] } });

      map.addSource('b', { type:'geojson', data:{ type:'FeatureCollection', features } });
      map.addLayer({ id:'b', type:'fill-extrusion', source:'b', paint:{
        'fill-extrusion-color':['case', ['boolean', ['feature-state', 'sel'], false], tok('--accent'), ['get', 'c']],
        'fill-extrusion-height':['get', 'h'], 'fill-extrusion-base':0, 'fill-extrusion-opacity':0.95,
        'fill-extrusion-vertical-gradient':true } });

      map.addSource('listed', { type:'geojson', data:data.listed });
      map.addLayer({ id:'listed', type:'circle', source:'listed', layout:{ visibility:'none' }, paint:{
        'circle-radius':['interpolate', ['linear'], ['zoom'], 14, 2.5, 18, 7],
        'circle-color':['match', ['get', 'g'], 'I', '#b3261e', 'II*', '#d9822b', '#1f5f7a'],
        'circle-stroke-color':'#fff', 'circle-stroke-width':1.2, 'circle-pitch-alignment':'map' } });

      map.on('click', 'b', e => { const f = e.features[0]; if (f) select(f.id); });
      map.on('mouseenter', 'b', () => map.getCanvas().style.cursor = 'pointer');
      map.on('mouseleave', 'b', () => map.getCanvas().style.cursor = '');
      resolve();
    });
  });
}

function addNls(key){
  if (map.getLayer('nls')) map.removeLayer('nls');
  if (map.getSource('nls')) map.removeSource('nls');
  map.addSource('nls', { type:'raster', url:`https://api.maptiler.com/tiles/uk-osgb10k1888/tiles.json?key=${encodeURIComponent(key)}`, tileSize:256 });
  map.addLayer({ id:'nls', type:'raster', source:'nls', layout:{ visibility:'none' }, paint:{ 'raster-opacity':0.85 } }, map.getLayer('parks') ? 'parks' : undefined);
}

// ================= Year slider =================
// Piecewise scale: little was built before 1700, so the early centuries get a short stretch of the track.
const SEG = [[0, 1100], [0.15, 1700], [0.45, 1850], [1, MAX_YEAR]];
function s2y(t){ for (let i = 1; i < SEG.length; i++) if (t <= SEG[i][0]) {
  const [t0, y0] = SEG[i-1], [t1, y1] = SEG[i]; return Math.round(y0 + (t - t0) / (t1 - t0) * (y1 - y0)); } return MAX_YEAR; }
function y2s(y){ for (let i = 1; i < SEG.length; i++) if (y <= SEG[i][1]) {
  const [t0, y0] = SEG[i-1], [t1, y1] = SEG[i]; return t0 + (y - y0) / (y1 - y0) * (t1 - t0); } return 1; }
const yearIn = $('year');
const curYear = () => s2y(+yearIn.value / 1000);
$('ticks').innerHTML = [1100, 1700, 1850, 1950, MAX_YEAR].map(y => `<span style="left:${(y2s(y) * 100).toFixed(1)}%">${y}</span>`).join('');

let showUnknown = true;
function updateYear(){
  const Y = curYear();
  $('yearOut').textContent = +yearIn.value === 0 ? 'by ' + Y : Y;
  if (!map || !map.getLayer('b')) return;
  const f = ['any', ['all', ['has', 'y'], ['<=', ['get', 'y'], Y]]];
  if (showUnknown) f.push(['!', ['has', 'y']]);
  map.setFilter('b', f);
  const shown = features.filter(x => x.properties.y != null ? x.properties.y <= Y : showUnknown).length;
  $('count').textContent = `${fmt(shown)} of ${fmt(stats.total)} buildings · year known for ${Math.round(stats.known / stats.total * 100)}%`;
}
yearIn.addEventListener('input', updateYear);

$('play').onclick = () => {
  if (playing) { clearInterval(playing); playing = null; $('play').textContent = '▶'; return; }
  if (+yearIn.value >= 1000) yearIn.value = 0;
  $('play').textContent = '❚❚';
  playing = setInterval(() => {
    const y = curYear(), step = y < 1700 ? 15 : y < 1850 ? 3 : 2;
    yearIn.value = Math.min(1000, Math.ceil(y2s(Math.min(MAX_YEAR, y + step)) * 1000)); updateYear();
    if (+yearIn.value >= 1000) { clearInterval(playing); playing = null; $('play').textContent = '▶'; }
  }, 70);
};

// ================= Toggles =================
function toggle(btn, fn){ btn.onclick = () => { const on = btn.getAttribute('aria-pressed') !== 'true'; btn.setAttribute('aria-pressed', on); fn(on); }; }
toggle($('tUnknown'), on => { showUnknown = on; updateYear(); });
toggle($('tListed'), on => map && map.setLayoutProperty('listed', 'visibility', on ? 'visible' : 'none'));

document.querySelectorAll('[data-base]').forEach(btn => btn.onclick = () => setBase(btn.dataset.base));
function setBase(kind){
  document.querySelectorAll('[data-base]').forEach(b => b.setAttribute('aria-pressed', b.dataset.base === kind));
  $('keyRow').hidden = !(kind === 'nls' && !store.get('mtKey'));
  if (!map) return;
  map.setLayoutProperty('osm', 'visibility', kind === 'osm' ? 'visible' : 'none');
  if (map.getLayer('nls')) map.setLayoutProperty('nls', 'visibility', kind === 'nls' ? 'visible' : 'none');
  ['parks', 'water', 'waterline', 'roads'].forEach(l => map.setLayoutProperty(l, 'visibility', kind === 'none' ? 'visible' : 'none'));
  if (kind === 'nls' && !store.get('mtKey')) say('Paste a MapTiler key to show the 1888–1913 map.');
}
$('mtSave').onclick = () => {
  const k = $('mtKey').value.trim(); if (!k) return;
  store.set('mtKey', k); addNls(k); setBase('nls'); say('');
};

// ================= Building card =================
const sheet = $('sheet');
function select(id){
  if (selectedId != null) map.setFeatureState({ source:'b', id:selectedId }, { sel:false });
  selectedId = id;
  map.setFeatureState({ source:'b', id }, { sel:true });
  const f = features[id], p = f.properties;
  const ring = f.geometry.type === 'Polygon' ? f.geometry.coordinates[0] : f.geometry.coordinates[0][0];
  const cx = ring.reduce((a, c) => a + c[0], 0) / ring.length, cy = ring.reduce((a, c) => a + c[1], 0) / ring.length;
  map.easeTo({ center:[cx, cy], zoom:Math.max(map.getZoom(), 16.5), duration:700, padding:{ bottom: innerWidth >= 760 ? 0 : sheet.offsetHeight * 0.6 } });

  $('cTitle').textContent = p.name || p.listName || 'Unnamed building';
  const rows = [];
  if (p.y != null) {
    const era = eraOf(p.y);
    rows.push(['Built', `${p.ya ? 'c. ' : ''}${p.y}<span class="pill" style="border-color:${era[3]}">${esc(era[2])}</span>`]);
    rows.push(['Date source', esc(p.ysrc)]);
  } else rows.push(['Built', '<span style="color:var(--muted)">not in open data yet</span>']);
  if (p.architect) rows.push(['Architect', esc(p.architect)]);
  if (p.grade) rows.push(['Listing', `Grade ${esc(p.grade)} listed`]);
  rows.push(['Height', `≈ ${Math.round(p.h)} m${p.levels ? ' · ' + esc(p.levels) + (p.levels === '1' ? ' storey' : ' storeys') : ''}`]);
  if (p.kind && p.kind !== 'yes') rows.push(['Type (OSM)', esc(p.kind.replace(/_/g, ' '))]);
  $('cFacts').innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');

  const links = [];
  if (p.listUrl || p.listEntry) links.push(`<a href="${esc(p.listUrl || 'https://historicengland.org.uk/listing/the-list/list-entry/' + p.listEntry)}" target="_blank" rel="noopener">Historic England list entry →</a>`);
  if (p.article) links.push(`<a href="${esc(p.article)}" target="_blank" rel="noopener">Wikipedia →</a>`);
  if (p.qid) links.push(`<a href="https://www.wikidata.org/wiki/${esc(p.qid)}" target="_blank" rel="noopener">Wikidata</a>`);
  links.push(`<a href="https://www.openstreetmap.org/${esc(p.osm)}" target="_blank" rel="noopener">OpenStreetMap</a>`);
  $('cLinks').innerHTML = links.join('');

  const img = $('cImg');
  if (p.image) { img.src = p.image.replace(/^http:/, 'https:') + '?width=640'; img.alt = p.name || ''; img.hidden = false; img.onerror = () => img.hidden = true; }
  else { img.hidden = true; img.removeAttribute('src'); }
  $('controls').hidden = true; $('card').hidden = false;
}
$('cClose').onclick = () => {
  if (selectedId != null) map.setFeatureState({ source:'b', id:selectedId }, { sel:false });
  selectedId = null; $('card').hidden = true; $('controls').hidden = false;
};
$('reset').onclick = () => map && map.easeTo({ ...city.home, duration:900 });

// ================= Legend + layout =================
$('legend').innerHTML = ERAS.map(e => `<div><i style="background:${e[3]}"></i>${e[2]}</div>`).join('')
  + `<div><i style="background:var(--unknown)"></i>no date</div>`;
const fit = () => document.documentElement.style.setProperty('--sheet-h', (innerWidth >= 760 ? 0 : sheet.offsetHeight) + 'px');
if (window.ResizeObserver) new ResizeObserver(() => requestAnimationFrame(fit)).observe(sheet);
fit(); addEventListener('resize', fit);

main().catch(e => {
  $('lpct').textContent = '—';
  $('lstep').textContent = 'Could not load the map: ' + e.message + '. Check your connection and reload the page.';
});
})();
