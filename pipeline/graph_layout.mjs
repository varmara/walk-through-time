// The graph's layout, worked out during the build (called by pipeline/s08_graph.py), so a phone opening the graph
// starts from where the points settle rather than working it out itself.
//
//   node pipeline/graph_layout.mjs data/<city>-graph.json
//
// Uses the page's own layout code (app/city/graphlayout.js) and d3 (lib/d3.min.js); adds "x" and "y" to each
// point shown with the default settings (folded places have none: they sit at their owner until spread out).
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = new URL('..', import.meta.url);
const d3 = createRequire(import.meta.url)(fileURLToPath(new URL('lib/d3.min.js', root)));
// loaded from its text, so it runs as a module whatever the folder's package settings
const src = readFileSync(new URL('app/city/graphlayout.js', root), 'utf8');
const { settle } = await import('data:text/javascript;base64,' + Buffer.from(src).toString('base64'));

const file = process.argv[2];
const data = JSON.parse(readFileSync(file, 'utf8'));
const t0 = Date.now();
const at = settle(d3, data);
for (const n of data.nodes) {
  delete n.x; delete n.y;
  if (at[n.id]) [n.x, n.y] = at[n.id];
}
writeFileSync(file, JSON.stringify(data));
console.error(`graph layout: ${Object.keys(at).length} of ${data.nodes.length} points placed in ${Date.now() - t0} ms`);
