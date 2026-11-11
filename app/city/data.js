// Walk Through Time, city page: The data files: the index (s10_tiles), card files loaded when a card opens, OpenStreetMap ids for links, the gzipped tiles,
// place references (b<n> buildings, p<n> pins, a<n> areas) and stories as shown (plaque words from pins, templates).
import { CITY_ID, fetchJSON, store } from './util.js';
import { S } from './state.js';

           // building index -> [{name, bs}] for people and stories with several places
// The index (see pipeline/s10_tiles.py): one column per field, one value per building. Outlines come from the
// vector tiles; the rest of a card's details from a card file, when the card opens (loadCard).
export const FLAGS = { e:'exact', a:'approx', c:'century', r:'area' };
export function fromIndex(ix){
  const out = new Array(ix.n);
  if (!ix.dxy) {             // the index has only the few named, listed or layered buildings; the rest is in the card files
    for (let i = 0; i < ix.n; i++) out[i] = { properties: { ...(ix.props[i] || {}) } };
    return out;
  }
  let x = 0, y = 0;          // older index: every building's centre and year
  for (let i = 0; i < ix.n; i++) {
    x += ix.dxy[2 * i]; y += ix.dxy[2 * i + 1];
    const p = { ...(ix.props[i] || {}) };
    if (ix.y[i] != null) { p.y = ix.y[i]; p.f = FLAGS[ix.f[i]]; }
    if (ix.per[i] >= 0) { p.per = ix.periods[ix.per[i]]; p.sh = ix.sh[i]; }
    out[i] = { properties: p, xy: [ix.origin[0] + x / ix.scale, ix.origin[1] + y / ix.scale] };
  }
  return out;
}
export function standingBy(Y){
  if (!S.hist) return S.features.filter(x => x.properties.y != null ? x.properties.y <= Y : S.showUnknown).length;
  let n = S.showUnknown ? S.hist.undated : 0;
  for (const [y, c] of S.hist.years) { if (y > Y) break; n += c; }
  return n;
}
export const tiled = () => !!S.data.index;
export const fstate = (id, st) => S.map.setFeatureState(tiled() ? { source:'b', sourceLayer:'b', id } : { source:'b', id }, st);
export function loadCard(id){       // the card's details, merged into the building's properties
  if (!tiled() || S.features[id].full) return Promise.resolve();
  const n = Math.floor(id / S.data.tiles.chunk);
  S.cardFiles[n] = S.cardFiles[n] || fetchJSON(`../data/${CITY_ID}/cards/${n}.json?v=${S.data.build}`).catch(e => { delete S.cardFiles[n]; throw e; });
  return S.cardFiles[n].then(chunk => {
    for (const [i, extra] of Object.entries(chunk)) if (!S.features[i].full) { Object.assign(S.features[i].properties, extra); S.features[i].full = true; }
    S.features[id].full = true;
  });
}           // for links that name an OpenStreetMap id
export async function byOsm(osm){
  if (!tiled()) return S.features.findIndex(f => f.properties.osm === osm);
  S.osmIds = S.osmIds || await fetchJSON(`../data/${CITY_ID}/osm.json?v=${S.data.build}`);
  return S.osmIds.indexOf(osm);
}
// Gzipped vector tiles: GitHub Pages serves them as they are, so the page unpacks them itself.
if (window.DecompressionStream) maplibregl.addProtocol('gzt', async (params, abort) => {
  const r = await fetch(params.url.replace(/^gzt:/, location.protocol), { signal: abort.signal });
  if (r.status === 404 || r.status === 204) return { data: new ArrayBuffer(0) };      // no buildings in that tile
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const bytes = new Uint8Array(await r.arrayBuffer());
  if (bytes[0] !== 0x1f || bytes[1] !== 0x8b) return { data: bytes.buffer };          // already unpacked
  const out = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
  return { data: out };
});
try { S.active = new Set(JSON.parse(store.get('layers:' + CITY_ID) || '[]')); } catch {}
export const saveActive = () => store.set('layers:' + CITY_ID, JSON.stringify([...S.active]));
export const isArea = key => S.groups.get(key)?.layer.kind === 'areas';

// ================= Place references =================
// Layer items point at buildings (a number), pins ("p<index>": places that are not buildings, plaques on no
// building) or areas ("a<index>": conservation and nature areas).
export const parseRef = x => typeof x === 'number' ? x : /^\d+$/.test(x) ? +x : x;
export const isB = r => typeof r === 'number';
export const pinOf = r => S.data.pins.features[+r.slice(1)];
// an area: { properties, bb: [west, south, east, north] } from the index, or from the older file's GeoJSON
export function areaOf(r){
  const i = +r.slice(1);
  if (S.data.areas) return S.data.areas[i] && { properties: S.data.areas[i], bb: S.data.areas[i].bb };
  const f = S.data.nature.features[i];
  if (!f) return null;
  const pts = ringsOf(f.geometry).flat(), xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  return { properties: f.properties, bb: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)] };
}
export function ringsOf(g){ return g.type === 'Polygon' ? [g.coordinates[0]] : g.type === 'MultiPolygon' ? g.coordinates.map(p => p[0]) : []; }
export function refCentre(r){
  if (isB(r)) return centreOf(r);
  if (r[0] === 'p') return pinOf(r).geometry.coordinates;
  const b = areaOf(r).bb;
  return [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
}               // marker key -> maplibregl.Marker
export const centreOf = b => {
  if (S.features[b].xy) return S.features[b].xy;
  if (S.features[b].properties.xy) return S.features[b].properties.xy;     // from the card file
  const g = S.features[b].geometry;
  if (!g) return null;                                                  // not loaded yet
  const ring = g.type === 'Polygon' ? g.coordinates[0] : g.coordinates[0][0];
  return [ring.reduce((a, c) => a + c[0], 0) / ring.length, ring.reduce((a, c) => a + c[1], 0) / ring.length];
};
// a story as shown: a plaque's words are stored once, on its pin, and shown on its building's card too
// and words the same but for a name are a template (pipeline/texts.py: TEMPLATES): "Designed by {who}…"
export function storyOf(s){
  if (s.text) return s;
  if (s.tpl) return { ...s, text: (S.data.templates?.[s.tpl] || '').replace('{who}', s.who || '').replace('{of}', s.of || '') };
  if (!s.pin) return s;
  const pp = pinOf(s.pin)?.properties || {};
  const J = v => typeof v === 'string' ? JSON.parse(v) : v;
  return { ...s, text: pp.text || '', source: J(pp.source), who: s.who || pp.who };
}
export function storyFor(b, name){
  const ss = (S.features[b].properties.stories || []).map(storyOf).filter(s => s.text);
  return ss.find(s => s.text.includes(name) || (s.source && s.source.title === name)) || ss.find(s => s.layer === 'people') || ss[0];
}
