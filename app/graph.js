// Walk Through Time: the graph page. People and story themes, linked to the places where a checked story ties
// them (pipeline/s08_graph.py). Tap a point to see its links and the stories behind them; open them on the map
// with ./?focus=<place>,<place>.
//
// Drawn on a canvas (not SVG, which grew slow on a phone with a few thousand points and lines). Points are found
// for tapping and dragging by distance; text, lines and points keep about the same size on screen as you zoom
// (as in Obsidian), so zooming in spreads points apart instead of blowing up the labels.
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
const off = new Set();
let G, sel = null, sim, T = d3.zoomIdentity, ns = [], ls = [], C = {};

// ================= settings (the Layout panel, kept in this browser) =================
// Layout: Daisies (each person or theme with its places round it on rings, daisies of one colour packed into a
// constellation, the colours' constellations packed further apart) or Forces (a force-directed layout, as Obsidian)
// Display
//   names    the zoom at which every point's name shows (Obsidian's "text fade threshold"); before it, only
//            story themes and well-linked points, and those next to the selection
//   size     points' size;  lines: lines' thickness
//   fold     places linked to only one person or theme are folded into it (its count shown by it) and spread
//            out round it when it is tapped; places shared by two or more stay, as they are the links between
//   lonely   hide points with no lines left (when the kinds they link to are switched off)
// Forces
//   group    how strongly each person or theme is pulled to its kind's spot (points of one colour together)
//   links    how strongly a line pulls its two ends together
//   length   how long the lines try to be
//   repel    how strongly points push each other apart
//   space    the gap kept round each point
//   orbit    how strongly a place is drawn to the middle of the people and themes it is linked to, so places
//            are satellites of their points (one linked to two settles between them)
// a phone's screen is small: names later, points a little bigger, colours further apart
const PHONE = innerWidth < 760;
const DEFAULTS = { mode: 'daisy', names: PHONE ? 3 : 2.2, size: PHONE ? 1.2 : 1, lines: 1, fold: true, lonely: false,
  petals: 6, daisies: 10, groups: PHONE ? 120 : 70,
  group: 0.14, links: 0.7, length: 34, repel: 1.2, space: 4, orbit: 0.12 };
// [key, title, lowest, highest, step, what it is for (shown under it)]
const DISPLAY = [
  ['names', 'Names from zoom', 0.5, 5, 0.1, 'Higher: fewer names until you zoom in'],
  ['size', 'Point size', 0.5, 2.5, 0.1, 'Bigger points are easier to see and tap'],
  ['lines', 'Line thickness', 0.3, 4, 0.1, 'Thicker if lines fade into the background']];
const CHECKS = [['fold', 'Fold places with one link', 'Tap a point to spread its places out'],
  ['lonely', 'Hide points with no lines', 'For when the kinds they link to are off']];
// Daisies (the default layout, daisyLayout): petals = the gap between a point's places on their rings, daisies =
// the gap between daisies of one colour, groups = the gap between the colours' constellations
const DAISY = [['petals', 'Space between petals', 0, 20, 1, 'More if places are hard to tap'],
  ['daisies', 'Space between daisies', 0, 60, 2, 'More if daisies of one colour run together'],
  ['groups', 'Space between colours', 0, 300, 10, 'More to keep colours apart (Show all zooms out further)']];
const FORCES = [
  ['group', 'Group by colour', 0, 0.5, 0.01, 'Pulls points of one colour together'],
  ['links', 'Pull along links', 0, 1, 0.05, 'Pulls linked points together'],
  ['length', 'Link length', 10, 120, 2, 'How long lines try to be'],
  ['repel', 'Push apart', 0, 3, 0.1, 'More to loosen dense clusters'],
  ['space', 'Space round points', 0, 20, 1, 'More to stop points overlapping'],
  ['orbit', 'Places round their points', 0, 1, 0.05, 'More to keep places tight to their people'],
];
const P = { ...DEFAULTS };
try { Object.assign(P, JSON.parse(localStorage.getItem('graph-layout-3') || '{}')); } catch {}
const saveP = () => { try { localStorage.setItem('graph-layout-3', JSON.stringify(P)); } catch {} };

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
  C = { edge: v('--edge'), ink: v('--ink'), bg: v('--bg'), muted: v('--muted'), sans: v('--sans') || 'sans-serif',
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

  const present = new Set(G.nodes.map(n => n.type));
  $('kinds').innerHTML = KINDS.filter(([k]) => present.has(k)).map(([k, t]) =>
    `<button class="kind" data-k="${k}" aria-pressed="true"><i style="background:var(--k-${k})"></i>${t}</button>`).join('');
  $('kinds').querySelectorAll('.kind').forEach(b => b.onclick = () => {
    off.has(b.dataset.k) ? off.delete(b.dataset.k) : off.add(b.dataset.k);
    b.classList.toggle('off', off.has(b.dataset.k)); b.setAttribute('aria-pressed', !off.has(b.dataset.k));
    draw();
  });

  const sel$ = d3.select(canvas);
  const zoom = d3.zoom().scaleExtent([0.15, 8]).clickDistance(6).on('zoom', e => { T = e.transform; redraw(); });
  // dragging a point moves it; dragging elsewhere pans (the drag starts only on a point)
  const drag = d3.drag().container(canvas).clickDistance(6).subject(e => pick(e.x, e.y))
    .on('start', e => { if (P.mode === 'daisy') return; if (!e.active) sim.alphaTarget(0.06).restart(); e.subject.fx = e.subject.x; e.subject.fy = e.subject.y; })
    .on('drag', e => {
      const [x, y] = T.invert([e.x, e.y]), d = e.subject;
      if (P.mode !== 'daisy') { d.fx = x; d.fy = y; return; }
      // daisies: a point moves with its petals
      const dx = x - d.x, dy = y - d.y;
      const moving = [d, ...(d.type === 'place' ? [] : ns.filter(n => n.type === 'place' && n.nb.size && [...n.nb].every(id => id === d.id)))];
      for (const n of moving) { n.x += dx; n.y += dy; n.tx = n.x; n.ty = n.y; }
      redraw();
    })
    .on('end', e => { if (P.mode === 'daisy') return; if (!e.active) sim.alphaTarget(0); e.subject.fx = e.subject.fy = null; });
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
    d3.zoomIdentity.translate(W / 2, H * (W >= 760 ? 0.5 : 0.3)).scale(Math.max(T.k, 1.4)).translate(-x, -y));
  // once the layout settles the first time, fit the whole graph on the screen
  let fitted = false;
  G.fit = () => {
    if (!ns.length) return;
    const xs = ns.map(n => n.x), ys = ns.map(n => n.y), top = 110;
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const k = Math.max(0.15, Math.min(3, 0.9 * Math.min(W / (x1 - x0 || 1), (H - top - 40) / (y1 - y0 || 1))));
    sel$.transition().duration(700).call(zoom.transform, d3.zoomIdentity
      .translate(W / 2, top + (H - top - 40) / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2));
  };

  sim = d3.forceSimulation().force('link', d3.forceLink().id(d => d.id)).force('charge', d3.forceManyBody().distanceMax(260))
    .force('collide', d3.forceCollide()).force('x', d3.forceX(d => anchor(d)[0])).force('y', d3.forceY(d => anchor(d)[1]))
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
    if (n) { select(n.id); G.zoomTo(n.x, n.y); }
  };
  $('find').onkeydown = e => { if (e.key === 'Enter') $('find').blur(); };
  $('close').onclick = () => select(null);
  const start = new URLSearchParams(location.search).get('node');
  if (start && byId.has(start)) setTimeout(() => { select(start); const n = byId.get(start); G.zoomTo(n.x, n.y); }, 900);
}

// ================= forces =================
// each place pulled to the middle of the points it is linked to (people and themes, as they move)
let around = new Map();
function orbit(alpha){
  const k = P.orbit * alpha;
  for (const [n, ps] of around) {
    if (!ps.length) continue;
    let x = 0, y = 0;
    for (const m of ps) { x += m.x; y += m.y; }
    n.vx += (x / ps.length - n.x) * k; n.vy += (y / ps.length - n.y) * k;
  }
}
function forces(){
  sim.force('link').distance(l => P.length * (l.how === 'mention' ? 1.6 : 1)).strength(P.links);
  sim.force('charge').strength(d => P.repel * (d.type === 'theme' ? -220 : d.type === 'place' ? -20 : d.deg > 1 ? -60 : -25));
  sim.force('collide').radius(d => radius(d) * P.size + P.space);
  sim.force('x').strength(d => d.type === 'place' ? 0 : P.group);         // places: no pull of their own…
  sim.force('y').strength(d => d.type === 'place' ? 0 : P.group);
  sim.force('orbit', orbit);                                               // …but drawn to their points
}

// Points of one kind (one colour) gather together: each kind is pulled towards its own spot on a circle round the
// middle, in the order of the kinds row. The spots are shared out again among the kinds shown.
let spots = {};
function placeSpots(){
  const kinds = KINDS.map(k => k[0]).filter(k => k !== 'place' && ns.some(n => n.type === k));
  const R = 120 + 28 * kinds.length, cx = innerWidth / 2, cy = innerHeight / 2;
  spots = Object.fromEntries(kinds.map((k, i) => {
    const a = -Math.PI / 2 + 2 * Math.PI * i / kinds.length;
    return [k, [cx + R * Math.cos(a), cy + R * Math.sin(a)]];
  }));
}
function anchor(d){ return spots[d.type] || [innerWidth / 2, innerHeight / 2]; }
function radius(d){ return d.type === 'theme' ? 11 : d.type === 'place' ? 4 + Math.min(4, d.deg) : 5 + Math.min(7, d.deg * 1.2); }

// ================= what is shown =================
// the point whose folded places are spread out: the selected one, or the owner of a selected folded place
const spread = () => { const n = sel && G.byId.get(sel); return !n ? null : n.owner && P.fold ? n.owner.id : n.id; };
let spreadNow;
function draw(){
  spreadNow = spread();
  const folded = n => P.fold && n.owner && n.owner.id !== spreadNow && !off.has(n.owner.type);
  // how many places each point has folded into it
  G.nodes.forEach(n => { n.folds = 0; });
  G.nodes.forEach(n => { if (!off.has(n.type) && folded(n)) n.owner.folds++; });
  let vis = G.nodes.filter(n => !off.has(n.type) && !folded(n));
  let ids = new Set(vis.map(n => n.id));
  ls = G.links.filter(l => ids.has(l.s) && ids.has(l.t));
  if (P.lonely) {
    const linked = new Set(ls.flatMap(l => [l.s, l.t]));
    vis = vis.filter(n => linked.has(n.id) || n.folds || n.id === sel);
    ids = new Set(vis.map(n => n.id));
  }
  // a place spread out starts at its owner, so it grows out of it
  for (const n of vis) if (n.x == null && n.owner && n.owner.x != null) {
    const a = Math.random() * 2 * Math.PI; n.x = n.owner.x + 12 * Math.cos(a); n.y = n.owner.y + 12 * Math.sin(a);
  }
  ns = vis;
  placeSpots();                 // before sim.nodes, which reads each point's spot
  sim.nodes(ns); sim.force('link').links(ls);
  around = new Map(ns.filter(n => n.type === 'place').map(n => [n, []]));    // each place's people and themes
  for (const l of ls) {
    if (around.has(l.source) && l.target.type !== 'place') around.get(l.source).push(l.target);
    if (around.has(l.target) && l.source.type !== 'place') around.get(l.target).push(l.source);
  }
  canvas.dataset.points = ns.length;          // for the page's checks (tests/page/smoke.cjs)
  if (P.mode === 'daisy') { sim.stop(); daisyLayout(); }
  else { sim.alpha(0.6).restart(); redraw(); }
}

// ================= the daisy layout =================
// Each person or theme is a daisy: the places linked to it alone round it on rings (petals), as many to a ring as
// fit. A colour's daisies are packed together without overlapping (d3.packSiblings) into a constellation, and the
// constellations are packed again, further apart. Places shared by two or more are laid last, each between its
// daisies, kept off the others' points (a short force layout with everything else fixed). The points glide to
// their new places (glide) rather than jump.
// A folded daisy spread out for the selection keeps its size: its petals are put round it on top, so the rest
// does not move every time a point is tapped.
const ringOf = d => radius(d) * P.size;
function daisyLayout(){
  const hubs = ns.filter(n => n.type !== 'place'), places = ns.filter(n => n.type === 'place');
  const hubsOf = new Map(places.map(n => [n, []]));
  for (const l of ls) {
    if (hubsOf.has(l.source) && l.target.type !== 'place') hubsOf.get(l.source).push(l.target);
    if (hubsOf.has(l.target) && l.source.type !== 'place') hubsOf.get(l.target).push(l.source);
  }
  const petals = new Map(hubs.map(h => [h, []])), extra = new Map(), shared = [];
  for (const [n, hs] of hubsOf) {
    if (hs.length !== 1) shared.push(n);
    else if (P.fold && n.owner && n.owner.id === spreadNow) (extra.get(hs[0]) || extra.set(hs[0], []).get(hs[0])).push(n);
    else petals.get(hs[0]).push(n);
  }
  // rings of petals round a point, from the middle out: returns the daisy's radius, sets the petals' targets
  const rings = (h, ps, cx, cy, start = -Math.PI / 2) => {
    const order = ps.slice().sort((a, b) => (a.year ?? 9999) - (b.year ?? 9999) || a.label.localeCompare(b.label));
    let r = ringOf(h) + P.petals + 6, i = 0, outer = ringOf(h);
    while (i < order.length) {
      const s = Math.max(...order.slice(i, i + 40).map(ringOf));
      r += s;
      const fit = Math.max(6, Math.floor(2 * Math.PI * r / (2 * s + P.petals)));
      const k = Math.min(fit, order.length - i), turn = (ringsDone(r) % 2) * Math.PI / k;
      for (let j = 0; j < k; j++) {
        const a = start + turn + 2 * Math.PI * j / k, n = order[i + j];
        n.tx = cx + r * Math.cos(a); n.ty = cy + r * Math.sin(a);
      }
      i += k; outer = r + s; r += s + P.petals;
    }
    return outer;
  };
  let ringCount = 0; const ringsDone = () => ringCount++;     // every other ring turned half a step, like seeds
  // a daisy's size, laid out at 0,0 for now
  const daisy = hubs.map(h => { ringCount = 0; return { h, r: rings(h, petals.get(h), 0, 0) + P.daisies / 2, x: 0, y: 0 }; });
  // constellations: the daisies of one colour packed together, biggest first
  const byKind = d3.group(daisy, d => d.h.type);
  const groups = [...byKind].map(([k, ds]) => {
    ds.sort((a, b) => b.r - a.r);
    d3.packSiblings(ds);
    const e = d3.packEnclose(ds);
    return { k, ds, r: e.r + P.groups / 2, cx: e.x, cy: e.y, x: 0, y: 0 };
  });
  groups.sort((a, b) => b.r - a.r);
  d3.packSiblings(groups);
  const ox = innerWidth / 2, oy = innerHeight / 2;
  for (const g of groups) for (const d of g.ds) {
    const x = ox + g.x + d.x - g.cx, y = oy + g.y + d.y - g.cy;
    d.h.tx = x; d.h.ty = y;
    // the first petal points away from the middle of the constellation, so a daisy of one or two petals
    // stands out from its neighbours
    const out = Math.hypot(d.x - g.cx, d.y - g.cy) > 1 ? Math.atan2(d.y - g.cy, d.x - g.cx) : -Math.PI / 2;
    ringCount = 0; rings(d.h, petals.get(d.h), x, y, out);
    const more = extra.get(d.h);                  // spread for the selection: on top, round its edge
    if (more) { ringCount = 0; rings(d.h, more, x, y, out); }
  }
  // shared places: between their daisies, off everyone else's points
  if (shared.length) {
    const fixed = ns.filter(n => !shared.includes(n)).map(n => ({ x: n.tx, y: n.ty, fx: n.tx, fy: n.ty, n }));
    const free = shared.map((n, i) => {           // the same small offsets every time, so the layout is steady
      const hs = hubsOf.get(n), m = hs.length ? [d3.mean(hs, h => h.tx), d3.mean(hs, h => h.ty)] : [ox, oy];
      return { x: m[0] + 2 * Math.cos(i * 2.4), y: m[1] + 2 * Math.sin(i * 2.4), mx: m[0], my: m[1], n };
    });
    const all = fixed.concat(free);
    d3.forceSimulation(all).stop()
      .force('x', d3.forceX(d => d.mx ?? d.x).strength(d => d.fx == null ? 0.25 : 0))
      .force('y', d3.forceY(d => d.my ?? d.y).strength(d => d.fx == null ? 0.25 : 0))
      .force('collide', d3.forceCollide(d => ringOf(d.n) + 3).iterations(2))
      .tick(120);
    for (const f of free) { f.n.tx = f.x; f.n.ty = f.y; }
  }
  glide();
}
// move each point to its target over about half a second
let gliding = 0, firstFit = true;
function glide(){
  for (const n of ns) if (n.x == null) { n.x = n.tx; n.y = n.ty; }
  const t0 = performance.now(), from = new Map(ns.map(n => [n, [n.x, n.y]]));
  cancelAnimationFrame(gliding);
  const step = now => {
    const t = Math.min(1, (now - t0) / 550), e = d3.easeCubicInOut(t);
    for (const [n, [x, y]] of from) { n.x = x + (n.tx - x) * e; n.y = y + (n.ty - y) * e; }
    paintNow();
    if (t < 1) gliding = requestAnimationFrame(step);
    else if (firstFit) { firstFit = false; if (!sel) G.fit(); }
  };
  gliding = requestAnimationFrame(step);
}

// a point's size on screen (points grow only slightly as you zoom in)
// (forces); in the daisy layout they scale with the zoom like the layout itself, so petals never cover their centre
const screenR = d => radius(d) * P.size * (P.mode === 'daisy' ? Math.max(T.k, 0.12) : Math.pow(T.k, 0.2));
// the point under a finger or the pointer, if any (a target of at least 14 px round it)
function pick(x, y){
  let best = null, bd = Infinity;
  for (const n of ns) {
    const [sx, sy] = T.apply([n.x, n.y]), d = Math.hypot(sx - x, sy - y), r = Math.max(14, screenR(n) + 6);
    if (d < r && d < bd) { best = n; bd = d; }
  }
  return best;
}

// Labels: story themes and well-linked points always; the rest from the "names" zoom (two links or more from a
// little before it), or next to the selection.
function labelled(d, near){
  const k = T.k, t = P.names;
  return d.type === 'theme' || d.id === sel || near.has(d.id) || k >= t || (k >= t * 0.55 && d.deg >= 2) || d.deg >= 4;
}

function paintNow(){ cancelAnimationFrame(frame); paint(); }
function paint(){
  frame = 0;
  if (!G) return;
  ctx.clearRect(0, 0, W, H);
  const near = sel ? G.byId.get(sel).nb : new Set(), focus = !!sel;
  const lw = P.lines;
  // lines
  for (const pass of focus ? [0, 1] : [0]) {
    for (const l of ls) {
      const on = focus && (l.s === sel || l.t === sel);
      if (pass !== (on ? 1 : 0)) continue;
      const [x1, y1] = T.apply([l.source.x, l.source.y]), [x2, y2] = T.apply([l.target.x, l.target.y]);
      if (Math.max(x1, x2) < 0 || Math.min(x1, x2) > W || Math.max(y1, y2) < 0 || Math.min(y1, y2) > H) continue;
      ctx.globalAlpha = focus && !on ? 0.12 : 1;
      ctx.strokeStyle = on ? C.ink : C.edge;
      ctx.lineWidth = (on ? 1.8 : 1) * lw;
      ctx.setLineDash(l.how === 'mention' ? [3, 3] : []);
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    }
  }
  ctx.setLineDash([]);
  // points, then their names on top
  const names = [];
  for (const d of ns) {
    const [x, y] = T.apply([d.x, d.y]), r = screenR(d);
    if (x < -40 || x > W + 40 || y < -40 || y > H + 40) continue;
    const lit = !focus || d.id === sel || near.has(d.id);
    ctx.globalAlpha = lit ? 1 : 0.18;
    ctx.fillStyle = C.kind[kindKey(d.type)] || C.muted;
    ctx.beginPath();
    if (d.type === 'place') ctx.rect(x - r, y - r, 2 * r, 2 * r);
    else if (d.type === 'theme') { const q = r * 1.3; ctx.moveTo(x, y - q); ctx.lineTo(x + q, y); ctx.lineTo(x, y + q); ctx.lineTo(x - q, y); ctx.closePath(); }
    else ctx.arc(x, y, r, 0, 2 * Math.PI);
    ctx.fill();
    ctx.lineWidth = d.id === sel ? 2.5 : 1.5; ctx.strokeStyle = d.id === sel ? C.ink : C.bg; ctx.stroke();
    if (d.folds) {             // a ring: places folded into this point
      ctx.beginPath(); ctx.arc(x, y, r + 3, 0, 2 * Math.PI);
      ctx.lineWidth = 1.5; ctx.strokeStyle = C.kind.place; ctx.setLineDash([2, 2]); ctx.stroke(); ctx.setLineDash([]);
    }
    if (labelled(d, near)) names.push([d, x + r + 4 + (d.folds ? 3 : 0), y, lit]);
  }
  ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
  for (const [d, x, y, lit] of names) {
    ctx.globalAlpha = lit ? 1 : 0.18;
    ctx.font = `${d.id === sel ? 600 : 400} 12px ${C.sans}`;
    const text = d.label + (d.folds ? ` · ${d.folds}` : '');
    ctx.lineWidth = 3; ctx.strokeStyle = C.bg; ctx.strokeText(text, x, y);
    ctx.fillStyle = d.type === 'place' ? C.muted : C.ink; ctx.fillText(text, x, y);
  }
  ctx.globalAlpha = 1;
}

// ================= the Layout panel =================
function panel(){
  const fmt = (v, step) => step < 1 ? (+v).toFixed(step < 0.01 ? 3 : step < 0.1 ? 2 : 1) : String(v);
  const slider = ([k, t, lo, hi, step, help]) => `<label class="param"><span>${t}<output id="o-${k}">${fmt(P[k], step)}</output></span>
    <input type="range" id="p-${k}" min="${lo}" max="${hi}" step="${step}" value="${P[k]}" aria-describedby="h-${k}">
    <small id="h-${k}">${help}</small></label>`;
  const daisy = P.mode === 'daisy';
  $('params').innerHTML = `<div class="modes" role="radiogroup" aria-label="Layout">${[['daisy', 'Daisies'], ['force', 'Forces']].map(([m, t]) =>
      `<button role="radio" aria-checked="${P.mode === m}" data-mode="${m}">${t}</button>`).join('')}</div>`
    + '<h4>Display</h4>' + DISPLAY.map(slider).join('')
    + CHECKS.map(([k, t, help]) => `<label class="check"><input type="checkbox" id="p-${k}"${P[k] ? ' checked' : ''} aria-describedby="h-${k}">
        <span>${t}<small id="h-${k}">${help}</small></span></label>`).join('')
    + (daisy ? '<h4>Daisies</h4>' + DAISY.map(slider).join('')
       : '<h4>Forces</h4><p class="note">Shows how groups connect: shared places pull their people together.</p>' + FORCES.map(slider).join(''))
    + '<button class="reset" id="pReset">Reset</button>';
  $('params').querySelectorAll('[data-mode]').forEach(b => b.onclick = () => {
    if (P.mode === b.dataset.mode) return;
    P.mode = b.dataset.mode; saveP(); panel(); draw();
  });
  let again = 0;
  for (const [k, , , , step] of [...DISPLAY, ...(daisy ? DAISY : FORCES)]) $('p-' + k).oninput = e => {
    P[k] = +e.target.value; $('o-' + k).textContent = fmt(P[k], step); saveP();
    if (k === 'names' || k === 'lines') return redraw();
    if (daisy) { cancelAnimationFrame(again); again = requestAnimationFrame(daisyLayout); return; }
    forces(); sim.alpha(0.5).restart();
  };
  for (const [k] of CHECKS) $('p-' + k).onchange = e => { P[k] = e.target.checked; saveP(); draw(); };
  $('pReset').onclick = () => { Object.assign(P, DEFAULTS); saveP(); panel(); forces(); draw(); };
}

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
