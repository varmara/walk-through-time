// Walk Through Time: the graph page. People and story themes, linked to the places where a checked story ties
// them (pipeline/s08_graph.py). Tap a point to see its links and the stories behind them; open them on the map
// with ./?focus=<place>,<place>.
//
// Laid out and set up as Obsidian's graph view is: a force-directed layout (centre, repel, link force, link
// distance), round points sized by their links, names that fade in as you zoom, and a settings panel with
// Filters, Groups (the colours), Display and Forces. One thing of our own: a place linked to only one person or
// theme is folded into it (a ring and its count) and spread out round it when it is tapped.
// Drawn on a canvas (SVG grew slow on a phone with a few thousand points and lines).
(() => {
const CITY = document.body.dataset.city;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;' }[c]));
const KINDS = [
  ['theme', 'Story themes'], ['architects', 'Architects'], ['writers', 'Writers'], ['science', 'Science'],
  ['industry', 'Industry'], ['sport', 'Sport'], ['arts', 'Arts'], ['faith', 'Faith'], ['military', 'Military'],
  ['public', 'Public life'], ['events', 'Events'], ['other', 'Other people'], ['place', 'Places'],
];
const KIND_TITLE = Object.fromEntries(KINDS);
const kindKey = k => KIND_TITLE[k] ? k : 'other';
let shownHubs = [];
let G, sel = null, sim, T = d3.zoomIdentity, ns = [], ls = [], C = {};

// ================= settings (kept in this browser), as in Obsidian =================
// Filters  fold: places with one link folded into their person or theme;  orphans: show points with no lines
// Groups   off: the kinds (colours) switched off
// Display  fade: Obsidian's text fade threshold (higher: names appear only when zoomed further in);
//          size: node size;  lines: link thickness
// Forces   centre: pulls everything to the middle (a rounder graph);  repel: points push each other apart;
//          link: lines pull their ends together;  distance: how long lines try to be;
//          group (ours, not Obsidian's): people and themes of one colour pulled to their own area (groupSpots)
const DEFAULTS = { fold: true, orphans: true, off: [], fade: 0, size: 1, lines: 1,
  centre: 0.5, repel: 10, link: 1, distance: 30, group: 0.5 };
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

// Opening the map from here: its biggest files fetched quietly once the graph has settled (the browser keeps
// them), so the map opens from the phone rather than the network. Not on a connection set to save data.
function readyTheMap(){
  if (readyTheMap.done || navigator.connection?.saveData) return;
  readyTheMap.done = true;
  const v = window.__v || '';
  const files = ['../lib/maplibre-gl.js', '../lib/maplibre-gl.css', `../app/city.css?v=${v}`, `../cities/${CITY}.json`,
    ...['util', 'state', 'data', 'map', 'timebar', 'sheet', 'panels', 'hours', 'cards', 'places', 'main'].map(m => `../app/city/${m}.js?v=${v}`)];
  const later = window.requestIdleCallback || (f => setTimeout(f, 1500));
  later(() => {
    for (const href of files) { const l = document.createElement('link'); l.rel = 'prefetch'; l.href = href; document.head.appendChild(l); }
    // the map's index: kept in the browser's cache; its build and card-file size tell us the card files' names
    fetch(`../data/${CITY}.json`).then(r => r.json()).then(ix => {
      mapIndex = { build: ix.build, chunk: ix.tiles?.chunk };
      if (sel) cardsFor(sel);
    }).catch(() => {});
  });
}
// A tapped person's or theme's places: their card files fetched now, so the map has them when it opens
// (the map asks for the same files: data/<city>/cards/<n>.json?v=<build>, n = building ÷ chunk)
let mapIndex = null;
const fetched = new Set();
function cardsFor(id){
  if (!mapIndex?.chunk || !id || id.startsWith('g:')) return;
  const n0 = G.byId.get(id); if (!n0) return;
  const ids = n0.type === 'place' ? [id] : [...n0.nb].filter(x => G.byId.get(x)?.type === 'place');
  const files = new Set(ids.filter(x => /^b\d+$/.test(x)).map(x => Math.floor(+x.slice(1) / mapIndex.chunk)));
  if (files.size > 30) return;                   // a whole group: the map does not need its cards to open
  for (const f of files) {
    const url = `../data/${CITY}/cards/${f}.json?v=${mapIndex.build}`;
    if (fetched.has(url)) continue;
    fetched.add(url); fetch(url).catch(() => fetched.delete(url));
  }
}
// "← Map": back in history when the map is the page just before this one (the phone may still hold it, with its
// tiles and where it was), a new visit otherwise
document.querySelector('.brand a')?.addEventListener('click', e => {
  try {
    const ref = document.referrer && new URL(document.referrer), map = new URL('./', location.href);
    if (ref && ref.origin === location.origin && ref.pathname === map.pathname && history.length > 1) {
      e.preventDefault(); history.back();
    }
  } catch {}
});
// the map takes a moment to open: say so at once
function opening(btn, href){ btn.textContent = 'Opening the map…'; btn.disabled = true; location.href = href; }
// back from the map (the page kept as it was): the button again as it should be
addEventListener('pageshow', e => { if (e.persisted && sel) { $('go').disabled = false; select(sel); } });

fetch(`../data/${CITY}-graph.json?v=${window.__v || ''}`).then(r => r.json()).then(init)
  .catch(() => { $('loading').textContent = 'The graph could not be loaded.'; });

// ================= the canvas =================
const canvas = $('graph'), ctx = canvas.getContext('2d');
let W = 0, H = 0, frame = 0;
function resize(){
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
matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', colours);
const redraw = () => { if (!frame) frame = requestAnimationFrame(paint); };

function init(data){
  G = data;
  $('loading').hidden = true;
  const byId = new Map(G.nodes.map(n => [n.id, n]));
  G.links = G.links.filter(l => byId.has(l.s) && byId.has(l.t)).map(l => ({ ...l, source: l.s, target: l.t }));
  G.nodes.forEach(n => { n.deg = 0; n.nb = new Set(); });
  G.links.forEach(l => { const a = byId.get(l.s), b = byId.get(l.t); a.deg++; b.deg++; a.nb.add(b.id); b.nb.add(a.id); });
  // a place linked to only one person or theme: that one is its owner, into which it folds
  G.nodes.forEach(n => { if (n.type === 'place' && n.nb.size === 1) { const o = byId.get([...n.nb][0]); if (o.type !== 'place') n.owner = o; } });
  G.byId = byId;
  G.present = new Set(G.nodes.map(n => n.type));
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
  // (the subject carries the finger's place on screen, so the drag's x and y stay in screen pixels)
  const drag = d3.drag().container(canvas).clickDistance(6).subject(e => { const n = pick(e.x, e.y); return n && { n, x: e.x, y: e.y }; })
    .on('start', e => { if (!e.active) sim.alphaTarget(0.1).restart(); const n = e.subject.n; n.fx = n.x; n.fy = n.y; })
    .on('drag', e => { const [x, y] = T.invert([e.x, e.y]), n = e.subject.n; n.fx = x; n.fy = y; G.moved = true; })
    .on('end', e => { if (!e.active) sim.alphaTarget(0); const n = e.subject.n; n.fx = n.fy = null; });
  sel$.call(drag).call(zoom).on('dblclick.zoom', null);
  canvas.addEventListener('click', e => { const n = pick(e.offsetX, e.offsetY); select(n ? n.id : null); if (n) G.reveal(n); });
  // buttons as well as pinching: on a phone the points can be too close together to pinch between. They zoom
  // about the selected point when there is one, so it stays in view, or else the middle of the screen
  const step = f => {
    const n = sel && G.byId.get(sel);
    const at = n && n.x != null && ns.includes(n) ? T.apply([n.x, n.y]) : [W / 2, H / 2];
    sel$.transition().duration(250).call(zoom.scaleBy, f, at);
  };
  $('zIn').onclick = () => step(1.6);
  $('zOut').onclick = () => step(1 / 1.6);
  $('zFit').onclick = () => G.fit();
  // a tapped point the sheet would cover (on a phone, the bottom half): the graph slides up to show it, at the
  // same zoom
  G.reveal = n => requestAnimationFrame(() => {
    if (!n || n.x == null || $('sheet').hidden || W >= 760) return;
    const [, sy] = T.apply([n.x, n.y]), room = H - $('sheet').offsetHeight - 30;
    if (sy > 70 && sy < room) return;
    sel$.transition().duration(350).call(zoom.translateBy, 0, (70 + room) / 2 / T.k - sy / T.k);
  });
  G.zoomTo = (x, y) => sel$.transition().duration(600).call(zoom.transform,
    d3.zoomIdentity.translate(W / 2, H * (W >= 760 ? 0.5 : 0.3)).scale(Math.max(T.k, 1.6)).translate(-x, -y));
  // once the layout settles the first time, fit the whole graph on the screen
  let fitted = false;
  G.fit = () => {
    if (!ns.length) return;
    const xs = ns.map(n => n.x), ys = ns.map(n => n.y), top = 70;
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const k = Math.max(0.1, Math.min(3, 0.9 * Math.min(W / (x1 - x0 || 1), (H - top - 40) / (y1 - y0 || 1))));
    sel$.transition().duration(700).call(zoom.transform, d3.zoomIdentity
      .translate(W / 2, top + (H - top - 40) / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2));
  };

  sim = d3.forceSimulation().force('link', d3.forceLink().id(d => d.id)).force('charge', d3.forceManyBody())
    .force('x', d3.forceX(0)).force('y', d3.forceY(0)).force('collide', d3.forceCollide())
    .force('gx', d3.forceX(d => spotOf(d)[0])).force('gy', d3.forceY(d => spotOf(d)[1]))
    .on('tick', redraw).on('end', () => { readyTheMap(); if (!fitted) { fitted = true; if (!sel && !G.moved) G.fit(); } });
  forces();
  panel();
  addEventListener('resize', () => { resize(); placeZoom(); });
  colours(); resize();
  draw();
  // a head start: most of the layout is worked out before the first picture (up to a third of a second, so a slow
  // phone is not left blank), then fitted to the screen, and the rest settles in view
  const t0 = performance.now();
  while (sim.alpha() > 0.08 && performance.now() - t0 < 330) sim.tick();
  G.fit();

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
  const start = new URLSearchParams(location.search).get('node');
  if (start && byId.has(start)) setTimeout(() => { select(start); const n = byId.get(start); G.zoomTo(n.x, n.y); }, 900);
}

// ================= forces (Obsidian's four) =================
// Each colour's area: the biggest group in the middle, the others round it, further out the more there are;
// places have none (they follow their lines)
let spots = {};
function groupSpots(){
  const count = d3.rollup(ns.filter(n => n.type !== 'place'), v => v.length, n => n.type);
  const kinds = [...count].sort((a, b) => b[1] - a[1]).map(k => k[0]);
  const R = 9 * Math.sqrt(ns.length) + 40;
  spots = Object.fromEntries(kinds.map((k, i) => i === 0 ? [k, [0, 0]]
    : [k, [R * Math.cos(2 * Math.PI * (i - 1) / (kinds.length - 1) - Math.PI / 2), R * Math.sin(2 * Math.PI * (i - 1) / (kinds.length - 1) - Math.PI / 2)]]));
}
const spotOf = d => spots[d.type] || [0, 0];
function forces(){
  // the centre force acts less on people and themes while they are grouped, so their areas can sit apart
  const c = d => P.centre * 0.1 * (d.type !== 'place' && P.group ? 1 - 0.8 * P.group : 1);
  sim.force('x').strength(c); sim.force('y').strength(c);
  const g = d => d.type === 'place' ? 0 : P.group * 0.12;
  sim.force('gx').x(d => spotOf(d)[0]).strength(g); sim.force('gy').y(d => spotOf(d)[1]).strength(g);
  sim.force('charge').strength(d => -P.repel * 6 * (1 + Math.sqrt(d.folds || 0) * 0.4)).distanceMax(400);
  sim.force('link').strength(P.link).distance(P.distance);
  sim.force('collide').radius(d => radius(d) + 1);
}
// a point's size: grows with its links (and the places folded into it), as Obsidian's do
const radius = d => P.size * (3 + 1.6 * Math.sqrt(d.deg + (d.folds || 0)));

// ================= what is shown =================
// the point whose folded places are spread out: the selected one, or the owner of a selected folded place
const spread = () => { const n = sel && G.byId.get(sel); return !n ? null : n.owner && P.fold ? n.owner.id : n.id; };
let spreadNow;
function draw(gentle){
  spreadNow = spread();
  const folded = n => P.fold && n.owner && n.owner.id !== spreadNow && !off.has(n.owner.type);
  G.nodes.forEach(n => { n.folds = 0; });
  G.nodes.forEach(n => { if (!off.has(n.type) && folded(n)) n.owner.folds++; });
  let vis = G.nodes.filter(n => !off.has(n.type) && !folded(n));
  let ids = new Set(vis.map(n => n.id));
  ls = G.links.filter(l => ids.has(l.s) && ids.has(l.t));
  if (!P.orphans) {
    const linked = new Set(ls.flatMap(l => [l.s, l.t]));
    vis = vis.filter(n => linked.has(n.id) || n.folds || n.id === sel);
  }
  // a place spread out starts at its owner, so it grows out of it
  for (const n of vis) if (n.owner && n.owner.x != null && (n.x == null || n.hidden)) {
    const a = Math.random() * 2 * Math.PI; n.x = n.owner.x + 8 * Math.cos(a); n.y = n.owner.y + 8 * Math.sin(a); n.vx = n.vy = 0;
  }
  G.nodes.forEach(n => { n.hidden = true; }); vis.forEach(n => { n.hidden = false; });
  ns = vis;
  groupSpots();
  sim.nodes(ns); sim.force('link').links(ls);
  forces();
  canvas.dataset.points = ns.length;          // for the page's checks (tests/page/smoke.cjs)
  canvas.inspect = () => ({ t: [T.x, T.y, T.k], nodes: ns.map(n => [n.id, n.x, n.y]) });
  sim.alpha(gentle ? 0.12 : 0.6).restart();     // a tap spreading a point's places: only a nudge, not a shake
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

// Names fade in as you zoom (Obsidian's text fade threshold moves where): fully shown from zoom 2^(fade + 0.6),
// gone below 2^(fade − 0.4). The selected point and its neighbours are always named.
// An unnamed building is named only when it is the one tapped ("Unnamed building" a hundred times says nothing).
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
  if (!G) return;
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
  // names under their points, as in Obsidian, none over another: the selection's first, then its neighbours',
  // then the best-linked; a name that would overlap one already drawn is left out
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
    const k = i.dataset.s; P[k] = +i.value; $('o-' + k).textContent = fmt(P[k], steps[k]); saveP();
    if (k === 'fade' || k === 'lines') return redraw();
    forces(); sim.alpha(0.4).restart();
  });
}
$('gear').onclick = () => { const open = $('settings').hidden; $('settings').hidden = !open; $('gear').setAttribute('aria-expanded', open); };
$('sClose').onclick = () => { $('settings').hidden = true; $('gear').setAttribute('aria-expanded', 'false'); };
$('sReset').onclick = () => { Object.assign(P, DEFAULTS); off.clear(); saveP(); panel(); draw(); };

// ================= the drawer (on a phone) =================
// Tapping a point opens a small bar: its name, kind and the map button. Its cards (who, what, the stories and
// their sources) open when asked for: a tap on the bar or More, or a swipe up; a swipe down folds them again, and
// another swipe down (or ✕) closes the bar.
const phone = () => innerWidth < 760;
function drawer(open){
  const sh = $('sheet');
  sh.classList.toggle('peek', phone() && !open);
  $('more').setAttribute('aria-expanded', String(!phone() || open));
  $('more').textContent = open ? 'Less' : 'More';
  if (open) $('links').scrollTop = 0;
  requestAnimationFrame(() => { placeZoom(); });
}
$('more').onclick = e => { e.stopPropagation(); drawer($('sheet').classList.contains('peek')); };
$('grab').onclick = () => drawer($('sheet').classList.contains('peek'));
$('shead').onclick = e => { if (e.target.closest('button')) return; if ($('sheet').classList.contains('peek')) drawer(true); };
{
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
}

// on a phone the sheet covers the bottom of the screen: the zoom buttons sit just above it
function placeZoom(){
  const open = !$('sheet').hidden && innerWidth < 760;
  $('zoom').style.bottom = open ? `${$('sheet').offsetHeight + 12}px` : '';
}

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
  $('go').onclick = () => opening($('go'), `./?group=${keys.map(encodeURIComponent).join(',')}`);
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
  if (n.hub) return groupSheet(n);     // on a phone: the small bar first; the cards when asked for (they stay open
                                    // when one card's link leads to the next)
  $('sTitle').textContent = n.label;
  $('sType').textContent = n.type === 'place'
    ? 'Place' + (n.year != null ? ' · ' + (n.f === 'area' ? 'probably ' : n.f === 'exact' ? '' : 'c. ') + n.year : '')
    : KIND_TITLE[n.type] ? KIND_TITLE[n.type].replace(/s$/, '') : n.type;
  const mine = G.links.filter(l => l.s === id || l.t === id);
  const places = n.type === 'place' ? [id] : mine.map(l => (l.s === id ? l.t : l.s)).filter(x => G.byId.get(x).type === 'place');
  $('go').hidden = !places.length;
  $('go').textContent = places.length > 1 ? `Show ${places.length} places on the map` : 'Show on the map';
  $('go').onclick = () => opening($('go'), `./?focus=${places.join(',')}&name=${encodeURIComponent(n.label)}`);
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
})();
