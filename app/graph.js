// Walk Through Time: the graph page. People and story themes, linked to the places where a checked story ties
// them (pipeline/s08_graph.py). Tap a point to see its links and the stories behind them; open them on the map
// with ./?focus=<place>,<place>.
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
const colour = k => `var(--k-${KIND_TITLE[k] ? k : 'other'})`;
const off = new Set();
let G, sel = null, sim, zoomK = 1;

fetch(`../data/${CITY}-graph.json?v=${window.__v || ''}`).then(r => r.json()).then(init)
  .catch(() => { $('loading').textContent = 'The graph could not be loaded.'; });

function init(data){
  G = data;
  $('loading').hidden = true;
  const byId = new Map(G.nodes.map(n => [n.id, n]));
  G.links = G.links.filter(l => byId.has(l.s) && byId.has(l.t)).map(l => ({ ...l, source: l.s, target: l.t }));
  G.nodes.forEach(n => { n.deg = 0; n.nb = new Set(); });
  G.links.forEach(l => { const a = byId.get(l.s), b = byId.get(l.t); a.deg++; b.deg++; a.nb.add(b.id); b.nb.add(a.id); });
  G.byId = byId;

  const present = new Set(G.nodes.map(n => n.type));
  $('kinds').innerHTML = KINDS.filter(([k]) => present.has(k)).map(([k, t]) =>
    `<button class="kind" data-k="${k}"><i style="background:${colour(k)}"></i>${t}</button>`).join('');
  $('kinds').querySelectorAll('.kind').forEach(b => b.onclick = () => {
    off.has(b.dataset.k) ? off.delete(b.dataset.k) : off.add(b.dataset.k);
    b.classList.toggle('off', off.has(b.dataset.k)); draw();
  });

  const svg = d3.select('#graph');
  const root = svg.append('g');
  G.edgeG = root.append('g');
  G.nodeG = root.append('g');
  // Zooming moves the drawing but keeps text, lines and points about the same size on screen (as in Obsidian),
  // so zooming in spreads points apart instead of blowing up the labels. Labels are updated once per frame.
  let frame = 0;
  const zoom = d3.zoom().scaleExtent([0.2, 8]).clickDistance(6).on('zoom', e => {
    root.attr('transform', e.transform); zoomK = e.transform.k;
    if (!frame) frame = requestAnimationFrame(() => { frame = 0; sizes(); labels(); });
  });
  svg.call(zoom);
  // buttons as well as pinching: on a phone the points can be too close together to pinch between. They zoom
  // about the selected point when there is one, so it stays in view, or else the middle of the screen
  const step = f => {
    const n = sel && G.byId.get(sel), t = d3.zoomTransform(svg.node());
    const at = n && n.x != null ? t.apply([n.x, n.y]) : [innerWidth / 2, innerHeight / 2];
    svg.transition().duration(250).call(zoom.scaleBy, f, at);
  };
  $('zIn').onclick = () => step(1.6);
  $('zOut').onclick = () => step(1 / 1.6);
  $('zFit').onclick = () => G.fit();
  svg.on('click', e => { if (e.target === svg.node()) select(null); });
  G.zoomTo = (x, y) => svg.transition().duration(600).call(zoom.transform,
    d3.zoomIdentity.translate(innerWidth / 2, innerHeight * (innerWidth >= 760 ? 0.5 : 0.3)).scale(Math.max(zoomK, 1.4)).translate(-x, -y));
  // once the layout settles the first time, fit the whole graph on the screen
  let fitted = false;
  G.fit = () => {
    const ns = sim.nodes(); if (!ns.length) return;
    const xs = ns.map(n => n.x), ys = ns.map(n => n.y), top = 110;
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const k = Math.max(0.25, Math.min(3, 0.92 * Math.min(innerWidth / (x1 - x0 || 1), (innerHeight - top - 40) / (y1 - y0 || 1))));
    svg.transition().duration(700).call(zoom.transform, d3.zoomIdentity
      .translate(innerWidth / 2, top + (innerHeight - top - 40) / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2));
  };

  sim = d3.forceSimulation().force('link', d3.forceLink().id(d => d.id)).force('charge', d3.forceManyBody().distanceMax(260))
    .force('collide', d3.forceCollide()).force('x', d3.forceX(d => anchor(d)[0])).force('y', d3.forceY(d => anchor(d)[1]))
    .on('tick', tick).on('end', () => { if (!fitted) { fitted = true; if (!sel) G.fit(); } });
  forces();
  layoutPanel();
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

// ================= the layout's forces, set from the Layout panel (kept in this browser) =================
//   group    how strongly each person or theme is pulled to its kind's spot (points of one colour together)
//   links    how strongly a line pulls its two ends together (places to the people and themes they belong to)
//   length   how long the lines try to be
//   repel    how strongly points push each other apart
//   space    the gap kept round each point
//   places   how strongly places are pulled to the middle (low: they stay by the points they are linked to)
const DEFAULTS = { group: 0.14, links: 0.9, length: 34, repel: 1, space: 3, places: 0.015 };
const PARAMS = [
  ['group', 'Group by colour', 0, 0.5, 0.01], ['links', 'Pull along links', 0, 1, 0.05],
  ['length', 'Link length', 10, 120, 2], ['repel', 'Push apart', 0, 3, 0.1],
  ['space', 'Space round points', 0, 20, 1], ['places', 'Places to the middle', 0, 0.15, 0.005],
];
const P = { ...DEFAULTS };
try { Object.assign(P, JSON.parse(localStorage.getItem('graph-layout') || '{}')); } catch {}
const saveP = () => { try { localStorage.setItem('graph-layout', JSON.stringify(P)); } catch {} };
function forces(){
  sim.force('link').distance(l => P.length * (l.how === 'mention' ? 1.6 : 1)).strength(P.links);
  sim.force('charge').strength(d => P.repel * (d.type === 'theme' ? -220 : d.deg > 1 ? -60 : -25));
  sim.force('collide').radius(d => radius(d) + P.space);
  sim.force('x').strength(d => d.type === 'place' ? P.places : P.group);
  sim.force('y').strength(d => d.type === 'place' ? P.places * 1.2 : P.group);
}
function layoutPanel(){
  const fmt = (v, step) => step < 1 ? (+v).toFixed(step < 0.01 ? 3 : 2) : String(v);
  $('params').innerHTML = PARAMS.map(([k, t, lo, hi, step]) => `<label class="param"><span>${t}<output id="o-${k}">${fmt(P[k], step)}</output></span>
    <input type="range" id="p-${k}" min="${lo}" max="${hi}" step="${step}" value="${P[k]}"></label>`).join('')
    + '<button class="reset" id="pReset">Reset</button>';
  for (const [k, , , , step] of PARAMS) $('p-' + k).oninput = e => {
    P[k] = +e.target.value; $('o-' + k).textContent = fmt(P[k], step); saveP();
    forces(); sim.alpha(0.5).restart();
  };
  $('pReset').onclick = () => { Object.assign(P, DEFAULTS); saveP(); layoutPanel(); forces(); sim.alpha(0.8).restart(); };
}

// Points of one kind (one colour) gather together: each kind is pulled towards its own spot on a circle round the
// middle, in the order of the kinds row; places are pulled only lightly, so they settle between the people and
// themes they are linked to. The spots are shared out again among the kinds shown when one is switched off.
let spots = {};
function placeSpots(ns){
  const kinds = KINDS.map(k => k[0]).filter(k => k !== 'place' && ns.some(n => n.type === k));
  const R = 120 + 28 * kinds.length, cx = innerWidth / 2, cy = innerHeight / 2;
  spots = Object.fromEntries(kinds.map((k, i) => {
    const a = -Math.PI / 2 + 2 * Math.PI * i / kinds.length;
    return [k, [cx + R * Math.cos(a), cy + R * Math.sin(a)]];
  }));
}
function anchor(d){ return spots[d.type] || [innerWidth / 2, innerHeight / 2]; }

function radius(d){ return d.type === 'theme' ? 11 : d.type === 'place' ? 4 + Math.min(4, d.deg) : 5 + Math.min(7, d.deg * 1.2); }
function shown(){ const ns = G.nodes.filter(n => !off.has(n.type)), ids = new Set(ns.map(n => n.id));
  return { ns, ls: G.links.filter(l => ids.has(l.s) && ids.has(l.t)) }; }

function draw(){
  const { ns, ls } = shown();
  G.edges = G.edgeG.selectAll('line').data(ls, l => l.s + '|' + l.t)
    .join('line').attr('class', l => 'edge' + (l.how === 'mention' ? ' mention' : ''));
  G.nodesSel = G.nodeG.selectAll('g.node').data(ns, d => d.id).join(enter => {
    const g = enter.append('g').attr('class', d => 'node ' + d.type);
    g.each(function(d){
      const s = d3.select(this), r = radius(d);
      if (d.type === 'place') s.append('rect').attr('class', 'shape').attr('x', -r).attr('y', -r).attr('width', 2 * r).attr('height', 2 * r).attr('rx', 1.5);
      else if (d.type === 'theme') s.append('path').attr('class', 'shape').attr('d', `M0,${-r * 1.3}L${r * 1.3},0L0,${r * 1.3}L${-r * 1.3},0Z`);
      else s.append('circle').attr('class', 'shape').attr('r', r);
      s.select('.shape').attr('fill', colour(d.type));
      s.append('circle').attr('class', 'hit').attr('r', Math.max(14, r + 6));   // a bigger target for fingers
      s.append('text').attr('y', 4).text(d.label);
    });
    g.on('click', (e, d) => { e.stopPropagation(); select(d.id); });
    g.call(d3.drag().clickDistance(6)
      .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.06).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end', (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = d.fy = null; }));
    return g;
  });
  placeSpots(ns);               // before sim.nodes, which reads each point's spot
  sim.nodes(ns); sim.force('link').links(ls); sim.alpha(0.8).restart();
  sizes(); highlight(); labels();
}

function tick(){
  G.edges.attr('x1', l => l.source.x).attr('y1', l => l.source.y).attr('x2', l => l.target.x).attr('y2', l => l.target.y);
  G.nodesSel.attr('transform', d => `translate(${d.x},${d.y})`);
}

// Screen-constant sizes: text stays 12 px and points grow only slightly as you zoom in.
function sizes(){
  if (!G.nodesSel) return;
  const k = zoomK, shape = Math.pow(k, -0.8);
  G.nodeG.style('font-size', (12 / k) + 'px').style('stroke-width', (3 / k) + 'px');
  G.nodesSel.select('.shape').attr('transform', `scale(${shape})`);
  G.nodesSel.select('.hit').attr('transform', `scale(${1 / k})`);
  G.nodesSel.select('text').attr('x', d => radius(d) * shape + 4 / k).attr('y', 4 / k);
}

// Labels: story themes and well-linked points always; the rest once zoomed in, or when next to the selection.
function labels(){
  if (!G.nodesSel) return;
  const near = sel ? G.byId.get(sel).nb : new Set();
  G.nodesSel.select('text').attr('display', d =>
    d.type === 'theme' || d.id === sel || near.has(d.id) || zoomK >= 2.2 || (zoomK >= 1.2 && d.deg >= 2) || d.deg >= 4 ? null : 'none');
}

function highlight(){
  const near = sel ? G.byId.get(sel).nb : null;
  d3.select('#graph').classed('focus', !!sel);
  G.nodesSel.classed('on', d => !!sel && (d.id === sel || near.has(d.id))).classed('sel', d => d.id === sel);
  G.edges.classed('on', l => !!sel && (l.s === sel || l.t === sel));
}

// on a phone the sheet covers the bottom of the screen: the zoom buttons sit just above it
function placeZoom(){
  const open = !$('sheet').hidden && innerWidth < 760;
  $('zoom').style.bottom = open ? `${$('sheet').offsetHeight + 12}px` : '';
}
addEventListener('resize', () => G && placeZoom());

function select(id){
  sel = id;
  highlight(); labels();
  requestAnimationFrame(placeZoom);
  if (!id) { $('sheet').hidden = true; $('hint').hidden = false; return; }
  const n = G.byId.get(id);
  $('hint').hidden = true; $('sheet').hidden = false;
  $('sTitle').textContent = n.label;
  $('sType').textContent = n.type === 'place'
    ? 'Place' + (n.year != null ? ' · ' + (n.f === 'area' ? 'probably ' : n.f === 'exact' ? '' : 'c. ') + n.year : '')
    : KIND_TITLE[n.type] ? KIND_TITLE[n.type].replace(/s$/, '').replace('Story theme', 'Story theme') : n.type;
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
      <button data-id="${esc(o.id)}"><i style="background:${colour(o.type)}"></i>${esc(o.label)}</button>
      ${l.text ? `<p>${esc(l.text)}</p>` : ''}
      ${l.src && l.src.url ? `<div class="src">${l.how === 'mention' ? 'Named in this story · ' : ''}${esc(l.src.kind || 'Source')}: <a href="${esc(l.src.url)}" target="_blank" rel="noopener">${esc(l.src.title)}</a></div>` : ''}
    </div>`).join('')).join('');
  $('links').scrollTop = 0;
  $('links').querySelectorAll('[data-id]').forEach(b => b.onclick = () => { const o = G.byId.get(b.dataset.id); select(o.id); G.zoomTo(o.x, o.y); });
}
})();
