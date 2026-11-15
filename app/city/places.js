// Walk Through Time, city page: Places: one person or story with several buildings, as numbered pins and a strip of cards that swipe sideways.
import { $, dateText, eraOf, esc, whenText } from './util.js';
import { S } from './state.js';
import { fstate, isB, loadCard, parseRef, refCentre, refOf, storyFor, tiled } from './data.js';
import { paintBuildings } from './map.js';
import { closeSheet } from './sheet.js';
import { openRef, refName, whoBrief } from './cards.js';

// A place's card in the strip: its name, date and the story that ties it to the set; a building whose card file
// has not arrived yet shows its name (from the index) and fills in when the file comes (fillCard)
const plain = t => String(t).replace(/\[\^[\w-]+\]/g, '');      // (footnote marks belong to the full card)
// the year a text tells of, as the build orders by it (pipeline/layerdata.year_in): a plaque's words, not when it
// was put up; "the 12th century" as it is written
function toldIn(text){
  let t = String(text || ''); if (t.includes('“')) t = t.split('“')[1];
  const ys = [...t.matchAll(/(?<![\d,.£$])\b(1[0-9]{3}|20[0-9]{2})\b(?![,.]\d)/g)].map(m => [m.index, m[1]]);
  const cs = [...t.matchAll(/\b(\d{1,2}(?:st|nd|rd|th))[ -]century/gi)].map(m => [m.index, m[1] + ' century']);
  const all = [...ys, ...cs].sort((a, b) => a[0] - b[0]);
  return all.length ? all[0][1] : '';
}
// a card's heading: the story or person that put the place in the set, and where it is, when the place has
// another name ("The castle burned, 1831 · at Nottingham Castle"; "Lucy Hutchinson · at Owthorpe")
function heading(b, told){
  const at = refName(b);
  return told && told !== at ? `<h3>${esc(told)}</h3><div class="pmeta pat">${/^(Plaque|Statue|Memorial)\b/.test(at) ? '' : 'At '}${esc(at)}</div>` : `<h3>${esc(at)}</h3>`;
}
function cardHtml(b, i, name, hint){
  if (!isB(b)) {
    const pp = refOf(b).properties, wt = whenText(pp.when, pp.made, hint?.when) || toldIn(pp.text);
    // a plaque: its words, what happened here, and who the person was
    return `<div class="pnum">${i + 1}</div>${heading(b, hint?.person ? hint.name : pp.nm)}
      ${wt ? `<div class="pmeta pwhen">${esc(wt)}</div>` : ''}
      ${pp.text ? `<p>${esc(plain(pp.text))}</p>` : ''}${pp.here ? `<p class="phere">${esc(pp.here)}</p>` : ''}${pp.who && !pp.own ? whoBrief(pp.who) : ''}
      <button class="textbtn" data-open="${b}">Details</button>`;
  }
  const f = S.features[b], p = f.properties;
  if (!f.full && tiled()) return `<div class="pnum">${i + 1}</div><h3>${esc(refName(b))}</h3><p class="pwait">Loading…</p>
    <button class="textbtn" data-open="${b}">Details</button>`;
  const st = storyFor(b, hint?.name || name, hint?.layer), era = p.y != null ? eraOf(p.y) : null;
  // the story's date (what the set is ordered by); the building's own, when the story tells of none
  let wt = whenText(st?.when, st?.made, hint?.when) || (st && toldIn(st.text));
  // the building's own story dated otherwise than the building: both dates (Severn's Building: the article's
  // c. 1450, the map's 1335; Nottingham Castle: the first castle, 1068, and the mansion standing, 1674–79)
  const own = st?.nm && st.nm === refName(b) && !hint?.person;
  const yr = w => +(/(\d{1,2})(?:st|nd|rd|th) century/.exec(w || '')?.[1] - 1) * 100 || +(/\d{3,4}/.exec(w || '') || [NaN])[0];
  if (own && wt && p.y != null && !hint?.when && Math.abs(yr(st.when) - p.y) >= 10)
    wt += ' · building ' + dateText(p.y, p.f, p.per, p.dt).replace(/^built (in |about )?/, '').replace(/^[A-Z](?=[a-z])/, c => c.toLowerCase());
  return `<div class="pnum">${i + 1}</div>
    ${heading(b, hint?.person ? hint.name : st?.nm)}
    ${wt ? `<div class="pmeta pwhen">${esc(wt)}</div>`
      : p.y != null ? `<div class="pmeta">${esc(dateText(p.y, p.f, p.per, p.dt))}<span class="pill" style="border-color:${era[3]}">${esc(era[2])}</span></div>` : ''}
    ${st ? `<p>${esc(plain(st.text))}</p>` : ''}
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
  if (S.applyLayers) S.applyLayers(); else paintBuildings();
  S.map.getSource('places').setData({ type:'FeatureCollection', features: bs.map((b, i) =>
    ({ type:'Feature', properties:{ n: i + 1 }, geometry:{ type:'Point', coordinates: refCentre(b) } })) });
  $('pName').textContent = name;
  $('pCards').innerHTML = bs.map((b, i) => `<article class="pcard" data-i="${i}"${!isB(b) || S.features[b].full || !tiled() ? ' data-full="1"' : ''}>${cardHtml(b, i, name, hints?.[i])}</article>`).join('');
  $('pCards').querySelectorAll('[data-open]').forEach(btn => btn.onclick = () => openRef(parseRef(btn.dataset.open)));
  $('placesbar').hidden = false; $('timebar').hidden = true;
  $('pCards').scrollLeft = 0;
  setPlace(0, false);
  // all the places in view first; a card tapped (or swiped to) then goes to its place. Measured once the strip
  // has its cards: its height is the bottom of the view
  requestAnimationFrame(() => {
    if (S.places?.bs !== bs) return;
    const pts = bs.map(refCentre), lons = pts.map(p => p[0]), lats = pts.map(p => p[1]);
    const cam = S.map.cameraForBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
      { padding: { top: 70, left: 16, right: 60, bottom: $('placesbar').offsetHeight + 24 }, maxZoom: 16 });
    if (cam) glide({ ...cam, bearing: S.map.getBearing(), pitch: S.map.getPitch() });
  });
}
// a layer's groups (or a whole story layer or topic, by its id) as one set of numbered cards, in the build's date
// order, item by item: each story at a place once (a building with two stories of the set has a card for each).
// Returns false when there is nothing to show
export function showGroups(keys, title){
  const seen = new Set(), refs = [], hints = [];
  for (const k of keys) {
    const g = S.groups.get(k); if (!g) continue;
    for (const it of g.items || []) {
      const rs = typeof it[0] === 'number' ? [it[0]] : it[1], name = typeof it[0] === 'number' ? it[1] : it[0];
      const h = it[2] || {}, layer = h.layer || (g.layer.kind === 'stories' ? g.layer.id : h.person || h.plaque ? 'people' : null);
      for (const r of rs.map(x => typeof x === 'number' ? x : parseRef(String(x))))
        if (!seen.has(r + '|' + name)) { seen.add(r + '|' + name); refs.push(r); hints.push({ name, layer, when: h.when, person: h.person }); }
    }
  }
  if (!refs.length) return false;
  showPlaces(title, refs, hints);
  return true;
}
// From place to place as Google Earth flew: up and out (curve: higher is further out), across, and down again,
// slower the further it goes (speed: lower is slower), easing
// in and out (MapLibre's flyTo follows van Wijk and Nuij's "smooth and efficient zooming and panning", the same
// kind of flight). With reduced motion asked for, a short ease instead.
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
// easing in and out: the higher EASE, the slower the takeoff and landing (3 is the classic cubic; 2.7, a tenth quicker)
const EASE = 2.7;
const smooth = t => t < 0.5 ? Math.pow(2, EASE - 1) * Math.pow(t, EASE) : 1 - Math.pow(-2 * t + 2, EASE) / 2;
export function glide(camera){
  if (reduced()) return S.map.easeTo({ ...camera, duration: 300 });
  S.map.flyTo({ ...camera, speed: 0.44, curve: 1.9, easing: smooth, maxDuration: 6800, essential: true });
}
// how close a card takes the map to its place: near enough to pick out the building, with its street round it
const PLACE_ZOOM = 16;
const FLY_AFTER = 350;       // ms of the cards left still before the map flies
let flyWait;
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
  // the flight starts once the cards are left still: swiping back and forth would otherwise start a new flight
  // from wherever the last one had got to, low and short, never rising
  clearTimeout(flyWait);
  if (fly) flyWait = setTimeout(() => S.places && S.places.i === i && glide({ center: refCentre(S.places.bs[i]),
    zoom: Math.max(S.map.getZoom(), PLACE_ZOOM), padding: { bottom: $('placesbar').offsetHeight + 20 } }), FLY_AFTER);
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
// a tap on a card (not on its Details button): the map goes to its place, the first card's too
$('pCards').addEventListener('click', e => {
  const card = e.target.closest('.pcard');
  if (!card || e.target.closest('button, a') || !S.places) return;
  if (+card.dataset.i !== S.places.i) goToCard(+card.dataset.i);     // the swipe's end moves the map
  else setPlace(+card.dataset.i);
});
$('pPrev').onclick = () => S.places && goToCard(Math.max(0, S.places.i - 1));
$('pNext').onclick = () => S.places && goToCard(Math.min(S.places.bs.length - 1, S.places.i + 1));
$('pClose').onclick = () => clearPlaces(true);
export function clearPlaces(showTime){
  if (S.places) S.places.bs.filter(isB).forEach(b => fstate(b, { hl:false }));
  if (S.selectedId != null) { fstate(S.selectedId, { sel:false }); S.selectedId = null; }
  S.places = null;
  if (S.applyLayers) S.applyLayers(); else if (S.map) paintBuildings();
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
