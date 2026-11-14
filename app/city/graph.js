// Walk Through Time: the graph, opened over the map (#graph) from the map's graph button. People and story themes,
// linked to the places where a checked story ties them (pipeline/s08_graph.py). Tap a point to see its links and
// the stories behind them, and open them on the map without leaving the page.
//
// Loaded the first time the graph opens (or fetched ahead once the map is idle: main.js). It lives in a shadow
// root, so its ids and styles (app/graph.css) cannot clash with the map's; the theme's colours still reach it.
// Laid out as Obsidian's graph view is (app/city/graphlayout.js), starting from the layout the build worked out,
// and drawn on a canvas. While it is hidden its layout and drawing stop.
import { CITY_ID } from './util.js';
import { S } from './state.js';
import { loadCard } from './data.js';
import { KINDS, DEFAULTS, prepare, visible, groupSpots, radius as radiusOf, simulation, forces as setForces,
  isDefaultLayout } from './graphlayout.js';

const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;' }[c]));
const KIND_TITLE = Object.fromEntries(KINDS);
const kindKey = k => KIND_TITLE[k] ? k : 'other';
const V = () => window.__v || '';

const MARKUP = `
<canvas id="graph" role="img" aria-label="Graph of people, story themes and places. Use the search box to find one."></canvas>
<div class="loading" id="loading">Loading the graph…</div>
<div class="top">
  <div class="bar">
    <div class="brand"><a href="./" id="back" aria-label="Back to the map"><img src="../app/logo.svg" alt="" width="20" height="20">← Map</a></div>
    <input class="find" id="find" type="search" placeholder="Find a person or place" aria-label="Find a person or place" autocomplete="off">
    <button class="gear" id="gear" aria-label="Graph settings" aria-expanded="false" aria-controls="settings"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
  </div>
</div>
<aside class="settings" id="settings" hidden aria-label="Graph settings">
  <div class="shd"><b>Graph settings</b>
    <button id="sReset" aria-label="Restore default settings" title="Restore default settings">↺</button>
    <button id="sClose" aria-label="Close settings">✕</button></div>
  <div id="settingsBody"></div>
</aside>
<div class="hint" id="hint">Each line is a checked story. A dotted ring holds folded places. Tap a point; the gear has the settings.</div>
<div class="zoom" id="zoom" aria-label="Zoom">
  <button id="zIn" aria-label="Zoom in">+</button>
  <button id="zOut" aria-label="Zoom out">−</button>
  <button id="zFit" aria-label="Show the whole graph" title="Show the whole graph"><svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M3 7V3h4M13 3h4v4M17 13v4h-4M7 17H3v-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
</div>
<div class="sheet" id="sheet" hidden>
  <button class="grab" id="grab" aria-label="Show or hide the details"><i></i></button>
  <div class="shead" id="shead"><div style="flex:1;min-width:0"><h2 id="sTitle"></h2><div class="stype" id="sType"></div></div>
    <button class="close" id="close" aria-label="Close">✕</button></div>
  <div class="sacts"><button class="go" id="go"></button><button class="more" id="more" aria-controls="links" aria-expanded="false">More</button></div>
  <div class="links" id="links"></div>
</div>`;

let host, root, $, hooks = {}, building = null, wanted = false;
let G, sel = null, sim, T = null, ns = [], ls = [], C = {}, spots = {}, shownHubs = [];
let canvas, ctx, W = 0, H = 0, frame = 0;

// ================= settings (kept in this browser) =================
const SLIDERS = {
  Display: [['fade', 'Text fade threshold', -3, 3, 0.1], ['size', 'Node size', 0.2, 4, 0.1], ['lines', 'Link thickness', 0.2, 4, 0.1]],
  Forces: [['centre', 'Center force', 0, 1, 0.01], ['repel', 'Repel force', 0, 20, 0.5],
           ['link', 'Link force', 0, 1, 0.01], ['distance', 'Link distance', 5, 250, 1],
           ['group', 'Group force', 0, 1, 0.01]],
};
const P = { ...DEFAULTS };
try { Object.assign(P, JSON.parse(localStorage.getItem('graph-settings') || '{}')); } catch {}
const off = new Set(P.off);
const saveP = () => { P.off = [...off]; try { localStorage.setItem('graph-settings', JSON.stringify(P)); } catch {} };
const radius = d => radiusOf(d, P);

// ================= opening and closing =================
// hooks: back() for "← Map", go(href) for "Show on the map" (the map opens that link in the page)
export async function showGraph(h){
  hooks = h || hooks; wanted = true;
  if (!G) building = building || build();
  await building;
  if (!wanted) return;                    // closed again while it was loading
  host.hidden = false;
  resize();
  if (sim && sim.alpha() > sim.alphaMin()) sim.restart();      // carry on settling where it stopped
  redraw();
}
export function hideGraph(){
  wanted = false;
  if (!host) return;
  host.hidden = true;
  sim?.stop();
  if (frame) { cancelAnimationFrame(frame); frame = 0; }
}
export const graphShown = () => !!host && !host.hidden;

const once = new Map();
function script(src){
  if (!once.has(src)) once.set(src, new Promise((ok, no) => {
    const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => no(new Error('could not load ' + src));
    document.head.appendChild(s);
  }));
  return once.get(src);
}

async function build(){
  if (host) {                              // tried before and failed: the data again
    $('loading').textContent = 'Loading the graph…';
    try { init(await graphData()); } catch { failed(); }
    return;
  }
  host = document.createElement('div');
  host.id = 'graphHost'; host.hidden = true;
  root = host.attachShadow({ mode: 'open' });
  $ = id => root.getElementById(id);
  const css = document.createElement('link');
  css.rel = 'stylesheet'; css.href = `../app/graph.css?v=${V()}`;
  const styled = new Promise(ok => { css.onload = css.onerror = ok; });
  root.appendChild(css);
  const t = document.createElement('template'); t.innerHTML = MARKUP; root.appendChild(t.content);
  document.body.appendChild(host);
  const data = graphData();
  await Promise.all([styled, script(`../lib/d3.min.js?v=${V()}`)]);
  canvas = $('graph'); ctx = canvas.getContext('2d');
  T = d3.zoomIdentity;
  wire();
  try { init(await data); } catch { failed(); }
}
// the graph's data, from the same build as the map's (main.js prefetches the same address)
export const graphUrl = () => `../data/${CITY_ID}-graph.json?v=${S.data?.build || V()}`;
const graphData = () => fetch(graphUrl()).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
function failed(){ $('loading').textContent = 'The graph could not be loaded. Check your connection and open it again.'; building = null; }

// A tapped person's or theme's places: their card files fetched now, so the map has them when it opens
function cardsFor(id){
  if (!S.features || !S.data?.tiles?.chunk || !id || id.startsWith('g:')) return;
  const n0 = G.byId.get(id); if (!n0) return;
  const ids = (n0.type === 'place' ? [id] : [...n0.nb].filter(x => G.byId.get(x)?.type === 'place'))
    .filter(x => /^b\d+$/.test(x)).map(x => +x.slice(1)).filter(i => i < S.features.length);
  const files = new Set(ids.map(i => Math.floor(i / S.data.tiles.chunk)));
  if (files.size > 30) return;                   // a whole group: the map does not need its cards to open
  for (const i of ids) loadCard(i).catch(() => {});
}

// ================= the canvas =================
function resize(){
  if (!canvas) return;
  const dpr = devicePixelRatio || 1;
  W = innerWidth; H = innerHeight;
  canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  redraw();
}
// colours from app/theme.css, read again when the theme changes
function colours(){
  const cs = getComputedStyle(document.documentElement), v = n => cs.getPropertyValue(n).trim();
  C = { edge: v('--edge'), ink: v('--ink'), bg: v('--bg'), muted: v('--muted'), accent: v('--accent'), sans: v('--sans') || 'sans-serif',
        kind: Object.fromEntries(KINDS.map(([k]) => [k, v('--k-' + k)])) };
  redraw();
}
const redraw = () => { if (!frame && host && !host.hidden) frame = requestAnimationFrame(paint); };

// the buttons and panels that do not need the data
function wire(){
  matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', colours);
  addEventListener('resize', () => { if (graphShown()) { resize(); placeZoom(); } });
  $('back').onclick = e => { e.preventDefault(); hooks.back?.(); };
  $('gear').onclick = () => { const open = $('settings').hidden; $('settings').hidden = !open; $('gear').setAttribute('aria-expanded', open); };
  $('sClose').onclick = () => { $('settings').hidden = true; $('gear').setAttribute('aria-expanded', 'false'); };
  $('sReset').onclick = () => { Object.assign(P, DEFAULTS); off.clear(); saveP(); panel(); draw(); };
  $('more').onclick = e => { e.stopPropagation(); drawer($('sheet').classList.contains('peek')); };
  $('grab').onclick = () => drawer($('sheet').classList.contains('peek'));
  $('shead').onclick = e => { if (e.target.closest('button')) return; if ($('sheet').classList.contains('peek')) drawer(true); };
  let y0 = null;
  const start = e => { y0 = e.touches[0].clientY; };
  const end = e => {
    if (y0 == null) return;
    const dy = e.changedTouches[0].clientY - y0; y0 = null;
    const peek = $('sheet').classList.contains('peek');
    if (dy < -30 && peek) drawer(true);
    else if (dy > 30) peek ? select(null) : drawer(false);
  };
  for (const el of [$('grab'), $('shead')]) { el.addEventListener('touchstart', start, { passive: true }); el.addEventListener('touchend', end); }
  // Escape: the settings closed, or else the tapped point let go
  addEventListener('keydown', e => {
    if (e.key !== 'Escape' || !graphShown() || !G) return;
    if (!$('settings').hidden) $('sClose').click(); else if (sel) select(null);
  });
}

function init(data){
  const began = performance.now();
  G = prepare(data);
  $('loading').hidden = true;
  const byId = G.byId;
  G.present = new Set(G.nodes.map(n => n.type));
  // laid out in the build (pipeline/graph_layout.mjs) with the default settings: started from there
  const laidOut = G.nodes.some(n => n.x != null);
  // a group point for each colour (each kind of person, and the story themes): tap it to pick out the whole
  // group, and open it on the map as that layer. Not part of the layout: it sits in the middle of its group.
  G.hubs = [];
  for (const [k, title] of KINDS) {
    const members = G.nodes.filter(n => n.type === k);
    if (k === 'place' || members.length < 2) continue;
    const h = { id: 'g:' + k, type: k, label: title, hub: true, members, nb: new Set(members.map(m => m.id)), deg: 0 };
    h.lit = new Set([...h.nb, ...members.flatMap(m => [...m.nb])]);     // its people and their places, lit when it is tapped
    G.hubs.push(h); byId.set(h.id, h);
  }

  const sel$ = d3.select(canvas);
  // a person's own pan or zoom (not the page's): from then on the page does not fit the graph by itself
  const zoom = d3.zoom().scaleExtent([0.1, 8]).clickDistance(6).on('zoom', e => { T = e.transform; if (e.sourceEvent) G.moved = true; redraw(); });
  // dragging a point moves it; dragging elsewhere pans (the drag starts only on a point)
  const drag = d3.drag().container(canvas).clickDistance(6).subject(e => { const n = pick(e.x, e.y); return n && !n.hub && { n, x: e.x, y: e.y }; })
    .on('start', e => { if (!e.active) sim.alphaTarget(0.1).restart(); const n = e.subject.n; n.fx = n.x; n.fy = n.y; })
    .on('drag', e => { const [x, y] = T.invert([e.x, e.y]), n = e.subject.n; n.fx = x; n.fy = y; G.moved = true; })
    .on('end', e => { if (!e.active) sim.alphaTarget(0); const n = e.subject.n; n.fx = n.fy = null; });
  sel$.call(drag).call(zoom).on('dblclick.zoom', null);
  canvas.addEventListener('click', e => { const n = pick(e.offsetX, e.offsetY); select(n ? n.id : null); if (n) G.reveal(n); });
  // buttons as well as pinching: they zoom about the selected point when there is one, or else the middle
  const step = f => {
    const n = sel && G.byId.get(sel);
    const at = n && n.x != null && ns.includes(n) ? T.apply([n.x, n.y]) : [W / 2, H / 2];
    sel$.transition().duration(250).call(zoom.scaleBy, f, at);
  };
  $('zIn').onclick = () => step(1.6);
  $('zOut').onclick = () => step(1 / 1.6);
  $('zFit').onclick = () => G.fit();
  // a tapped point the sheet would cover (on a phone, the bottom half): the graph slides up to show it
  G.reveal = n => requestAnimationFrame(() => {
    if (!n || n.x == null || $('sheet').hidden || W >= 760) return;
    const [, sy] = T.apply([n.x, n.y]), room = H - $('sheet').offsetHeight - 30;
    if (sy > 70 && sy < room) return;
    sel$.transition().duration(350).call(zoom.translateBy, 0, (70 + room) / 2 / T.k - sy / T.k);
  });
  G.zoomTo = (x, y) => sel$.transition().duration(600).call(zoom.transform,
    d3.zoomIdentity.translate(W / 2, H * (W >= 760 ? 0.5 : 0.3)).scale(Math.max(T.k, 1.6)).translate(-x, -y));
  G.fit = (now) => {
    if (!ns.length) return;
    const xs = ns.map(n => n.x), ys = ns.map(n => n.y), top = 70;
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const k = Math.max(0.1, Math.min(3, 0.9 * Math.min(W / (x1 - x0 || 1), (H - top - 40) / (y1 - y0 || 1))));
    const t = d3.zoomIdentity.translate(W / 2, top + (H - top - 40) / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
    now ? sel$.call(zoom.transform, t) : sel$.transition().duration(700).call(zoom.transform, t);
  };

  let fitted = false;
  sim = simulation(d3).on('tick', redraw).on('end', () => {
    canvas.dataset.settled = Math.round(performance.now() - began);     // for the page's checks: how long it took
    if (!fitted) { fitted = true; if (!sel && !G.moved) G.fit(); }
  });
  panel();
  colours(); resize();
  const asBuilt = laidOut && isDefaultLayout(P, off);
  if (asBuilt) fitted = true;
  draw(false, asBuilt);
  if (asBuilt) G.fit(true);                         // already settled: shown at once, fitted to the screen
  else {
    // a head start: most of the layout worked out before the first picture (up to a third of a second, so a slow
    // phone is not left blank), then fitted to the screen, and the rest settles in view
    const t0 = performance.now();
    while (sim.alpha() > 0.08 && performance.now() - t0 < 330) sim.tick();
    G.fit(true);
  }

  $('find').oninput = () => {
    const q = $('find').value.trim().toLowerCase();
    if (q.length < 2) return;
    // people and themes before places; a word that starts with the text before a match inside a word
    const score = n => (n.type === 'place' ? 2 : 0) + (n.label.toLowerCase().startsWith(q) ? 0 : new RegExp('\\b' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).test(n.label.toLowerCase()) ? 0.5 : 1);
    const n = G.nodes.filter(n => !off.has(n.type) && n.label.toLowerCase().includes(q)).sort((a, b) => score(a) - score(b) || b.deg - a.deg)[0];
    if (n) { select(n.id); setTimeout(() => G.zoomTo(n.x, n.y), 50); }
  };
  $('find').onkeydown = e => { if (e.key === 'Enter') $('find').blur(); };
  $('close').onclick = () => select(null);
  // ?node=<id> (an old link to the graph page): that point picked out
  const start = new URLSearchParams(location.search).get('node');
  if (start && byId.has(start)) setTimeout(() => { select(start); const n = byId.get(start); G.zoomTo(n.x, n.y); }, 300);
}

// ================= what is shown =================
// the point whose folded places are spread out: the selected one, or the owner of a selected folded place
const spread = () => { const n = sel && G.byId.get(sel); return !n || n.hub ? null : n.owner && P.fold ? n.owner.id : n.id; };
let spreadNow;
function draw(gentle, asBuilt){
  spreadNow = spread();
  ({ ns, ls } = visible(G, P, off, spreadNow, sel));
  spots = groupSpots(d3, ns);
  sim.nodes(ns); sim.force('link').links(ls);
  setForces(sim, P, spots);
  canvas.dataset.points = ns.length;          // for the page's checks (tests/page/smoke.cjs)
  canvas.inspect = () => ({ t: [T.x, T.y, T.k], nodes: ns.map(n => [n.id, n.x, n.y]) });
  // a tap spreading a point's places: only a nudge; a change of settings: a shake
  if (asBuilt) { sim.stop(); sim.alpha(0); sim.on('end')(); }     // the build's layout: already settled, so nothing to run
  else sim.alpha(gentle ? 0.12 : 0.6).restart();
  redraw();
}

// the point under a finger or the pointer, if any (a target of at least 14 px round it)
const screenR = d => Math.max(1.5, radius(d) * T.k);
function pick(x, y){
  for (const h of shownHubs) if (Math.hypot(h.sx - x, h.sy - y) < 22) return h;      // group points first
  let best = null, bd = Infinity;
  for (const n of ns) {
    const [sx, sy] = T.apply([n.x, n.y]), d = Math.hypot(sx - x, sy - y), r = Math.max(14, screenR(n) + 6);
    if (d < r && d < bd) { best = n; bd = d; }
  }
  return best;
}

// Names fade in as you zoom (Obsidian's text fade threshold moves where). The selected point and its neighbours
// are always named; an unnamed building only when it is the one tapped.
const UNNAMED = /^Unnamed /;
function nameAlpha(d, near){
  if (d.id === sel) return 1;
  if (UNNAMED.test(d.label)) return 0;
  if (near.has(d.id)) return 1;
  const z = Math.log2(T.k) - P.fade + (d.deg >= 6 ? 1 : d.deg >= 3 ? 0.5 : 0);    // well-linked points sooner
  return Math.max(0, Math.min(1, z + 0.4));
}

function paint(){
  frame = 0;
  if (!G || host.hidden) return;
  ctx.clearRect(0, 0, W, H);
  const hubSel = !!sel && sel.startsWith('g:');
  const near = sel ? (hubSel ? G.byId.get(sel).lit : G.byId.get(sel).nb) : new Set(), focus = !!sel, lw = P.lines;
  // lines (the selection's on top, darker)
  for (const pass of focus ? [0, 1] : [0]) {
    for (const l of ls) {
      const on = focus && (l.s === sel || l.t === sel || (hubSel && (G.byId.get(sel).nb.has(l.s) || G.byId.get(sel).nb.has(l.t))));
      if (pass !== (on ? 1 : 0)) continue;
      const [x1, y1] = T.apply([l.source.x, l.source.y]), [x2, y2] = T.apply([l.target.x, l.target.y]);
      if (Math.max(x1, x2) < 0 || Math.min(x1, x2) > W || Math.max(y1, y2) < 0 || Math.min(y1, y2) > H) continue;
      ctx.globalAlpha = focus && !on ? 0.12 : 1;
      ctx.strokeStyle = on ? C.accent : C.edge;
      ctx.lineWidth = (on ? 1.6 : 1) * lw * Math.min(1.5, Math.max(0.4, T.k));
      ctx.setLineDash(l.how === 'mention' ? [3, 3] : []);
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    }
  }
  ctx.setLineDash([]);
  // points, then their names on top
  const names = [];
  for (const d of ns) {
    const [x, y] = T.apply([d.x, d.y]), r = screenR(d);
    if (x < -60 || x > W + 60 || y < -60 || y > H + 60) continue;
    const lit = !focus || d.id === sel || near.has(d.id);
    ctx.globalAlpha = lit ? 1 : 0.15;
    ctx.fillStyle = C.kind[kindKey(d.type)] || C.muted;
    ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.fill();
    if (d.id === sel) { ctx.lineWidth = 2.5; ctx.strokeStyle = C.ink; ctx.stroke(); }
    if (d.folds) {             // a ring: places folded into this point
      ctx.beginPath(); ctx.arc(x, y, r + Math.max(2, r * 0.25), 0, 2 * Math.PI);
      ctx.lineWidth = 1.2; ctx.strokeStyle = C.kind.place; ctx.setLineDash([2, 2]); ctx.stroke(); ctx.setLineDash([]);
    }
    // a place named as its person (a plaque's "George Henry Hurt"): one name is enough, the person's
    const same = d.owner && d.id !== sel && d.label === d.owner.label && !d.owner.hidden;
    const a = same ? 0 : nameAlpha(d, near) * (lit ? 1 : 0.3);
    if (a > 0.02) names.push([d, x, y + r + 9, a]);
  }
  // group points: in the middle of their group's points on screen, with the group's name and size
  shownHubs = [];
  const hubBoxes = [];
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
  for (const h of G.hubs) {
    if (off.has(h.type)) continue;
    const vis = h.members.filter(m => !m.hidden && m.x != null);
    if (vis.length < 2) continue;
    const [x, y] = T.apply([d3.mean(vis, m => m.x), d3.mean(vis, m => m.y)]);
    h.sx = x; h.sy = y; shownHubs.push(h);
    if (x < -80 || x > W + 80 || y < -80 || y > H + 80) continue;
    const on = sel === h.id, dim = focus && !on && !near.has(h.id);
    ctx.globalAlpha = dim ? 0.25 : 1;
    ctx.beginPath(); ctx.arc(x, y, on ? 13 : 11, 0, 2 * Math.PI);
    ctx.fillStyle = C.bg; ctx.fill();
    ctx.lineWidth = on ? 4 : 3; ctx.strokeStyle = C.kind[kindKey(h.type)]; ctx.stroke();
    ctx.beginPath(); ctx.arc(x, y, 4, 0, 2 * Math.PI); ctx.fillStyle = C.kind[kindKey(h.type)]; ctx.fill();
    ctx.font = `700 13px ${C.sans}`;
    const text = `${h.label} · ${h.members.length}`, w = ctx.measureText(text).width + 8;
    // the name above the ring, or below it if another group's name is there already
    const hit = b => hubBoxes.some(t => b[0] < t[2] && b[2] > t[0] && b[1] < t[3] && b[3] > t[1]);
    let ty = y - 22;
    if (hit([x - w / 2, ty - 9, x + w / 2, ty + 9])) ty = y + 24;
    ctx.lineWidth = 4; ctx.strokeStyle = C.bg; ctx.strokeText(text, x, ty);
    ctx.fillStyle = C.ink; ctx.fillText(text, x, ty);
    hubBoxes.push([x - w / 2, ty - 9, x + w / 2, ty + 9], [x - 14, y - 14, x + 14, y + 14]);
  }
  ctx.globalAlpha = 1;
  // names under their points, none over another: the selection's first, then its neighbours', then the
  // best-linked; a name that would overlap one already drawn is left out
  const rank = d => d.id === sel ? 0 : near.has(d.id) ? 1 : 2;
  names.sort((p, q) => rank(p[0]) - rank(q[0]) || (q[0].deg + (q[0].folds || 0)) - (p[0].deg + (p[0].folds || 0)));
  const taken = hubBoxes.slice();
  for (const [d, x, y, a] of names) {
    ctx.font = `${d.id === sel ? 600 : 400} 12px ${C.sans}`;
    const text = d.label + (d.folds ? ` · ${d.folds}` : ''), w = ctx.measureText(text).width + 6;
    const box = [x - w / 2, y - 8, x + w / 2, y + 8];
    if (d.id !== sel && taken.some(t => box[0] < t[2] && box[2] > t[0] && box[1] < t[3] && box[3] > t[1])) continue;
    taken.push(box);
    ctx.globalAlpha = a;
    ctx.lineWidth = 3; ctx.strokeStyle = C.bg; ctx.strokeText(text, x, y);
    ctx.fillStyle = d.type === 'place' ? C.muted : C.ink; ctx.fillText(text, x, y);
  }
  ctx.globalAlpha = 1;
}

// ================= the settings panel (Filters, Groups, Display, Forces) =================
const openSections = new Set(['Filters']);      // the others folded, so all four headings show on a phone
function panel(){
  const fmt = (v, step) => step < 1 ? (+v).toFixed(step < 0.1 ? 2 : 1) : String(v);
  const toggle = (k, t, on) => `<label class="tg"><span>${t}</span><input type="checkbox" role="switch" data-k="${k}"${on ? ' checked' : ''}><i></i></label>`;
  const slider = ([k, t, lo, hi, step]) => `<label class="sl"><span>${t}<output id="o-${k}">${fmt(P[k], step)}</output></span>
    <input type="range" data-s="${k}" min="${lo}" max="${hi}" step="${step}" value="${P[k]}"></label>`;
  const section = (name, body) => `<details class="sec"${openSections.has(name) ? ' open' : ''} data-sec="${name}"><summary>${name}</summary><div class="body">${body}</div></details>`;
  const groups = KINDS.filter(([k]) => G.present.has(k)).map(([k, t]) =>
    `<label class="tg"><span><i class="dot" style="background:var(--k-${k})"></i>${t}</span><input type="checkbox" role="switch" data-kind="${k}"${off.has(k) ? '' : ' checked'}><i></i></label>`).join('');
  $('settingsBody').innerHTML =
    section('Filters', toggle('fold', 'Fold places with one link', P.fold) + toggle('orphans', 'Orphans', P.orphans)
      + '<p class="note">Folded places show as a dotted ring and a count; tap the point to spread them out.</p>')
    + section('Groups', groups)
    + section('Display', SLIDERS.Display.map(slider).join(''))
    + section('Forces', SLIDERS.Forces.map(slider).join(''));
  const body = $('settingsBody');
  body.querySelectorAll('details').forEach(d => d.ontoggle = () => { d.open ? openSections.add(d.dataset.sec) : openSections.delete(d.dataset.sec); });
  body.querySelectorAll('[data-k]').forEach(i => i.onchange = () => { P[i.dataset.k] = i.checked; saveP(); draw(); });
  body.querySelectorAll('[data-kind]').forEach(i => i.onchange = () => { i.checked ? off.delete(i.dataset.kind) : off.add(i.dataset.kind); saveP(); draw(); });
  const steps = Object.fromEntries([...SLIDERS.Display, ...SLIDERS.Forces].map(s => [s[0], s[4]]));
  body.querySelectorAll('[data-s]').forEach(i => i.oninput = () => {
    const k = i.dataset.s; P[k] = +i.value; root.getElementById('o-' + k).textContent = fmt(P[k], steps[k]); saveP();
    if (k === 'fade' || k === 'lines') return redraw();
    setForces(sim, P, spots); sim.alpha(0.4).restart();
  });
}

// ================= the drawer (on a phone) =================
// Tapping a point opens a small bar: its name, kind and the map button. Its cards open when asked for: a tap on
// the bar or More, or a swipe up; a swipe down folds them again, and another swipe down (or ✕) closes the bar.
const phone = () => innerWidth < 760;
function drawer(open){
  const sh = $('sheet');
  sh.classList.toggle('peek', phone() && !open);
  $('more').setAttribute('aria-expanded', String(!phone() || open));
  $('more').textContent = open ? 'Less' : 'More';
  if (open) $('links').scrollTop = 0;
  requestAnimationFrame(placeZoom);
}

// on a phone the sheet covers the bottom of the screen: the zoom buttons sit just above it
function placeZoom(){
  const open = !$('sheet').hidden && innerWidth < 760;
  $('zoom').style.bottom = open ? `${$('sheet').offsetHeight + 12}px` : '';
}

// "Show on the map": the map opens the link in the page (main.js openLink), the graph kept as it is
const go = href => hooks.go?.(href);

// a group point's sheet: the group, its people (or themes) by how many places they have, and the map button,
// which opens the map with that layer ticked (pipeline/s06_people.py: people-<kind>; the themes: their layers)
function groupSheet(h){
  const placesOf = m => G.links.filter(l => l.s === m.id || l.t === m.id).map(l => l.s === m.id ? l.t : l.s)
    .filter(x => G.byId.get(x)?.type === 'place');
  const all = new Set(h.members.flatMap(placesOf));
  $('sTitle').textContent = h.label;
  $('sType').textContent = `${h.members.length} ${h.type === 'theme' ? 'story themes' : 'people'} · ${all.size} places`;
  const keys = h.type === 'theme' ? h.members.map(m => m.id.replace(/^t:/, '')) : ['people-' + h.type];
  $('go').hidden = !all.size;
  $('go').textContent = `Show ${all.size} places on the map`;
  $('go').onclick = () => go(`./?group=${keys.map(encodeURIComponent).join(',')}`);
  const rows = h.members.map(m => [m, placesOf(m).length]).sort((a, b) => b[1] - a[1] || a[0].label.localeCompare(b[0].label));
  $('links').innerHTML = `<h3>${esc(h.label)}</h3>` + rows.map(([m, c]) => `<div class="link">
      <button data-id="${esc(m.id)}"><i style="background:var(--k-${kindKey(m.type)})"></i>${esc(m.label)}</button>
      <div class="src">${c} ${c === 1 ? 'place' : 'places'}</div></div>`).join('');
  $('links').scrollTop = 0;
  $('links').querySelectorAll('[data-id]').forEach(b => b.onclick = () => {
    const o = G.byId.get(b.dataset.id); select(o.id, true); setTimeout(() => G.zoomTo(o.x, o.y), 50);
  });
}

function select(id, fromCards){
  const wasOpen = !$('sheet').hidden && !$('sheet').classList.contains('peek');
  sel = id;
  if (spread() !== spreadNow) draw(true); else redraw();
  requestAnimationFrame(placeZoom);
  if (!id) { $('sheet').hidden = true; $('hint').hidden = false; return; }
  const n = G.byId.get(id);
  $('hint').hidden = true; $('sheet').hidden = false;
  drawer(fromCards && wasOpen);
  cardsFor(id);
  if (n.hub) return groupSheet(n);
  $('sTitle').textContent = n.label;
  $('sType').textContent = n.type === 'place'
    ? 'Place' + (n.year != null ? ' · ' + (n.f === 'area' ? 'probably ' : n.f === 'exact' ? '' : 'c. ') + n.year : '')
    : KIND_TITLE[n.type] ? KIND_TITLE[n.type].replace(/s$/, '') : n.type;
  const mine = G.links.filter(l => l.s === id || l.t === id);
  const places = n.type === 'place' ? [id] : mine.map(l => (l.s === id ? l.t : l.s)).filter(x => G.byId.get(x).type === 'place');
  $('go').hidden = !places.length;
  $('go').textContent = places.length > 1 ? `Show ${places.length} places on the map` : 'Show on the map';
  $('go').onclick = () => go(`./?focus=${places.join(',')}&name=${encodeURIComponent(n.label)}`);
  const groups = {};
  mine.forEach(l => { const o = G.byId.get(l.s === id ? l.t : l.s); (groups[o.type] = groups[o.type] || []).push([o, l]); });
  $('links').innerHTML = (n.about ? `<div class="about"><p>${esc(n.about.text)}</p><div class="src">Wikipedia: <a href="${esc(n.about.url)}" target="_blank" rel="noopener">${esc(n.about.title)}</a></div></div>` : '')
    + `<h3>Linked to ${mine.length}</h3>` + Object.entries(groups)
    .sort((a, b) => KINDS.findIndex(k => k[0] === a[0]) - KINDS.findIndex(k => k[0] === b[0]))
    .map(([k, xs]) => xs.map(([o, l]) => `<div class="link">
      <button data-id="${esc(o.id)}"><i style="background:var(--k-${kindKey(o.type)})"></i>${esc(o.label)}</button>
      ${l.text ? `<p>${esc(l.text)}</p>` : ''}
      ${l.src && l.src.url ? `<div class="src">${l.how === 'mention' ? 'Named in this story · ' : ''}${esc(l.src.kind || 'Source')}: <a href="${esc(l.src.url)}" target="_blank" rel="noopener">${esc(l.src.title)}</a></div>` : ''}
    </div>`).join('')).join('');
  $('links').scrollTop = 0;
  $('links').querySelectorAll('[data-id]').forEach(b => b.onclick = () => {
    const o = G.byId.get(b.dataset.id); select(o.id, true);
    setTimeout(() => G.zoomTo(o.x, o.y), 50);          // a folded place is placed once its owner spreads out
  });
}
