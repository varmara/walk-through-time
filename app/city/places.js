// Walk Through Time, city page: Places: one person or story with several buildings, as numbered pins and a strip of cards that swipe sideways.
import { $, dateText, eraOf, esc } from './util.js';
import { S } from './state.js';
import { fstate, isB, loadCard, parseRef, refCentre, refOf, storyFor } from './data.js';
import { buildingColour } from './map.js';
import { closeSheet } from './sheet.js';
import { openRef, refName } from './cards.js';

export function showPlaces(name, bs){
  // the stories' words are in the card files: fetch those first (one or two files for most people and stories)
  const need = bs.filter(isB).filter(b => !S.features[b].full);
  if (need.length) return Promise.all(need.map(b => loadCard(b).catch(() => {}))).then(() => showPlaces(name, bs));
  closeSheet();
  clearPlaces(false);
  S.places = { name, bs, i: 0 };
  bs.filter(isB).forEach(b => fstate(b, { hl:true }));
  S.map.setPaintProperty('b', 'fill-extrusion-color', buildingColour());
  S.map.getSource('places').setData({ type:'FeatureCollection', features: bs.map((b, i) =>
    ({ type:'Feature', properties:{ n: i + 1 }, geometry:{ type:'Point', coordinates: refCentre(b) } })) });
  $('pName').textContent = name;
  $('pCards').innerHTML = bs.map((b, i) => {
    if (!isB(b)) {
      const pp = refOf(b).properties;
      return `<article class="pcard" data-i="${i}"><div class="pnum">${i + 1}</div><h3>${esc(refName(b))}</h3>
        ${pp.text ? `<p>${esc(pp.text)}</p>` : ''}<button class="textbtn" data-open="${b}">Details</button></article>`;
    }
    const p = S.features[b].properties, st = storyFor(b, name), era = p.y != null ? eraOf(p.y) : null;
    return `<article class="pcard" data-i="${i}">
      <div class="pnum">${i + 1}</div>
      <h3>${esc(refName(b))}</h3>
      ${p.y != null ? `<div class="pmeta">${esc(dateText(p.y, p.f, p.per, p.dt))}<span class="pill" style="border-color:${era[3]}">${esc(era[2])}</span></div>` : ''}
      ${st ? `<p>${esc(st.text)}</p>` : ''}
      <button class="textbtn" data-open="${b}">Details</button></article>`;
  }).join('');
  $('pCards').querySelectorAll('[data-open]').forEach(btn => btn.onclick = () => openRef(parseRef(btn.dataset.open)));
  $('placesbar').hidden = false; $('timebar').hidden = true;
  $('pCards').scrollLeft = 0;
  setPlace(0, false);
  const pts = bs.map(refCentre), lons = pts.map(p => p[0]), lats = pts.map(p => p[1]);
  S.map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
    { padding: { top: 90, left: 40, right: 70, bottom: $('placesbar').offsetHeight + 40 }, maxZoom: 16.5, duration: 900 });
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
