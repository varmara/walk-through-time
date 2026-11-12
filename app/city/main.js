// Walk Through Time, city page: Start-up: loads the city settings and the index, draws the map, opens a building or a set of places from the link.
import './util.js';
import './data.js';
import './map.js';
import './timebar.js';
import './sheet.js';
import './panels.js';
import './cards.js';
import './places.js';
import { $, CITY_ID, fetchData, fetchJSON, progress, setPeriods } from './util.js';
import { S } from './state.js';
import { areaOf, byOsm, fromIndex, loadCard, pinOf, refOf, saveActive, tiled } from './data.js';
import { drawMap } from './map.js';
import { updateYear } from './timebar.js';
import { applyLayers, drawLegend, groundNote, renderLayers } from './panels.js';
import { openRef, selectBuilding } from './cards.js';
import { showPlaces } from './places.js';

export async function main(){
  progress(5, 'loading map data…');
  S.city = await fetchJSON(`../cities/${CITY_ID}.json`);
  setPeriods(S.city.periods);
  drawLegend();
  S.data = await fetchData(`../data/${CITY_ID}.json`);
  keepOnPhone(S.data.build);
  progress(70, 'reading buildings…');
  S.features = S.data.index ? fromIndex(S.data.index) : S.data.buildings.features;
  if (!S.features.length) throw new Error('no buildings in the map data');
  let known = 0;
  let estimated = 0;
  if (!(S.data.index && S.data.index.hist)) S.features.forEach((f, i) => {     // an older file: count them here
    f.id = i;
    if (f.properties.y != null) f.properties.f === 'area' ? estimated++ : known++;
  });
  else {
    S.hist = { years: S.data.index.hist, undated: S.data.index.undated };
    estimated = S.data.index.estimated;
    known = S.features.length - S.data.index.undated - estimated;
  }
  S.stats = { total: S.features.length, known, estimated };
  groundNote();

  S.layers = (S.data.layers || []).map(L => ({ ...L, groups: (L.groups || []).map(g => Array.isArray(g) ? { key: g[0], title: g[1] } : g) }));
  S.layers.forEach(L => L.groups.forEach(g => S.groups.set(g.key, { ...g, layer: L })));
  S.layers.forEach(L => L.groups.forEach(g => (g.items || []).forEach(it => {
    const [name, bs] = typeof it[0] === 'number' ? [it[1], [it[0]]] : it;
    if (bs.length > 1) bs.filter(b => typeof b === 'number').forEach(b => (S.entitiesAt[b] = S.entitiesAt[b] || []).some(x => x.name === name) || S.entitiesAt[b].push({ name, bs }));
  })));
  S.active = new Set([...S.active].filter(k => S.groups.has(k)));
  renderLayers();

  progress(90, 'drawing the map…');
  await drawMap();
  progress(100);
  $('loader').classList.add('done');
  if (S.data.built) $('dataNote').textContent = 'Data updated ' + new Date(S.data.built).toLocaleDateString('en-GB', { day:'numeric', month:'long', year:'numeric' }) + '.';
  // ?layer=inns (from a layer's page): tick that layer
  const lq = new URLSearchParams(location.search).get('layer'), lyr = lq && S.layers.find(L => L.id === lq);
  if (lyr) { lyr.groups.filter(g => g.count > 0).forEach(g => S.active.add(g.key)); saveActive(); renderLayers(); }
  applyLayers();
  updateYear();
  // ?focus=b12,p3&name=… (from the graph page): open those places, as a set when there are several
  const q = new URLSearchParams(location.search), focus = q.get('focus'), osm = q.get('osm');
  // a shared building: the OpenStreetMap id is the lasting key; ?b= is its place in the build the link was made
  // from, used only if it still points at the same building (positions change between builds)
  const bq = q.get('b');
  if (osm) {
    let i = bq != null && +bq < S.features.length ? +bq : -1;
    if (i >= 0 && tiled()) { await loadCard(i).catch(() => {}); if (S.features[i].properties.osm !== osm) i = -1; }
    else if (i >= 0 && S.features[i].properties.osm !== osm) i = -1;
    if (i < 0) i = await byOsm(osm).catch(() => -1);
    if (i >= 0) selectBuilding(i);
  } else if (bq != null && +bq < S.features.length) selectBuilding(+bq);
  if (focus) {
    const refs = focus.split(',').map(x => x[0] === 'b' ? +x.slice(1) : x)
      .filter(r => typeof r === 'number' ? r < S.features.length : r[0] === 'p' ? S.data.pins && pinOf(r) : refOf(r));
    if (refs.length > 1) showPlaces(q.get('name') || 'Selected places', refs);
    else if (refs.length) openRef(refs[0]);
  }
}

// ================= Layout =================
export const bar = $('timebar');
export const fit = () => document.documentElement.style.setProperty('--bar-h', (bar.offsetHeight + 20) + 'px');
if (window.ResizeObserver) new ResizeObserver(() => requestAnimationFrame(fit)).observe(bar);
fit(); addEventListener('resize', fit);

main().catch(e => {
  $('lpct').textContent = '—';
  $('lstep').textContent = 'Could not load the map: ' + e.message + '. Check your connection and reload the page.';
});

// what the map has loaded stays on the phone (sw.js): repeat visits load little, and seen streets work offline
function keepOnPhone(build){
  if (!('serviceWorker' in navigator) || !build) return;
  navigator.serviceWorker.register('../sw.js').catch(() => {});
  navigator.serviceWorker.ready.then(reg => reg.active && reg.active.postMessage({ build, v: window.__v })).catch(() => {});
}
