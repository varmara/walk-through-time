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
import { areaOf, byOsm, fromIndex, loadCard, parseRef, pinOf, refOf, saveActive, tiled } from './data.js';
import { drawMap } from './map.js';
import { stopPlay, updateYear } from './timebar.js';
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
  if (graphWanted()) syncGraph();                // a link to the graph (#graph): opened now, the map drawn behind
  progress(70, 'reading buildings…');
  S.features = S.data.index ? fromIndex(S.data.index) : S.data.buildings.features;
  if (!S.features.length) throw new Error('no buildings in the map data');
  // ?focus=b12,b40… (from the graph): fetch those buildings' card files now, while the map is drawn, not
  // after (a person's places can be in a dozen files)
  for (const x of (new URLSearchParams(location.search).get('focus') || '').split(',')) {
    if (/^b\d+$/.test(x) && +x.slice(1) < S.features.length) loadCard(+x.slice(1)).catch(() => {});
  }
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
  applyLayers();
  updateYear();
  mapReady();
  await openLink(new URLSearchParams(location.search), true);
  later(prefetchGraph);
}

// What a link asks the map to show: on opening the page, and from the graph (its "Show on the map" opens the same
// links in the page, without loading it again).
//   ?layer=inns              that layer ticked
//   ?group=people-architects,inns   those layer groups ticked (the rest off), their places as numbered cards
//   ?focus=b12,p3&name=…     those places (as a set when there are several)
//   ?osm=way/123&b=…         a shared building
export async function openLink(q, first){
  let ticked = false;
  const lq = q.get('layer'), lyr = lq && S.layers.find(L => L.id === lq);
  if (lyr) { lyr.groups.filter(g => g.count > 0).forEach(g => S.active.add(g.key)); ticked = true; }
  const gq = q.get('group');
  const keys = gq ? gq.split(',').filter(k => S.groups.has(k)) : [];
  if (keys.length) { S.active.clear(); keys.forEach(k => S.active.add(k)); ticked = true; }
  if (ticked) { saveActive(); renderLayers(); applyLayers(); if (!first) updateYear(); }
  // a group's places as numbered cards, person by person (or story by story), each place once
  const groupSet = keys.length && (() => {
    const seen = new Set(), refs = [];
    for (const k of keys) for (const it of S.groups.get(k).items || []) {
      const rs = typeof it[0] === 'number' ? [it[0]] : it[1];
      for (const r of rs.map(x => typeof x === 'number' ? x : parseRef(String(x)))) if (!seen.has(r)) { seen.add(r); refs.push(r); }
    }
    const title = keys.length === 1 ? S.groups.get(keys[0]).title : 'Story themes';
    return refs.length ? [title, refs] : null;
  })();
  const focus = q.get('focus'), osm = q.get('osm');
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
  if (groupSet) showPlaces(...groupSet);
  if (focus) {
    const refs = focus.split(',').map(x => x[0] === 'b' ? +x.slice(1) : x)
      .filter(r => typeof r === 'number' ? r < S.features.length : r[0] === 'p' ? S.data.pins && pinOf(r) : refOf(r));
    if (refs.length > 1) showPlaces(q.get('name') || 'Selected places', refs);
    else if (refs.length) openRef(refs[0]);
  }
}

// ================= The graph, over the map (#graph) =================
// The graph button opens it in this page (app/city/graph.js, loaded the first time): "← Map" or the phone's Back
// closes it and the map is as it was; opened again, it is as it was left. While it is open the map is hidden and
// still (nothing of it drawn); while it is closed the graph's layout and drawing stop.
const graphWanted = () => location.hash === '#graph';
let mapReady;
const mapDone = new Promise(ok => { mapReady = ok; });      // the map drawn: links can be opened
let graph = null;
const graphModule = () => graph = graph || import('./graph.js');
async function syncGraph(){
  if (graphWanted()) {
    if (!S.data) return;                         // main() opens it once the map's index is in
    stopPlay();
    S.map?.stop();
    pauseMap(true);
    document.body.classList.add('graph-open');
    (await graphModule()).showGraph({ back: closeGraph, go: fromGraph });
  } else if (graph) {
    (await graph).hideGraph();
    document.body.classList.remove('graph-open');
    pauseMap(false);
  }
}
// The map still while the graph covers it: MapLibre draws a frame whenever a tile arrives or anything moves, hidden
// or not, and on a phone those frames would slow the graph. Its frames are skipped (tiles still load) and one is
// drawn when the map shows again. (MapLibre 4's own render step, lib/maplibre-gl.js; left alone if it changes.)
function pauseMap(on){
  const m = S.map;
  if (!m || typeof m._render !== 'function') return;
  if (on && !m._paused) { m._paused = m._render; m._render = function(){ return this; }; }
  else if (!on && m._paused) { m._render = m._paused; delete m._paused; m.triggerRepaint(); }
}
// "← Map": back in history when the graph was opened from this page, or else the graph's address let go
function closeGraph(){
  if (history.state && history.state.graph) history.back();
  else { history.replaceState(null, '', location.pathname + location.search); syncGraph(); }
}
// "Show on the map": the map opens those places, at a new address, so Back returns to the graph
function fromGraph(href){
  const u = new URL(href, location.href);
  history.pushState({ link: 1 }, '', u.pathname + u.search);
  syncGraph();
  mapDone.then(() => openLink(u.searchParams));
}
$('bGraph').addEventListener('click', e => {
  e.preventDefault();
  if (!graphWanted()) history.pushState({ graph: 1 }, '', location.pathname + location.search + '#graph');
  syncGraph();
});
addEventListener('popstate', e => {
  syncGraph();
  if (!graphWanted() && e.state && e.state.link) mapDone.then(() => openLink(new URLSearchParams(location.search)));   // Forward
});
addEventListener('hashchange', syncGraph);

// Once the map is drawn and the phone idle: the graph's files fetched ahead (the browser keeps them), so the graph
// opens from the phone rather than the network. Not on a connection set to save data.
const later = f => (window.requestIdleCallback ? requestIdleCallback(f, { timeout: 8000 }) : setTimeout(f, 3000));
function prefetchGraph(){
  if (navigator.connection?.saveData || graph) return;
  const v = window.__v || '';
  for (const m of ['graphlayout', 'graph']) {
    const l = document.createElement('link'); l.rel = 'modulepreload'; l.href = `../app/city/${m}.js?v=${v}`; document.head.appendChild(l);
  }
  for (const u of [`../lib/d3.min.js?v=${v}`, `../app/graph.css?v=${v}`, `../data/${CITY_ID}-graph.json?v=${S.data.build}`]) fetch(u).catch(() => {});
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
