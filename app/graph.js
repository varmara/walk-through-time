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
let G, sel = null, sim, T = d3.zoomIdentity, ns = [], ls = [], C = {};

// ================= settings (kept in this browser), as in Obsidian =================
// Filters  fold: places with one link folded into their person or theme;  orphans: show points with no lines
// Groups   off: the kinds (colours) switched off
// Display  fade: Obsidian's text fade threshold (higher: names appear only when zoomed further in);
//          size: node size;  lines: link thickness
// Forces   centre: pulls everything to the middle (a rounder graph);  repel: points push each other apart;
//          link: lines pull their ends together;  distance: how long lines try to be
const DEFAULTS = { fold: true, orphans: true, off: [], fade: 0, size: 1, lines: 1,
  centre: 0.5, repel: 10, link: 1, distance: 30 };
const SLIDERS = {
  Display: [['fade', 'Text fade threshold', -3, 3, 0.1], ['size', 'Node size', 0.2, 4, 0.1], ['lines', 'Link thickness', 0.2, 4, 0.1]],
  Forces: [['centre', 'Center force', 0, 1, 0.01], ['repel', 'Repel force', 0, 20, 0.5],
           ['link', 'Link force', 0, 1, 0.01], ['distance', 'Link distance', 5, 250, 1]],
};
const P = { ...DEFAULTS };
try { Object.assign(P, JSON.parse(localStorage.getItem('graph-settings') || '{}')); } catch {}
const off = new Set(P.off);
const saveP = () => { P.off = [...off]; try { localStorage.setItem('graph-settings', JSON.stringify(P)); } catch {} };

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

  const sel$ = d3.select(canvas);
  const zoom = d3.zoom().scaleExtent([0.1, 8]).clickDistance(6).on('zoom', e => { T = e.transform; redraw(); });
  // dragging a point moves it; dragging elsewhere pans (the drag starts only on a point)
  const drag = d3.drag().container(canvas).clickDistance(6).subject(e => pick(e.x, e.y))
    .on('start', e => { if (!e.active) sim.alphaTarget(0.1).restart(); e.subject.fx = e.subject.x; e.subject.fy = e.subject.y; })
    .on('drag', e => { const [x, y] = T.invert([e.x, e.y]); e.subject.fx = x; e.subject.fy = y; })
    .on('end', e => { if (!e.active) sim.alphaTarget(0); e.subject.fx = e.subject.fy = null; });
  sel$.call(drag).call(zoom).on('dblclick.zoom', null);
  canvas.addEventListener('click', e => { const n = pick(e.offsetX, e.offsetY); select(n ? n.id : null); });
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
    .on('tick', redraw).on('end', () => { if (!fitted) { fitted = true; if (!sel) G.fit(); } });
  forces();
  panel();
  addEventListener('resize', () => { resize(); placeZoom(); });
  colours(); resize();
  draw();

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
function forces(){
  sim.force('x').strength(P.centre * 0.1); sim.force('y').strength(P.centre * 0.1);
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
function draw(){
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
  sim.nodes(ns); sim.force('link').links(ls);
  forces();
  canvas.dataset.points = ns.length;          // for the page's checks (tests/page/smoke.cjs)
  sim.alpha(0.6).restart();
  redraw();
}

// the point under a finger or the pointer, if any (a target of at least 14 px round it)
const screenR = d => Math.max(1.5, radius(d) * T.k);
function pick(x, y){
  let best = null, bd = Infinity;
  for (const n of ns) {
    const [sx, sy] = T.apply([n.x, n.y]), d = Math.hypot(sx - x, sy - y), r = Math.max(14, screenR(n) + 6);
    if (d < r && d < bd) { best = n; bd = d; }
  }
  return best;
}

// Names fade in as you zoom (Obsidian's text fade threshold moves where): fully shown from zoom 2^(fade + 0.6),
// gone below 2^(fade − 0.4). The selected point and its neighbours are always named.
function nameAlpha(d, near){
  if (d.id === sel || near.has(d.id)) return 1;
  const z = Math.log2(T.k) - P.fade + (d.deg >= 6 ? 1 : d.deg >= 3 ? 0.5 : 0);    // well-linked points sooner
  return Math.max(0, Math.min(1, z + 0.4));
}

function paint(){
  frame = 0;
  if (!G) return;
  ctx.clearRect(0, 0, W, H);
  const near = sel ? G.byId.get(sel).nb : new Set(), focus = !!sel, lw = P.lines;
  // lines (the selection's on top, darker)
  for (const pass of focus ? [0, 1] : [0]) {
    for (const l of ls) {
      const on = focus && (l.s === sel || l.t === sel);
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
    const a = nameAlpha(d, near) * (lit ? 1 : 0.3);
    if (a > 0.02) names.push([d, x, y + r + 9, a]);
  }
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
  for (const [d, x, y, a] of names) {          // under the point, as in Obsidian
    ctx.globalAlpha = a;
    ctx.font = `${d.id === sel ? 600 : 400} 12px ${C.sans}`;
    const text = d.label + (d.folds ? ` · ${d.folds}` : '');
    ctx.lineWidth = 3; ctx.strokeStyle = C.bg; ctx.strokeText(text, x, y);
    ctx.fillStyle = d.type === 'place' ? C.muted : C.ink; ctx.fillText(text, x, y);
  }
  ctx.globalAlpha = 1;
}

// ================= the settings panel (Filters, Groups, Display, Forces) =================
const openSections = new Set(['Filters', 'Groups']);
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

// on a phone the sheet covers the bottom of the screen: the zoom buttons sit just above it
function placeZoom(){
  const open = !$('sheet').hidden && innerWidth < 760;
  $('zoom').style.bottom = open ? `${$('sheet').offsetHeight + 12}px` : '';
}

function select(id){
  sel = id;
  if (spread() !== spreadNow) draw(); else redraw();
  requestAnimationFrame(placeZoom);
  if (!id) { $('sheet').hidden = true; $('hint').hidden = false; return; }
  const n = G.byId.get(id);
  $('hint').hidden = true; $('sheet').hidden = false;
  $('sTitle').textContent = n.label;
  $('sType').textContent = n.type === 'place'
    ? 'Place' + (n.year != null ? ' · ' + (n.f === 'area' ? 'probably ' : n.f === 'exact' ? '' : 'c. ') + n.year : '')
    : KIND_TITLE[n.type] ? KIND_TITLE[n.type].replace(/s$/, '') : n.type;
  const mine = G.links.filter(l => l.s === id || l.t === id);
  const places = n.type === 'place' ? [id] : mine.map(l => (l.s === id ? l.t : l.s)).filter(x => G.byId.get(x).type === 'place');
  $('go').hidden = !places.length;
  $('go').textContent = places.length > 1 ? `Show ${places.length} places on the map` : 'Show on the map';
  $('go').onclick = () => { location.href = `./?focus=${places.join(',')}&name=${encodeURIComponent(n.label)}`; };
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
    const o = G.byId.get(b.dataset.id); select(o.id);
    setTimeout(() => G.zoomTo(o.x, o.y), 50);          // a folded place is placed once its owner spreads out
  });
}
})();
