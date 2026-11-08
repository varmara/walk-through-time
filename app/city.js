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
// How much each date precision is faded towards the background
const FADE = { exact: 0, approx: 0.4, century: 0.62 };

const $ = id => document.getElementById(id);
const store = { get(k){ try { return localStorage.getItem(k); } catch { return null; } },
                set(k,v){ try { localStorage.setItem(k,v); } catch {} } };
const tok = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const say = t => { $('status').textContent = t || ''; };
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = n => n.toLocaleString('en-GB');
function progress(p, step){ $('lpct').textContent = Math.round(p) + '%'; if (step) $('lstep').textContent = step; }

async function fetchJSON(url, ms = 60000){
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    const r = await fetch(url, { cache:'no-cache', signal: ctrl.signal });
    if (!r.ok) throw new Error(r.status === 404 ? 'the data file has not been built yet' : 'HTTP ' + r.status);
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
function dateText(y, f){
  if (f === 'century') return `${ordinal(Math.floor(y / 100) + 1)} century`;
  return (f === 'approx' ? 'c. ' : '') + y;
}
const PRECISION = { exact: 'exact year', approx: 'approximate', century: 'only the century is known' };

// ================= Main =================
let city, data, features = [], selectedId = null, map, playing = null, stats, activeLayer = null;

async function main(){
  progress(5, 'loading map data…');
  city = await fetchJSON(`../cities/${CITY_ID}.json`, 20000);
  data = await fetchData(`../data/${CITY_ID}.json`);
  progress(70, 'colouring by year…');
  features = data.buildings.features;
  if (!features.length) throw new Error('no buildings in the map data');
  let known = 0;
  features.forEach((f, i) => { f.id = i; if (f.properties.y != null) known++; f.properties.c = colourFor(f.properties); });
  stats = { total: features.length, known };
  buildLayerChips();

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

function buildingColour(){
  const base = ['case', ['boolean', ['feature-state', 'sel'], false], tok('--accent'), ['get', 'c']];
  if (!activeLayer) return base;
  const inLayer = ['any', ...activeLayer.groups.map(g => ['in', ',' + g[0] + ',', ['coalesce', ['get', 'L'], '']])];
  return ['case', ['boolean', ['feature-state', 'sel'], false], tok('--accent'), inLayer, ['get', 'c'], tok('--ghost')];
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
      '© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors · Historic England (OGL) · Wikidata (CC0) · Wikipedia (CC BY-SA)' }), 'bottom-right');

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
        'fill-extrusion-color':buildingColour(),
        'fill-extrusion-height':['get', 'h'], 'fill-extrusion-base':0, 'fill-extrusion-opacity':0.95,
        'fill-extrusion-vertical-gradient':true } });

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

// ================= Fold the panel =================
function setFolded(on){
  $('sheet').classList.toggle('folded', on);
  $('fold').setAttribute('aria-expanded', !on);
  $('fold').setAttribute('aria-label', on ? 'Show all controls' : 'Show fewer controls');
  $('fold').textContent = on ? '▴' : '▾';
  store.set('folded', on ? '1' : '0');
}
$('fold').onclick = () => setFolded(!$('sheet').classList.contains('folded'));
setFolded(store.get('folded') === '1');

// ================= Layers and stories =================
function buildLayerChips(){
  const layers = (data.layers || []).filter(L => L.count > 0);
  $('layerChips').innerHTML = layers.map(L =>
    `<button class="chip" data-layer="${esc(L.id)}" aria-pressed="false">${esc(L.title)}<small>${fmt(L.count)}</small></button>`).join('');
  $('layerChips').querySelectorAll('[data-layer]').forEach(btn => btn.onclick = () => {
    const L = layers.find(x => x.id === btn.dataset.layer);
    setLayer(activeLayer && activeLayer.id === L.id ? null : L);
  });
  $('layerSection').hidden = !layers.length;
}
function setLayer(L){
  activeLayer = L;
  $('layerChips').querySelectorAll('[data-layer]').forEach(b => b.setAttribute('aria-pressed', !!L && b.dataset.layer === L.id));
  $('layerInfo').hidden = !L;
  if (L) {
    $('lIntro').textContent = L.intro || '';
    $('lItems').innerHTML = (L.items || []).map(([b, name]) => `<button class="item" data-b="${b}">${esc(name)}</button>`).join('');
    $('lItems').querySelectorAll('[data-b]').forEach(btn => btn.onclick = () => select(+btn.dataset.b));
    $('lSource').innerHTML = L.kind === 'stories'
      ? 'Each story is checked against its Wikipedia article. Tap a building to read it.'
      : L.source ? `Source: <a href="${esc(L.source.url)}" target="_blank" rel="noopener">${esc(L.source.title)}</a>` : '';
  }
  if (map && map.getLayer('b')) map.setPaintProperty('b', 'fill-extrusion-color', buildingColour());
}

// ================= Toggles =================
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
  if (kind === 'nls' && !store.get('mtKey')) say('Paste a MapTiler key to show the 1888–1913 map.');
}
$('mtSave').onclick = () => {
  const k = $('mtKey').value.trim(); if (!k) return;
  store.set('mtKey', k); addNls(k); setBase('nls'); say('');
};

// ================= Building card =================
const sheet = $('sheet');
const layerTitle = id => (data.layers || []).find(L => L.id === id)?.title || id;
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
    rows.push(['Built', `${esc(dateText(p.y, p.f))}<span class="pill" style="border-color:${era[3]}">${esc(era[2])}</span>`]);
    rows.push(['Date', `${esc(PRECISION[p.f] || '')} · from ${esc(p.src)}`]);
    const alts = p.alts || (p.alt ? [p.alt] : []);
    if (alts.length) rows.push(['Other dates', alts.map(a => `${esc(dateText(a.y, a.f))} <span class="muted">from ${esc(a.src)}</span>`).join('<br>')
      + '<div class="hint">Sources disagree. They may describe different moments, such as a founding and a rebuilding.</div>']);
  } else rows.push(['Built', '<span style="color:var(--muted)">not in open data yet</span>']);
  if (p.architect) rows.push(['Architect', esc(p.architect)]);
  if (p.grade) rows.push(['Listing', `Grade ${esc(p.grade)} listed`]);
  rows.push(['Height', `≈ ${Math.round(p.h)} m${p.levels ? ' · ' + esc(p.levels) + (p.levels === '1' ? ' storey' : ' storeys') : ''}`]);
  if (p.kind && p.kind !== 'yes') rows.push(['Type (OSM)', esc(p.kind.replace(/_/g, ' '))]);
  $('cFacts').innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');

  $('cStories').innerHTML = (p.stories || []).map(s => `<div class="story"><div class="seclbl">${esc(layerTitle(s.layer))}</div>
    <p>${esc(s.text)}</p>${s.source ? `<p class="src">Source: <a href="${esc(s.source.url)}" target="_blank" rel="noopener">${esc(s.source.title)}, Wikipedia</a></p>` : ''}</div>`).join('');

  const links = [];
  if (p.listUrl || p.listEntry) links.push(`<a href="${esc(p.listUrl || 'https://historicengland.org.uk/listing/the-list/list-entry/' + p.listEntry)}" target="_blank" rel="noopener">Historic England list entry →</a>`);
  if (p.article) links.push(`<a href="${esc(p.article)}" target="_blank" rel="noopener">Wikipedia →</a>`);
  if (p.qid) links.push(`<a href="https://www.wikidata.org/wiki/${esc(p.qid)}" target="_blank" rel="noopener">Wikidata</a>`);
  links.push(`<a href="https://www.openstreetmap.org/${esc(p.osm)}" target="_blank" rel="noopener">OpenStreetMap</a>`);
  $('cLinks').innerHTML = links.join('');

  const img = $('cImg');
  if (p.image) { img.src = p.image.replace(/^http:/, 'https:') + '?width=640'; img.alt = p.name || ''; img.hidden = false; img.onerror = () => img.hidden = true; }
  else { img.hidden = true; img.removeAttribute('src'); }
  $('controls').hidden = true; $('card').hidden = false; sheet.scrollTop = 0;
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
