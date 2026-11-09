// Walk Through Time: city page. Loads ../cities/<city>.json and ../data/<city>.json
// (the data file is built by the pipeline in pipeline/ and committed by GitHub Actions).
(() => {
const CITY_ID = document.body.dataset.city;
const MAX_YEAR = new Date().getFullYear();

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
const FADE = { exact: 0, approx: 0.4, century: 0.62, area: 0.74 };   // how far each precision fades towards the background
const SECTIONS = ['Stories', 'People', 'Heritage', 'Nature', 'Today'];
const AREA_TYPES = ['nnr', 'lnr', 'sssi', 'ancient', 'reserve', 'conservation'];   // areas drawn on the ground

const $ = id => document.getElementById(id);
const store = { get(k){ try { return localStorage.getItem(k); } catch { return null; } },
                set(k,v){ try { localStorage.setItem(k,v); } catch {} } };
const tok = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const say = t => { $('status').textContent = t || ''; };
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = n => n.toLocaleString('en-GB');
function progress(p, step){ $('lpct').textContent = Math.round(p) + '%'; if (step) $('lstep').textContent = step; }

async function fetchJSON(url, ms = 30000){
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    const r = await fetch(url, { cache:'no-cache', signal: ctrl.signal });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } catch (e) {
    throw new Error(e.name === 'AbortError' ? 'timed out' : e.message);
  } finally { clearTimeout(timer); }
}
// The data file is large, so read it as a stream and show how much has arrived.
async function fetchData(url){
  const r = await fetch(url, { cache:'no-cache' });
  if (!r.ok) throw new Error(r.status === 404 ? 'the data file has not been built yet' : 'HTTP ' + r.status);
  if (!r.body || !window.TextDecoder) return r.json();
  const reader = r.body.getReader(), parts = [];
  let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parts.push(value); got += value.length;
    progress(5 + Math.min(60, got / 4e5), `loading map data… ${(got / 1e6).toFixed(1)} MB`);
  }
  const all = new Uint8Array(got);
  let o = 0; for (const p of parts) { all.set(p, o); o += p.length; }
  progress(66, 'reading buildings…');
  return JSON.parse(new TextDecoder().decode(all));
}

// ================= Colour and date wording =================
function hexToRgb(h){ const n = parseInt(h.slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255]; }
function mix(a, b, t){ const A = hexToRgb(a), B = hexToRgb(b);
  return '#' + A.map((v, i) => Math.round(v + (B[i] - v) * t).toString(16).padStart(2, '0')).join(''); }
const eraOf = y => ERAS.find(e => y >= e[0] && y <= e[1]);
function colourFor(p){
  if (p.y == null) return tok('--unknown');
  return mix(eraOf(p.y)[3], tok('--bg'), FADE[p.f] || 0);
}
function ordinal(n){ const s = ['th','st','nd','rd'], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }
function dateText(y, f, per){
  if (f === 'area') return 'probably ' + (per || y);
  if (f === 'century') return `${ordinal(Math.floor(y / 100) + 1)} century`;
  return (f === 'approx' ? 'c. ' : '') + y;
}
const PRECISION = { exact: 'exact year', approx: 'approximate', century: 'only the century is known', area: 'estimate for the area' };

// ================= State =================
let city, data, features = [], selectedId = null, map, playing = null, stats;
let layers = [];                 // layer metadata from the data file
const groups = new Map();        // group key -> { key, title, count, items, layer }
let active = new Set();          // ticked group keys
const entitiesAt = {};           // building index -> [{name, bs}] for people and stories with several places
try { active = new Set(JSON.parse(store.get('layers:' + CITY_ID) || '[]')); } catch {}
const saveActive = () => store.set('layers:' + CITY_ID, JSON.stringify([...active]));
const isArea = key => groups.get(key)?.layer.kind === 'areas';

async function main(){
  progress(5, 'loading map data…');
  city = await fetchJSON(`../cities/${CITY_ID}.json`);
  data = await fetchData(`../data/${CITY_ID}.json`);
  progress(70, 'colouring by year…');
  features = data.buildings.features;
  if (!features.length) throw new Error('no buildings in the map data');
  let known = 0;
  let estimated = 0;
  features.forEach((f, i) => {
    f.id = i;
    if (f.properties.y != null) f.properties.f === 'area' ? estimated++ : known++;
    f.properties.c = colourFor(f.properties);
  });
  stats = { total: features.length, known, estimated };

  layers = (data.layers || []).map(L => ({ ...L, groups: (L.groups || []).map(g => Array.isArray(g) ? { key: g[0], title: g[1] } : g) }));
  layers.forEach(L => L.groups.forEach(g => groups.set(g.key, { ...g, layer: L })));
  layers.forEach(L => L.groups.forEach(g => (g.items || []).forEach(it => {
    const [name, bs] = typeof it[0] === 'number' ? [it[1], [it[0]]] : it;
    if (bs.length > 1) bs.filter(b => typeof b === 'number').forEach(b => (entitiesAt[b] = entitiesAt[b] || []).some(x => x.name === name) || entitiesAt[b].push({ name, bs }));
  })));
  active = new Set([...active].filter(k => groups.has(k)));
  renderLayers();

  progress(90, 'drawing the map…');
  await drawMap();
  progress(100);
  $('loader').classList.add('done');
  if (data.built) $('dataNote').textContent = 'Data updated ' + new Date(data.built).toLocaleDateString('en-GB', { day:'numeric', month:'long', year:'numeric' }) + '.';
  applyLayers();
  updateYear();
}

function isDark(){
  const t = document.documentElement.dataset.theme;
  return t === 'dark' || (t !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
}

// ================= Map =================
function buildingColour(){
  const base = ['case', ['boolean', ['feature-state', 'sel'], false], tok('--accent'),
    ['boolean', ['feature-state', 'hl'], false], tok('--hl'), ['get', 'c']];
  if (places) return ['case', ['boolean', ['feature-state', 'sel'], false], tok('--accent'),
    ['boolean', ['feature-state', 'hl'], false], tok('--hl'), tok('--ghost')];   // only this person's places stand out
  const keys = [...active].filter(k => !isArea(k));
  if (!keys.length) return base;
  const inLayer = ['any', ...keys.map(k => ['in', ',' + k + ',', ['coalesce', ['get', 'L'], '']])];
  // in a ticked layer: era colour when dated, a strong neutral when not (plain grey would vanish into the faded rest)
  return ['case', ['boolean', ['feature-state', 'sel'], false], tok('--accent'),
    ['boolean', ['feature-state', 'hl'], false], tok('--hl'),
    inLayer, ['case', ['has', 'y'], ['get', 'c'], tok('--marked')], tok('--ghost')];
}
const natureColour = () => ['match', ['get', 't'], ...AREA_TYPES.flatMap(t => [t, tok('--n-' + t)]), tok('--n-reserve')];

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
      '© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors · Historic England (OGL) · Natural England (OGL) · Wikidata (CC0) · Wikipedia (CC BY-SA)' }), 'bottom-right');

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

      map.addSource('nature', { type:'geojson', data: data.nature || { type:'FeatureCollection', features:[] } });
      map.addLayer({ id:'nature-fill', type:'fill', source:'nature', layout:{ visibility:'none' },
        paint:{ 'fill-color':natureColour(), 'fill-opacity':0.32 } });
      map.addLayer({ id:'nature-line', type:'line', source:'nature', layout:{ visibility:'none' },
        paint:{ 'line-color':natureColour(), 'line-width':2, 'line-dasharray':[2, 1] } });

      map.addSource('b', { type:'geojson', data:{ type:'FeatureCollection', features } });
      map.addLayer({ id:'b', type:'fill-extrusion', source:'b', paint:{
        'fill-extrusion-color':buildingColour(),
        'fill-extrusion-height':['get', 'h'], 'fill-extrusion-base':0, 'fill-extrusion-opacity':0.95,
        'fill-extrusion-vertical-gradient':true } });

      map.addSource('storypins', { type:'geojson', data: data.pins || { type:'FeatureCollection', features:[] } });
      map.addLayer({ id:'storypins', type:'circle', source:'storypins', layout:{ visibility:'none' }, paint:{
        'circle-radius':['interpolate', ['linear'], ['zoom'], 13, 4, 18, 9], 'circle-color':tok('--marked'),
        'circle-stroke-color':'#fff', 'circle-stroke-width':2, 'circle-pitch-alignment':'map' } });
      map.addSource('places', { type:'geojson', data:{ type:'FeatureCollection', features:[] },
        cluster:true, clusterRadius:44, clusterMaxZoom:18 });
      // invisible layer: keeps the clustered source loaded so the HTML pins can read it
      map.addLayer({ id:'places-probe', type:'circle', source:'places', paint:{ 'circle-radius':1, 'circle-opacity':0 } });
      map.on('moveend', drawPins); map.on('sourcedata', e => { if (e.sourceId === 'places' && e.isSourceLoaded) drawPins(); });

      map.on('click', e => {
        if (e.originalEvent && e.originalEvent.target.closest('.pin')) return;
        const pinHit = map.getLayoutProperty('storypins', 'visibility') === 'visible'
          && map.queryRenderedFeatures([[e.point.x - 8, e.point.y - 8], [e.point.x + 8, e.point.y + 8]], { layers:['storypins'] })[0];
        if (pinHit) return showPin(pinHit.properties);
        const hit = map.queryRenderedFeatures(e.point, { layers:['b'] })[0];
        if (hit) return selectBuilding(hit.id);
        const area = map.getLayer('nature-fill') && map.getLayoutProperty('nature-fill', 'visibility') === 'visible'
          && map.queryRenderedFeatures(e.point, { layers:['nature-fill'] })[0];
        if (area) showArea(area.properties);
      });
      // start the credits folded behind their (i) button: on a phone they would cover the map
      document.querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show');
      map.on('rotate', turnNeedle); turnNeedle();
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
  $('count').textContent = `${fmt(shown)} of ${fmt(stats.total)} buildings · year known for ${Math.round(stats.known / stats.total * 100)}%`
    + (stats.estimated ? `, estimated for ${Math.round(stats.estimated / stats.total * 100)}%` : '');
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

// ================= The sheet =================
const sheet = $('sheet');
let sheetKind = null;
function openSheet(kind, title){
  sheetKind = kind;
  $('sTitle').textContent = title;
  ['pLayers', 'pMap', 'pCard'].forEach(id => $(id).hidden = true);
  $({ layers:'pLayers', map:'pMap', card:'pCard' }[kind]).hidden = false;
  sheet.hidden = false; sheet.scrollTop = 0;
  $('bLayers').setAttribute('aria-expanded', kind === 'layers');
  $('bMap').setAttribute('aria-expanded', kind === 'map');
}
function closeSheet(){
  sheet.hidden = true; sheetKind = null;
  $('bLayers').setAttribute('aria-expanded', false);
  $('bMap').setAttribute('aria-expanded', false);
  if (places) { setPlace(places.i, false); return; }   // back to the places strip, its building still selected
  if (selectedId != null && map) { map.setFeatureState({ source:'b', id:selectedId }, { sel:false }); selectedId = null; }
}
$('sClose').onclick = closeSheet;
addEventListener('keydown', e => { if (e.key === 'Escape' && !sheet.hidden) closeSheet(); });
$('bLayers').onclick = () => sheetKind === 'layers' ? closeSheet() : openSheet('layers', 'Layers');
$('bMap').onclick = () => sheetKind === 'map' ? closeSheet() : openSheet('map', 'Map');
$('bHome').onclick = () => map && map.easeTo({ ...city.home, duration:900 });
$('bNorth').onclick = () => map && map.easeTo({ bearing: 0, duration: 600 });
// the needle points to north as the map turns
const turnNeedle = () => { $('needle').style.transform = `rotate(${-map.getBearing()}deg)`; };

// ================= Layers panel =================
function renderLayers(){
  const html = [];
  for (const sec of SECTIONS) {
    const Ls = layers.filter(L => L.section === sec && L.groups.some(g => g.count > 0));
    if (!Ls.length) continue;
    html.push(`<div class="section"><div class="seclbl">${esc(sec)}</div>`);
    for (const L of Ls) {
      const gs = L.groups.filter(g => g.count > 0);
      const single = gs.length === 1;
      if (!single) html.push(`<div class="lrow" style="cursor:default;border-bottom:0;padding-bottom:2px"><b>${esc(L.title)}</b>
        <button class="more" data-info="${esc(L.id)}" aria-label="About ${esc(L.title)}" aria-expanded="false">ⓘ</button></div>
        <div class="linfo" id="info-${esc(L.id)}" hidden>${infoHtml(L, null)}</div>`);
      for (const g of gs) {
        const title = single ? L.title : g.title;
        const sw = L.kind === 'areas' ? `<span class="sw" style="background:var(--n-${esc(g.key)})"></span>` : '';
        html.push(`<label class="lrow"${single ? '' : ' style="padding-left:14px"'}><input type="checkbox" data-g="${esc(g.key)}"${active.has(g.key) ? ' checked' : ''}>${sw}
          <span>${esc(title)}</span><span class="n">${fmt(g.count)}</span>
          ${single || g.items ? `<button class="more" data-info="g-${esc(g.key)}" aria-label="About ${esc(title)}" aria-expanded="false">ⓘ</button>` : ''}</label>
          <div class="linfo" id="info-g-${esc(g.key)}" hidden>${infoHtml(L, single || g.items ? g : null, single)}</div>`);
      }
    }
    html.push('</div>');
  }
  $('lSections').innerHTML = html.join('');
  $('lSections').querySelectorAll('input[data-g]').forEach(cb => cb.onchange = () => {
    cb.checked ? active.add(cb.dataset.g) : active.delete(cb.dataset.g);
    saveActive(); applyLayers();
  });
  $('lSections').querySelectorAll('.find').forEach(inp => inp.oninput = () => {
    const q = inp.value.trim().toLowerCase();
    inp.nextElementSibling.querySelectorAll('.item').forEach(b => { b.hidden = q && !b.dataset.name.toLowerCase().includes(q); });
  });
  $('lSections').querySelectorAll('[data-info]').forEach(btn => btn.onclick = e => {
    e.preventDefault(); e.stopPropagation();
    const box = $('info-' + btn.dataset.info), open = box.hidden;
    box.hidden = !open; btn.setAttribute('aria-expanded', open);
  });
  $('lSections').querySelectorAll('[data-b]').forEach(btn => btn.onclick = e => {
    e.preventDefault();
    const bs = btn.dataset.b.split(',').map(parseRef);
    bs.length > 1 ? showPlaces(btn.dataset.name, bs) : openRef(bs[0]);
  });
  updateSummary();
}
function infoHtml(L, g, withIntro = true){
  const parts = [];
  if (withIntro && L.intro) parts.push(`<p>${esc(L.intro)}</p>`);
  // items are [name, [buildings]] (older data: [building, name]); long lists sort ignoring a leading "The"
  const norm = it => typeof it[0] === 'number' ? [it[1], [it[0]]] : it;
  const sortKey = n => n.replace(/^the\s+/i, '').toLowerCase();
  let items = g && g.items ? g.items.map(norm) : [];
  if (L.kind === 'rule') items = items.slice().sort((a, b) => sortKey(a[0]).localeCompare(sortKey(b[0])));
  if (items.length > 20) parts.push(`<input class="find" type="search" placeholder="Find in ${items.length} names" aria-label="Find a name in this list">`);
  if (items.length) parts.push(`<div class="items">${items.map(it => {
    const [name, bs] = it;
    return `<button class="item" data-b="${bs.join(',')}" data-name="${esc(name)}">${esc(name)}${bs.length > 1 ? `<span class="cnt">${bs.length}</span>` : ''}</button>`;
  }).join('')}</div>`);
  if (L.kind === 'stories') parts.push('<p class="src">Each entry is checked against its Wikipedia article.</p>');
  else if (L.source) parts.push(`<p class="src">Source: <a href="${esc(L.source.url)}" target="_blank" rel="noopener">${esc(L.source.title)}</a></p>`);
  return parts.join('');
}
function updateSummary(){
  const names = [...active].map(k => groups.get(k)).filter(Boolean)
    .map(g => g.layer.groups.filter(x => x.count > 0).length === 1 ? g.layer.title : g.title);
  $('lSummary').innerHTML = names.length
    ? `<b>${names.length} on:</b> ${esc(names.join(', '))}<span class="key"><i style="background:var(--marked)"></i>in the layer, no date yet</span>`
    : 'No layers on. Tick any to highlight them on the map.';
  $('lClear').hidden = !names.length;
  $('layerCount').hidden = !names.length;
  $('layerCount').textContent = names.length;
}
$('lClear').onclick = () => { active.clear(); saveActive(); renderLayers(); applyLayers(); };

function applyLayers(){
  updateSummary();
  if (!map || !map.getLayer('b')) return;
  map.setPaintProperty('b', 'fill-extrusion-color', buildingColour());
  const pinGroups = [...active].filter(k => !isArea(k));
  map.setLayoutProperty('storypins', 'visibility', pinGroups.length ? 'visible' : 'none');
  map.setFilter('storypins', ['in', ['get', 'group'], ['literal', pinGroups.length ? pinGroups : ['none']]]);
  const types = [...active].filter(isArea);
  const vis = types.length ? 'visible' : 'none';
  ['nature-fill', 'nature-line'].forEach(id => {
    map.setLayoutProperty(id, 'visibility', vis);
    map.setFilter(id, ['in', ['get', 't'], ['literal', types.length ? types : ['none']]]);
  });
}

// ================= Map panel =================
function toggle(btn, fn){ btn.onclick = () => { const on = btn.getAttribute('aria-pressed') !== 'true'; btn.setAttribute('aria-pressed', on); fn(on); }; }
toggle($('tUnknown'), on => { showUnknown = on; updateYear(); });
document.querySelectorAll('[data-base]').forEach(btn => btn.onclick = () => setBase(btn.dataset.base));
function setBase(kind){
  document.querySelectorAll('[data-base]').forEach(b => b.setAttribute('aria-pressed', b.dataset.base === kind));
  $('keyRow').hidden = !(kind === 'nls' && !store.get('mtKey'));
  if (!map) return;
  map.setLayoutProperty('osm', 'visibility', kind === 'osm' ? 'visible' : 'none');
  if (map.getLayer('nls')) map.setLayoutProperty('nls', 'visibility', kind === 'nls' ? 'visible' : 'none');
  ['parks', 'water', 'waterline', 'roads'].forEach(l => map.setLayoutProperty(l, 'visibility', kind === 'none' ? 'visible' : 'none'));
}
$('mtSave').onclick = () => {
  const k = $('mtKey').value.trim(); if (!k) return;
  store.set('mtKey', k); addNls(k); setBase('nls');
};
$('legend').innerHTML = ERAS.map(e => `<div><i style="background:${e[3]}"></i>${e[2]}</div>`).join('')
  + `<div><i style="background:var(--unknown)"></i>no date</div>`
  + `<div><i style="background:var(--marked)"></i>in a ticked layer, no date</div>`;
$('legend').insertAdjacentHTML('afterend', '<p class="note">Palest of all: no date for the building, only the period most homes in its small area were built (Council Tax records).</p>');

// ================= Cards =================
const layerTitle = id => layers.find(L => L.id === id)?.title || id;
function selectBuilding(id){
  if (selectedId != null) map.setFeatureState({ source:'b', id:selectedId }, { sel:false });
  selectedId = id;
  map.setFeatureState({ source:'b', id }, { sel:true });
  const f = features[id], p = f.properties;
  const ring = f.geometry.type === 'Polygon' ? f.geometry.coordinates[0] : f.geometry.coordinates[0][0];
  const cx = ring.reduce((a, c) => a + c[0], 0) / ring.length, cy = ring.reduce((a, c) => a + c[1], 0) / ring.length;
  map.easeTo({ center:[cx, cy], zoom:Math.max(map.getZoom(), 16.5), duration:700,
    padding: innerWidth >= 760 ? { right: 400 } : { bottom: innerHeight * 0.45 } });

  const rows = [];
  if (p.y != null) {
    const era = eraOf(p.y);
    rows.push(['Built', `${esc(dateText(p.y, p.f, p.per))}<span class="pill" style="border-color:${era[3]}">${esc(era[2])}</span>`]);
    if (p.f === 'area') rows.push(['Date', `<span class="muted">No date for this building yet. ${esc(p.sh)}% of homes in its small `
      + `area were built ${esc(p.per)}, according to Council Tax records (Valuation Office Agency).</span>`]);
    else rows.push(['Date', `${esc(PRECISION[p.f] || '')} · from ${esc(p.src)}`]);
    const alts = p.alts || (p.alt ? [p.alt] : []);
    if (alts.length) rows.push(['Other dates', alts.map(a => `${esc(dateText(a.y, a.f))} <span class="muted">from ${esc(a.src)}</span>`).join('<br>')
      + '<div class="hint">Sources disagree. They may describe different moments, such as a founding and a rebuilding.</div>']);
  } else rows.push(['Built', '<span class="muted">not in open data yet</span>']);
  if (p.architect) rows.push(['Architect', esc(p.architect)]);
  if (p.grade) rows.push(['Listing', `Grade ${esc(p.grade)} listed`]);
  rows.push(['Height', `≈ ${Math.round(p.h)} m${p.levels ? ' · ' + esc(p.levels) + (p.levels === '1' ? ' storey' : ' storeys') : ''}`]);
  if (p.kind && p.kind !== 'yes') rows.push(['Type (OSM)', esc(p.kind.replace(/_/g, ' '))]);
  $('cFacts').innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');

  const link = s => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a>`;
  $('cStories').innerHTML = (p.stories || []).map(s => `<div class="story"><div class="seclbl">${esc(layerTitle(s.layer))}</div>
    <p>${esc(s.text)}</p>${s.source ? `<p class="src">${esc(s.source.kind || 'Wikipedia')}: ${link(s.source)}${s.place ? ` · ${esc(s.place.kind || 'Wikipedia')}: ` + link(s.place) : ''}</p>` : ''}</div>`).join('');

  const many = entitiesAt[id] || [];
  $('cStories').insertAdjacentHTML('beforeend', many.map(m =>
    `<button class="textbtn allplaces" data-name="${esc(m.name)}" data-b="${m.bs.join(',')}">All ${m.bs.length} places: ${esc(m.name)} →</button>`).join(''));
  $('cStories').querySelectorAll('.allplaces').forEach(btn => btn.onclick = () => showPlaces(btn.dataset.name, btn.dataset.b.split(',').map(parseRef)));

  const links = [];
  if (p.listUrl || p.listEntry) links.push(`<a href="${esc(p.listUrl || 'https://historicengland.org.uk/listing/the-list/list-entry/' + p.listEntry)}" target="_blank" rel="noopener">Historic England list entry →</a>`);
  if (p.article) links.push(`<a href="${esc(p.article)}" target="_blank" rel="noopener">Wikipedia →</a>`);
  if (p.qid) links.push(`<a href="https://www.wikidata.org/wiki/${esc(p.qid)}" target="_blank" rel="noopener">Wikidata</a>`);
  links.push(`<a href="https://www.openstreetmap.org/${esc(p.osm)}" target="_blank" rel="noopener">OpenStreetMap</a>`);
  $('cLinks').innerHTML = links.join('');

  const img = $('cImg');
  if (p.image) { img.src = p.image.replace(/^http:/, 'https:') + '?width=640'; img.alt = p.name || ''; img.hidden = false; img.onerror = () => img.hidden = true; }
  else { img.hidden = true; img.removeAttribute('src'); }
  openSheet('card', p.name || p.listName || 'Unnamed building');
}
function showArea(p){
  const type = (groups.get(p.t) || {}).title || 'Nature area';
  $('cImg').hidden = true;
  $('cFacts').innerHTML = `<dt>Type</dt><dd>${esc(type.replace(/s$/, ''))}</dd>`
    + (p.designated ? `<dt>Designated</dt><dd>${esc(p.designated)}</dd>` : '')
    + (p.lpa ? `<dt>Council</dt><dd>${esc(p.lpa)}</dd>` : '')
    + `<dt>Source</dt><dd>${esc(p.source)}</dd>`;
  $('cStories').innerHTML = p.t === 'conservation'
    ? '<p class="src">The outline is indicative. The council\'s own conservation area maps are definitive.</p>' : '';
  $('cLinks').innerHTML = p.source === 'Natural England'
    ? '<a href="https://designatedsites.naturalengland.org.uk/" target="_blank" rel="noopener">Natural England designated sites →</a>'
    : p.source === 'Historic England'
    ? '<a href="https://historicengland.org.uk/listing/what-is-designation/local/conservation-areas/" target="_blank" rel="noopener">About conservation areas →</a>'
    : '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';
  openSheet('card', p.name);
}

// ================= Place references =================
// Layer items point at buildings (a number), pins ("p<index>": places that are not buildings, plaques on no
// building) or areas ("a<index>": conservation and nature areas).
const parseRef = x => typeof x === 'number' ? x : /^\d+$/.test(x) ? +x : x;
const isB = r => typeof r === 'number';
const pinOf = r => data.pins.features[+r.slice(1)];
const areaOf = r => data.nature.features[+r.slice(1)];
function ringsOf(g){ return g.type === 'Polygon' ? [g.coordinates[0]] : g.type === 'MultiPolygon' ? g.coordinates.map(p => p[0]) : []; }
function refCentre(r){
  if (isB(r)) return centreOf(r);
  if (r[0] === 'p') return pinOf(r).geometry.coordinates;
  const pts = ringsOf(areaOf(r).geometry).flat();
  return [pts.reduce((a, c) => a + c[0], 0) / pts.length, pts.reduce((a, c) => a + c[1], 0) / pts.length];
}
function refName(r){
  if (isB(r)) { const p = features[r].properties; return p.name || p.listName || 'Unnamed building'; }
  return (r[0] === 'p' ? pinOf(r) : areaOf(r)).properties.name;
}
function openRef(r){
  if (isB(r)) return selectBuilding(r);
  if (r[0] === 'p') return showPin(pinOf(r).properties);
  const f = areaOf(r), pts = ringsOf(f.geometry).flat();
  if (!active.has(f.properties.t)) { active.add(f.properties.t); saveActive(); renderLayers(); applyLayers(); }
  map.fitBounds([[Math.min(...pts.map(p => p[0])), Math.min(...pts.map(p => p[1]))], [Math.max(...pts.map(p => p[0])), Math.max(...pts.map(p => p[1]))]],
    { padding: innerWidth >= 760 ? { top: 60, bottom: 60, left: 60, right: 420 } : { top: 80, left: 30, right: 70, bottom: innerHeight * 0.45 }, maxZoom: 17, duration: 800 });
  showArea(f.properties);
}
function showPin(p){
  const link = s => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a>`;
  $('cImg').hidden = true;
  $('cFacts').innerHTML = `<dt>Layer</dt><dd>${esc((groups.get(p.group) || {}).title || layerTitle(p.layer))}</dd>`;
  const src = typeof p.source === 'string' ? JSON.parse(p.source) : p.source;
  const place = typeof p.place === 'string' ? JSON.parse(p.place) : p.place;
  $('cStories').innerHTML = `<div class="story"><p>${esc(p.text)}</p>${src ? `<p class="src">${esc(src.kind || 'Wikipedia')}: ${link(src)}${place ? ` · ${esc(place.kind || 'Wikipedia')}: ` + link(place) : ''}</p>` : ''}</div>`;
  $('cLinks').innerHTML = '';
  openSheet('card', p.name);
}

// ================= Places: one person or story with several buildings =================
// Numbered pins on the map (grouped into bubbles when close together) and a strip of cards that swipe
// sideways; the pin, the card and the map move together.
let places = null;             // { name, bs, i }
const pins = {};               // marker key -> maplibregl.Marker
const centreOf = b => {
  const g = features[b].geometry, ring = g.type === 'Polygon' ? g.coordinates[0] : g.coordinates[0][0];
  return [ring.reduce((a, c) => a + c[0], 0) / ring.length, ring.reduce((a, c) => a + c[1], 0) / ring.length];
};
function storyFor(b, name){
  const ss = features[b].properties.stories || [];
  return ss.find(s => s.text.includes(name) || (s.source && s.source.title === name)) || ss.find(s => s.layer === 'people') || ss[0];
}
function showPlaces(name, bs){
  closeSheet();
  clearPlaces(false);
  places = { name, bs, i: 0 };
  bs.filter(isB).forEach(b => map.setFeatureState({ source:'b', id:b }, { hl:true }));
  map.setPaintProperty('b', 'fill-extrusion-color', buildingColour());
  map.getSource('places').setData({ type:'FeatureCollection', features: bs.map((b, i) =>
    ({ type:'Feature', properties:{ n: i + 1 }, geometry:{ type:'Point', coordinates: refCentre(b) } })) });
  $('pName').textContent = name;
  $('pCards').innerHTML = bs.map((b, i) => {
    if (!isB(b)) {
      const pp = (b[0] === 'p' ? pinOf(b) : areaOf(b)).properties;
      return `<article class="pcard" data-i="${i}"><div class="pnum">${i + 1}</div><h3>${esc(refName(b))}</h3>
        ${pp.text ? `<p>${esc(pp.text)}</p>` : ''}<button class="textbtn" data-open="${b}">Details →</button></article>`;
    }
    const p = features[b].properties, st = storyFor(b, name), era = p.y != null ? eraOf(p.y) : null;
    return `<article class="pcard" data-i="${i}">
      <div class="pnum">${i + 1}</div>
      <h3>${esc(refName(b))}</h3>
      ${p.y != null ? `<div class="pmeta">${esc(dateText(p.y, p.f, p.per))}<span class="pill" style="border-color:${era[3]}">${esc(era[2])}</span></div>` : ''}
      ${st ? `<p>${esc(st.text)}</p>` : ''}
      <button class="textbtn" data-open="${b}">Details →</button></article>`;
  }).join('');
  $('pCards').querySelectorAll('[data-open]').forEach(btn => btn.onclick = () => openRef(parseRef(btn.dataset.open)));
  $('placesbar').hidden = false; $('timebar').hidden = true;
  $('pCards').scrollLeft = 0;
  setPlace(0, false);
  const pts = bs.map(refCentre), lons = pts.map(p => p[0]), lats = pts.map(p => p[1]);
  map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
    { padding: { top: 90, left: 40, right: 70, bottom: $('placesbar').offsetHeight + 40 }, maxZoom: 16.5, duration: 900 });
}
function setPlace(i, fly = true){
  if (!places) return;
  places.i = i;
  $('pCount').textContent = `${i + 1} of ${places.bs.length}`;
  if (selectedId != null) map.setFeatureState({ source:'b', id:selectedId }, { sel:false });
  selectedId = isB(places.bs[i]) ? places.bs[i] : null;
  if (selectedId != null) map.setFeatureState({ source:'b', id:selectedId }, { sel:true });
  Object.entries(pins).forEach(([k, m]) => m.getElement().classList.toggle('on', k === 'p' + (i + 1)));
  $('pCards').querySelectorAll('.pcard').forEach(c => c.classList.toggle('on', +c.dataset.i === i));
  if (fly) map.easeTo({ center: refCentre(places.bs[i]), zoom: Math.max(map.getZoom(), 16.5), duration: 700,
    padding: { bottom: $('placesbar').offsetHeight + 20 } });
}
function goToCard(i){
  const card = $('pCards').querySelector(`[data-i="${i}"]`);
  if (card) $('pCards').scrollTo({ left: card.offsetLeft - 12, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
}
let scrollTimer;
$('pCards').addEventListener('scroll', () => {
  clearTimeout(scrollTimer);
  scrollTimer = setTimeout(() => {
    const cards = [...$('pCards').querySelectorAll('.pcard')], x = $('pCards').scrollLeft;
    let best = 0;
    cards.forEach((c, i) => { if (Math.abs(c.offsetLeft - 12 - x) < Math.abs(cards[best].offsetLeft - 12 - x)) best = i; });
    if (places && best !== places.i) setPlace(best);
  }, 120);
});
$('pPrev').onclick = () => places && goToCard(Math.max(0, places.i - 1));
$('pNext').onclick = () => places && goToCard(Math.min(places.bs.length - 1, places.i + 1));
$('pClose').onclick = () => clearPlaces(true);
function clearPlaces(showTime){
  if (places) places.bs.filter(isB).forEach(b => map.setFeatureState({ source:'b', id:b }, { hl:false }));
  if (selectedId != null) { map.setFeatureState({ source:'b', id:selectedId }, { sel:false }); selectedId = null; }
  places = null;
  if (map && map.getLayer('b')) map.setPaintProperty('b', 'fill-extrusion-color', buildingColour());
  if (map && map.getSource('places')) map.getSource('places').setData({ type:'FeatureCollection', features:[] });
  Object.keys(pins).forEach(k => { pins[k].remove(); delete pins[k]; });
  $('placesbar').hidden = true;
  if (showTime) $('timebar').hidden = false;
}
function drawPins(){
  if (!map || !map.getSource('places')) return;
  const seen = new Set();
  for (const f of map.querySourceFeatures('places')) {
    const pr = f.properties, cl = pr.cluster;
    const key = cl ? 'c' + pr.cluster_id : 'p' + pr.n;
    if (seen.has(key)) continue;
    seen.add(key);
    if (!pins[key]) {
      const el = document.createElement('button');
      el.className = cl ? 'pin cluster' : 'pin';
      el.textContent = cl ? pr.point_count : pr.n;
      el.setAttribute('aria-label', cl ? `${pr.point_count} places here: zoom in` : `Place ${pr.n}`);
      el.onclick = e => {
        e.stopPropagation();
        if (cl) map.getSource('places').getClusterExpansionZoom(pr.cluster_id)
          .then(z => map.easeTo({ center: f.geometry.coordinates, zoom: z + 0.3 }));
        else goToCard(pr.n - 1);
      };
      pins[key] = new maplibregl.Marker({ element: el }).setLngLat(f.geometry.coordinates).addTo(map);
    }
    if (!cl) pins[key].getElement().classList.toggle('on', places && pr.n === places.i + 1);
  }
  Object.keys(pins).forEach(k => { if (!seen.has(k)) { pins[k].remove(); delete pins[k]; } });
}

// ================= Layout =================
const bar = $('timebar');
const fit = () => document.documentElement.style.setProperty('--bar-h', (bar.offsetHeight + 20) + 'px');
if (window.ResizeObserver) new ResizeObserver(() => requestAnimationFrame(fit)).observe(bar);
fit(); addEventListener('resize', fit);

main().catch(e => {
  $('lpct').textContent = '—';
  $('lstep').textContent = 'Could not load the map: ' + e.message + '. Check your connection and reload the page.';
});
})();
