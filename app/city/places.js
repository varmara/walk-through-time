// Walk Through Time, city page: Places: one person or story with several buildings, as numbered pins and a strip of cards that swipe sideways.
import { $, dateText, eraOf, esc } from './util.js';
import { S } from './state.js';
import { fstate, isB, loadCard, parseRef, refCentre, refOf, storyFor, tiled } from './data.js';
import { buildingColour } from './map.js';
import { closeSheet } from './sheet.js';
import { openRef, refName } from './cards.js';

// A place's card in the strip: its name, date and the story that ties it to the set; a building whose card file
// has not arrived yet shows its name (from the index) and fills in when the file comes (fillCard)
function cardHtml(b, i, name, hint){
  if (!isB(b)) {
    const pp = refOf(b).properties;
    return `<div class="pnum">${i + 1}</div><h3>${esc(refName(b))}</h3>
      ${pp.text ? `<p>${esc(pp.text)}</p>` : ''}<button class="textbtn" data-open="${b}">Details</button>`;
  }
  const f = S.features[b], p = f.properties;
  if (!f.full && tiled()) return `<div class="pnum">${i + 1}</div><h3>${esc(refName(b))}</h3><p class="pwait">Loading…</p>
    <button class="textbtn" data-open="${b}">Details</button>`;
  const st = storyFor(b, hint?.name || name, hint?.layer), era = p.y != null ? eraOf(p.y) : null;
  return `<div class="pnum">${i + 1}</div>
    <h3>${esc(refName(b))}</h3>
    ${p.y != null ? `<div class="pmeta">${esc(dateText(p.y, p.f, p.per, p.dt))}<span class="pill" style="border-color:${era[3]}">${esc(era[2])}</span></div>` : ''}
    ${st ? `<p>${esc(st.text)}</p>` : ''}
    <button class="textbtn" data-open="${b}">Details</button>`;
}
function fillCard(i){
  const P = S.places, el = P && $('pCards').querySelector(`[data-i="${i}"]`);
  if (!el || el.dataset.full) return;
  if (isB(P.bs[i]) && !S.features[P.bs[i]].full && tiled()) return;
  el.innerHTML = cardHtml(P.bs[i], i, P.name, P.hints?.[i]); el.dataset.full = '1';
  el.querySelector('[data-open]').onclick = () => openRef(parseRef(el.querySelector('[data-open]').dataset.open));
}
// the cards round the one in view, loaded first (a big set, as a group from the graph, has places in dozens of
// card files: they come as you swipe, not all before the strip shows)
function loadAround(i){
  const P = S.places; if (!P) return;
  for (let j = Math.max(0, i - 3); j < Math.min(P.bs.length, i + 9); j++) {
    const b = P.bs[j];
    if (!isB(b) || S.features[b].full || !tiled()) { fillCard(j); continue; }
    loadCard(b).then(() => { if (S.places === P) fillCard(j); }).catch(() => {});
  }
}

// hints: for each place, the name and story layer of what put it in the set (a group's or a topic's items), so its
// card tells that story
export function showPlaces(name, bs, hints){
  // the stories' words are in the card files. A small set (a person, a story: one or two files) waits for them,
  // showing the bar meanwhile; a big set, or one whose places' whereabouts need the files, shows at once
  // (the single data file, with no card files: every building is complete already)
  const need = tiled() ? bs.filter(isB).filter(b => !S.features[b].full) : [];
  const placed = bs.every(b => refCentre(b));
  if (need.length && (need.length <= 12 || !placed)) {
    $('pName').textContent = name; $('pCount').textContent = '';
    $('pCards').innerHTML = `<p class="pwait">Finding ${bs.length} ${bs.length === 1 ? 'place' : 'places'}…</p>`;
    $('placesbar').hidden = false; $('timebar').hidden = true;
    return Promise.all(need.map(b => loadCard(b).catch(() => {}))).then(() => showPlaces(name, bs, hints));
  }
  closeSheet();
  clearPlaces(false);
  S.places = { name, bs, hints, i: 0 };
  bs.filter(isB).forEach(b => fstate(b, { hl:true }));
  S.map.setPaintProperty('b', 'fill-extrusion-color', buildingColour());
  S.map.getSource('places').setData({ type:'FeatureCollection', features: bs.map((b, i) =>
    ({ type:'Feature', properties:{ n: i + 1 }, geometry:{ type:'Point', coordinates: refCentre(b) } })) });
  $('pName').textContent = name;
  $('pCards').innerHTML = bs.map((b, i) => `<article class="pcard" data-i="${i}"${!isB(b) || S.features[b].full || !tiled() ? ' data-full="1"' : ''}>${cardHtml(b, i, name, hints?.[i])}</article>`).join('');
  $('pCards').querySelectorAll('[data-open]').forEach(btn => btn.onclick = () => openRef(parseRef(btn.dataset.open)));
  $('placesbar').hidden = false; $('timebar').hidden = true;
  $('pCards').scrollLeft = 0;
  setPlace(0, false);
  const pts = bs.map(refCentre), lons = pts.map(p => p[0]), lats = pts.map(p => p[1]);
  S.map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
    { padding: { top: 90, left: 40, right: 70, bottom: $('placesbar').offsetHeight + 40 }, maxZoom: 16.5, duration: 900 });
}
// a layer's groups (or a whole story layer or topic, by its id) as one set of numbered cards, in the build's date
// order, item by item, each place once. Returns false when there is nothing to show
export function showGroups(keys, title){
  const seen = new Set(), refs = [], hints = [];
  for (const k of keys) {
    const g = S.groups.get(k); if (!g) continue;
    for (const it of g.items || []) {
      const rs = typeof it[0] === 'number' ? [it[0]] : it[1], name = typeof it[0] === 'number' ? it[1] : it[0];
      const h = it[2] || {}, layer = h.layer || (g.layer.kind === 'stories' ? g.layer.id : h.person || h.plaque ? 'people' : null);
      for (const r of rs.map(x => typeof x === 'number' ? x : parseRef(String(x))))
        if (!seen.has(r)) { seen.add(r); refs.push(r); hints.push({ name, layer }); }
    }
  }
  if (!refs.length) return false;
  showPlaces(title, refs, hints);
  return true;
}
export function setPlace(i, fly = true){
  if (!S.places) return;
  S.places.i = i;
  $('pCount').textContent = `${i + 1} of ${S.places.bs.length}`;
  if (S.selectedId != null) fstate(S.selectedId, { sel:false });
  S.selectedId = isB(S.places.bs[i]) ? S.places.bs[i] : null;
  if (S.selectedId != null) fstate(S.selectedId, { sel:true });
  Object.entries(S.pins).forEach(([k, m]) => m.getElement().classList.toggle('on', k === 'p' + (i + 1)));
  $('pCards').querySelectorAll('.pcard').forEach(c => c.classList.toggle('on', +c.dataset.i === i));
  loadAround(i);
  if (fly) S.map.easeTo({ center: refCentre(S.places.bs[i]), zoom: Math.max(S.map.getZoom(), 16.5), duration: 700,
    padding: { bottom: $('placesbar').offsetHeight + 20 } });
}
export function goToCard(i){
  const card = $('pCards').querySelector(`[data-i="${i}"]`);
  if (card) $('pCards').scrollTo({ left: card.offsetLeft - 12, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
}
export let scrollTimer;
$('pCards').addEventListener('scroll', () => {
  clearTimeout(scrollTimer);
  scrollTimer = setTimeout(() => {
    const cards = [...$('pCards').querySelectorAll('.pcard')], x = $('pCards').scrollLeft;
    let best = 0;
    cards.forEach((c, i) => { if (Math.abs(c.offsetLeft - 12 - x) < Math.abs(cards[best].offsetLeft - 12 - x)) best = i; });
    if (S.places && best !== S.places.i) setPlace(best);
  }, 120);
});
$('pPrev').onclick = () => S.places && goToCard(Math.max(0, S.places.i - 1));
$('pNext').onclick = () => S.places && goToCard(Math.min(S.places.bs.length - 1, S.places.i + 1));
$('pClose').onclick = () => clearPlaces(true);
export function clearPlaces(showTime){
  if (S.places) S.places.bs.filter(isB).forEach(b => fstate(b, { hl:false }));
  if (S.selectedId != null) { fstate(S.selectedId, { sel:false }); S.selectedId = null; }
  S.places = null;
  if (S.map && S.map.getLayer('b')) S.map.setPaintProperty('b', 'fill-extrusion-color', buildingColour());
  if (S.map && S.map.getSource('places')) S.map.getSource('places').setData({ type:'FeatureCollection', features:[] });
  Object.keys(S.pins).forEach(k => { S.pins[k].remove(); delete S.pins[k]; });
  $('placesbar').hidden = true;
  if (showTime) $('timebar').hidden = false;
}
export function drawPins(){
  if (!S.map || !S.map.getSource('places')) return;
  const seen = new Set();
  for (const f of S.map.querySourceFeatures('places')) {
    const pr = f.properties, cl = pr.cluster;
    const key = cl ? 'c' + pr.cluster_id : 'p' + pr.n;
    if (seen.has(key)) continue;
    seen.add(key);
    if (!S.pins[key]) {
      const el = document.createElement('button');
      el.className = cl ? 'pin cluster' : 'pin';
      el.textContent = cl ? pr.point_count : pr.n;
      el.setAttribute('aria-label', cl ? `${pr.point_count} places here: zoom in` : `Place ${pr.n}`);
      el.onclick = e => {
        e.stopPropagation();
        if (cl) S.map.getSource('places').getClusterExpansionZoom(pr.cluster_id)
          .then(z => S.map.easeTo({ center: f.geometry.coordinates, zoom: z + 0.3 }));
        else goToCard(pr.n - 1);
      };
      S.pins[key] = new maplibregl.Marker({ element: el }).setLngLat(f.geometry.coordinates).addTo(S.map);
    }
    if (!cl) S.pins[key].getElement().classList.toggle('on', S.places && pr.n === S.places.i + 1);
  }
  Object.keys(S.pins).forEach(k => { if (!seen.has(k)) { S.pins[k].remove(); delete S.pins[k]; } });
}
