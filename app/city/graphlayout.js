// Walk Through Time: the graph's layout, shared by the map page (app/city/graph.js) and the build
// (pipeline/graph_layout.mjs), so the build can work the layout out once and the page start from it.
// Nothing here touches the page: d3 is passed in, and nothing is imported (the build loads this file as it is).
//
// Laid out as Obsidian's graph view is: a force-directed layout (centre, repel, link force, link distance), with
// one force of our own (group: people and themes of one colour pulled to their own area), and one thing of our own
// in what is shown: a place linked to only one person or theme is folded into it.

export const KINDS = [
  ['theme', 'Story themes'], ['architects', 'Architects'], ['writers', 'Writers'], ['science', 'Science'],
  ['industry', 'Industry'], ['sport', 'Sport'], ['arts', 'Arts'], ['faith', 'Faith'], ['military', 'Military'],
  ['public', 'Public life'], ['events', 'Events'], ['other', 'Other people'], ['place', 'Places'],
];

// Filters  fold: places with one link folded into their person or theme;  orphans: show points with no lines
// Groups   off: the kinds (colours) switched off
// Display  fade: Obsidian's text fade threshold;  size: node size;  lines: link thickness
// Forces   centre, repel, link, distance (Obsidian's four), group (ours)
export const DEFAULTS = { fold: true, orphans: true, off: [], fade: 0, size: 1, lines: 1,
  centre: 0.5, repel: 10, link: 1, distance: 30, group: 0.5 };
// the settings that change where points go: when they are all as here, the build's layout is the page's
export const LAYOUT_KEYS = ['fold', 'orphans', 'centre', 'repel', 'link', 'distance', 'group', 'size'];
export const isDefaultLayout = (P, off) => !off.size && LAYOUT_KEYS.every(k => P[k] === DEFAULTS[k]);

// links, each point's links and neighbours, and the owner of a place with only one link
export function prepare(G){
  const byId = new Map(G.nodes.map(n => [n.id, n]));
  G.links = G.links.filter(l => byId.has(l.s) && byId.has(l.t)).map(l => ({ ...l, source: l.s, target: l.t }));
  G.nodes.forEach(n => { n.deg = 0; n.nb = new Set(); });
  G.links.forEach(l => { const a = byId.get(l.s), b = byId.get(l.t); a.deg++; b.deg++; a.nb.add(b.id); b.nb.add(a.id); });
  G.nodes.forEach(n => { if (n.type === 'place' && n.nb.size === 1) { const o = byId.get([...n.nb][0]); if (o.type !== 'place') n.owner = o; } });
  G.byId = byId;
  return G;
}

// the points and lines shown: switched-off kinds left out, folded places counted into their owner (except the
// owner spread out, `spreadId`), and points with no lines left out when orphans are off (except `keep`)
export function visible(G, P, off, spreadId, keep, random = Math.random){
  const folded = n => P.fold && n.owner && n.owner.id !== spreadId && !off.has(n.owner.type);
  G.nodes.forEach(n => { n.folds = 0; });
  G.nodes.forEach(n => { if (!off.has(n.type) && folded(n)) n.owner.folds++; });
  let vis = G.nodes.filter(n => !off.has(n.type) && !folded(n));
  const ids = new Set(vis.map(n => n.id));
  const ls = G.links.filter(l => ids.has(l.s) && ids.has(l.t));
  if (!P.orphans) {
    const linked = new Set(ls.flatMap(l => [l.s, l.t]));
    vis = vis.filter(n => linked.has(n.id) || n.folds || n.id === keep);
  }
  // a place spread out starts at its owner, so it grows out of it
  for (const n of vis) if (n.owner && n.owner.x != null && (n.x == null || n.hidden)) {
    const a = random() * 2 * Math.PI; n.x = n.owner.x + 8 * Math.cos(a); n.y = n.owner.y + 8 * Math.sin(a); n.vx = n.vy = 0;
  }
  G.nodes.forEach(n => { n.hidden = true; }); vis.forEach(n => { n.hidden = false; });
  return { ns: vis, ls };
}

// Each colour's area: the biggest group in the middle, the others round it, further out the more there are;
// places have none (they follow their lines)
export function groupSpots(d3, ns){
  const count = d3.rollup(ns.filter(n => n.type !== 'place'), v => v.length, n => n.type);
  const kinds = [...count].sort((a, b) => b[1] - a[1]).map(k => k[0]);
  const R = 9 * Math.sqrt(ns.length) + 40, m = Math.max(1, kinds.length - 1);
  return Object.fromEntries(kinds.map((k, i) => i === 0 ? [k, [0, 0]]
    : [k, [R * Math.cos(2 * Math.PI * (i - 1) / m - Math.PI / 2), R * Math.sin(2 * Math.PI * (i - 1) / m - Math.PI / 2)]]));
}

// a point's size: grows with its links (and the places folded into it), as Obsidian's do
export const radius = (d, P) => P.size * (3 + 1.6 * Math.sqrt(d.deg + (d.folds || 0)));

export function simulation(d3){
  return d3.forceSimulation().force('link', d3.forceLink().id(d => d.id)).force('charge', d3.forceManyBody())
    .force('x', d3.forceX(0)).force('y', d3.forceY(0)).force('collide', d3.forceCollide())
    .force('gx', d3.forceX(0)).force('gy', d3.forceY(0));
}

export function forces(sim, P, spots){
  const spotOf = d => spots[d.type] || [0, 0];
  // the centre force acts less on people and themes while they are grouped, so their areas can sit apart
  const c = d => P.centre * 0.1 * (d.type !== 'place' && P.group ? 1 - 0.8 * P.group : 1);
  sim.force('x').strength(c); sim.force('y').strength(c);
  const g = d => d.type === 'place' ? 0 : P.group * 0.12;
  sim.force('gx').x(d => spotOf(d)[0]).strength(g); sim.force('gy').y(d => spotOf(d)[1]).strength(g);
  sim.force('charge').strength(d => -P.repel * 6 * (1 + Math.sqrt(d.folds || 0) * 0.4)).distanceMax(400);
  sim.force('link').strength(P.link).distance(P.distance);
  sim.force('collide').radius(d => radius(d, P) + 1);
}

// The build's layout: the default settings, run until it settles. Returns {id: [x, y]} for the points shown.
export function settle(d3, data){
  const G = prepare({ nodes: data.nodes.map(n => ({ ...n })), links: data.links });
  const P = { ...DEFAULTS }, off = new Set();
  let seed = 1;
  const random = () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296);
  const { ns, ls } = visible(G, P, off, null, null, random);
  const sim = simulation(d3).stop();
  sim.nodes(ns); sim.force('link').links(ls);
  forces(sim, P, groupSpots(d3, ns));
  sim.alpha(0.6);
  for (let i = 0; i < 600 && sim.alpha() > sim.alphaMin(); i++) sim.tick();
  return Object.fromEntries(ns.map(n => [n.id, [Math.round(n.x * 10) / 10, Math.round(n.y * 10) / 10]]));
}
