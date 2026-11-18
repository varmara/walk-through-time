// Walk Through Time, city page: Places: a thread, a place or a person with several buildings, as numbered pins and
// cards that swipe sideways one at a time, or the same cards one under another as a page.
import { $, dateText, esc, flightPace, whenText } from './util.js';
import { S } from './state.js';
import { fstate, isB, loadCard, loadSet, parseRef, refCentre, refOf, storyFor, tiled } from './data.js';
import { paintBuildings } from './map.js';
import { closeSheet } from './sheet.js';
import { openRef, refName } from './cards.js';

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
// what a ref tells on its card: a building's story for the set, or a pin's own words (a plaque's, with its context)
function told(b, name, hint){
  if (!isB(b)) {
    const pp = refOf(b).properties;
    return { nm: pp.nm, when: pp.when, made: pp.made, text: pp.text, here: pp.here, source: parseJ(pp.source), layer: pp.layer,
      who: pp.who && !pp.own ? pp.who : null, at: refName(b) };
  }
  const f = S.features[b], p = f.properties, st = storyFor(b, hint?.name || name, hint?.layer);
  return { ...(st || {}), at: refName(b), y: p.y, f: p.f, per: p.per, dt: p.dt, own: st?.nm && st.nm === refName(b) && !hint?.person };
}
const parseJ = v => { try { return typeof v === 'string' ? JSON.parse(v) : v; } catch { return null; } };
const ready = refs => refs.every(b => !isB(b) || S.features[b].full || !tiled());
const src = s => s && s.url ? `<p class="psrc">${esc(s.kind || 'Source')}: <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title || s.url)}</a></p>` : '';
// the first card of a thread or a place: its title and introduction, and how many stories follow
// (a chapter of a thread with several has its own: its number, title and introduction, and how many stories
// follow before the next chapter)
function introHtml(P, card){
  const ch = card?.chapter;
  if (ch) return `<p class="pmeta pchap">Chapter ${ch.j} of ${ch.m}</p><h3 class="ptitle">${esc(ch.title)}</h3>${ch.text ? `<p>${esc(ch.text)}</p>` : ''}
    <p class="pmeta">${ch.n} ${ch.n === 1 ? 'story' : 'stories'}</p>
    <button class="textbtn pnext" data-first>${P.page ? 'Show them on the map' : 'Start'}</button>`;
  const n = P.cards.filter(c => !c.intro).length;
  return `<h3 class="ptitle">${esc(P.name)}</h3>${P.intro ? `<p>${esc(P.intro)}</p>` : ''}
    <p class="pmeta">${n} ${n === 1 ? 'story' : 'stories'}${P.chapters ? ` in ${P.chapters} chapters` : ''}</p>
    <button class="textbtn pnext" data-first>${P.page ? 'Show them on the map' : 'Start'}</button>`;
}
// one story's card, laid out as the thread's page tells it: its name; its date and where it is; who the person was;
// what it tells, each with its source; the full card (Details), or, in the page view, the way to the map
function cardHtml(card, n, P){
  if (card.intro) return introHtml(P, card);
  const { refs, hint } = card, name = hint?.name || P.name;
  if (!ready(refs)) return `<div class="pnum">${n}</div><h3>${esc(hint?.name || refName(refs[0]))}</h3><p class="pwait">Loading…</p>`;
  const ts = refs.map(b => told(b, P.name, hint)), first = ts[0];
  const title = hint?.name || first.nm || first.at;
  // the thread's date for it, then the story's own when that differs, as the thread's page gives them
  // (St Nicholas': destroyed in 1643, the church standing built by 1678)
  let wt = whenText(first.when, first.made, hint?.when) || toldIn(first.text);
  if (hint?.when && first.when && ![first.when, first.made].includes(hint.when)) wt = hint.when + ' · ' + whenText(first.when, first.made);
  // a building's own story dated otherwise than the building: both dates (Severn's Building: the article's c. 1450,
  // the map's 1335)
  const yr = w => +(/(\d{1,2})(?:st|nd|rd|th) century/.exec(w || '')?.[1] - 1) * 100 || +(/\d{3,4}/.exec(w || '') || [NaN])[0];
  if (first.own && wt && first.y != null && !hint?.when && Math.abs(yr(first.when) - first.y) >= 10)
    wt += ' · building ' + dateText(first.y, first.f, first.per, first.dt).replace(/^built (in |about )?/, '').replace(/^[A-Z](?=[a-z])/, c => c.toLowerCase());
  if (!wt && first.y != null) wt = dateText(first.y, first.f, first.per, first.dt);
  // a person's card is dated by the thread, or by their own story; another story of their place is not theirs (Albert
  // Iremonger at the Ferry Inn, whose story begins in the 17th century)
  if (hint?.person && !hint.when && first.layer !== 'people' && !first.who) wt = '';
  const at = [...new Set(ts.map(x => x.at).filter(a => a && a !== title))];
  const meta = [wt, at.length ? (/^(Plaque|Statue|Memorial)\b/.test(at[0]) ? '' : 'At ') + at.join(', ') : ''].filter(Boolean);
  const who = S.data.people?.[hint?.person ? name : ts.find(x => x.who)?.who];
  const seen = new Set(), parts = [];
  ts.forEach((x, j) => {
    if (!x.text || seen.has(x.text)) return; seen.add(x.text);
    parts.push(`<p>${esc(plain(x.text))}</p>${x.here ? `<p class="phere">${esc(x.here)}</p>` : ''}${src(x.source)}`
      + (refs.length > 1 ? `<button class="textbtn" data-open="${refs[j]}">Details</button>` : ''));
  });
  return `<div class="pnum">${n}</div><h3>${esc(title)}</h3>
    ${meta.length ? `<div class="pmeta pwhen">${esc(meta.join(' · '))}</div>` : ''}
    ${who?.text ? `<p class="pabout"><i>${esc(who.text)}</i>${who.life ? ` (${esc(who.life)})` : ''}</p>${src({ kind: 'Wikipedia', url: who.url, title: who.title })}` : ''}
    ${parts.join('')}
    <div class="pbtns">${refs.length === 1 ? `<button class="textbtn" data-open="${refs[0]}">Details</button>` : ''}<button class="textbtn pmap" data-map>Show on the map</button></div>`;
}
const numOf = (P, k) => P.cards[k].n;       // a story's number: the opening cards (the set's, each chapter's) have none
function wire(el){
  el.querySelectorAll('[data-open]').forEach(btn => btn.onclick = () => openRef(parseRef(btn.dataset.open)));
  el.querySelectorAll('[data-map]').forEach(btn => btn.onclick = () => { pageView(false); goToCard(+el.dataset.i); });
  el.querySelectorAll('[data-first]').forEach(btn => btn.onclick = () => { pageView(false); goToCard(+el.dataset.i + 1); });
}
function fillCard(k){
  const P = S.places, el = P && $('pCards').querySelector(`[data-i="${k}"]`);
  if (!el || el.dataset.full) return;
  const c = P.cards[k]; if (!c.intro && !ready(c.refs)) return;
  el.innerHTML = cardHtml(c, numOf(P, k), P); el.dataset.full = '1'; wire(el);
}
// the cards round the one in view, loaded first (a big set, as a group from the graph, has places in dozens of
// card files: they come as you swipe, not all before the strip shows); in the page view, all of them
function loadAround(k){
  const P = S.places; if (!P || P.set) return;      // a thread's own file on its way: its cards come with it
  const lo = P.page ? 0 : Math.max(0, k - 3), hi = P.page ? P.cards.length : Math.min(P.cards.length, k + 9);
  for (let j = lo; j < hi; j++) {
    const c = P.cards[j]; if (c.intro) { fillCard(j); continue; }
    const need = c.refs.filter(b => isB(b) && !S.features[b].full && tiled());
    if (!need.length) { fillCard(j); continue; }
    Promise.all(need.map(b => loadCard(b).catch(() => {}))).then(() => { if (S.places === P) fillCard(j); });
  }
}

// a set of places as cards: one card for each story (hints: for each place, the name and story layer of what put it
// in the set; places of the same story, as a person's two plaques, share its card), after an opening card with the
// set's title and introduction when it has one (a thread, a place)
export function showPlaces(name, bs, hints, intro, set, chapters){
  // the stories' words are in the card files. A small set (a person, a story: one or two files) waits for them,
  // showing the bar meanwhile; a big set, or one whose places' whereabouts need the files, shows at once
  // (the single data file, with no card files: every building is complete already)
  const need = tiled() ? bs.filter(isB).filter(b => !S.features[b].full) : [];
  const placed = bs.every(b => refCentre(b));
  // a thread or place with its own file (set) opens at once, its cards filled when the file comes; it waits only
  // if its places' whereabouts are in that file
  if (need.length && (set ? !placed : need.length <= 12 || !placed)) {
    $('pName').textContent = name; $('pCount').textContent = '';
    $('pCards').innerHTML = `<p class="pwait">Finding ${bs.length} ${bs.length === 1 ? 'place' : 'places'}…</p>`;
    $('placesbar').hidden = false; $('timebar').hidden = true;
    return (set ? set.catch(() => {}) : Promise.all(need.map(b => loadCard(b).catch(() => {}))))
      .then(() => showPlaces(name, bs, hints, intro, set && need.some(b => !S.features[b].full) ? null : set, chapters));
  }
  closeSheet();
  clearPlaces(false);
  const cards = intro !== undefined ? [{ intro: true }] : [];
  let ch = null;
  bs.forEach((b, i) => {
    const h = hints?.[i], last = cards[cards.length - 1];
    // a thread of several chapters: each opens with its own card, and its stories do not mix with the next's
    if (chapters && h?.ch != null && h.ch !== ch) {
      ch = h.ch;
      const c = chapters[ch]; if (c) cards.push({ intro: true, chapter: { ...c, j: ch + 1, m: chapters.length, n: 0 } });
    }
    if (h && last && !last.intro && last.hint?.name === h.name && h.ch === last.hint.ch) last.refs.push(b);
    else cards.push({ refs: [b], hint: h });
  });
  let num = 0, open = null;
  cards.forEach(c => { if (!c.intro) { c.n = ++num; if (open) open.n++; } else { c.n = 0; open = c.chapter || null; } });
  const P = S.places = { name, intro, bs, cards, chapters: chapters ? chapters.length : 0, i: 0, page: false, set: need.length && set ? set : null };
  if (P.set) P.set.catch(() => {}).then(() => { if (S.places !== P) return; P.set = null;
    P.cards.forEach((c, k) => fillCard(k)); loadAround(P.i); });
  bs.filter(isB).forEach(b => fstate(b, { hl:true }));
  if (S.applyLayers) S.applyLayers(); else paintBuildings();
  // every place of a story carries the story's number
  S.map.getSource('places').setData({ type:'FeatureCollection', features: cards.flatMap((c, k) => c.intro ? [] :
    c.refs.map((b, j) => ({ type:'Feature', properties:{ n: numOf(P, k), k, j }, geometry:{ type:'Point', coordinates: refCentre(b) } }))) });
  $('pName').textContent = name;
  $('pCards').innerHTML = cards.map((c, k) => `<article class="pcard${c.intro ? ' pintro' : ''}" data-i="${k}">${cardHtml(c, numOf(P, k), P)}</article>`).join('');
  $('pCards').querySelectorAll('.pcard').forEach(el => { if (el.querySelector('.pwait') == null) el.dataset.full = '1'; wire(el); });
  $('placesbar').hidden = false; $('timebar').hidden = true;
  $('placesbar').classList.remove('page'); $('pPage').setAttribute('aria-pressed', 'false');
  $('pCards').scrollLeft = 0;
  setPlace(0, false);
  // all the places in view first; a card tapped (or swiped to) then goes to its place. Measured once the strip
  // has its cards: its height is the bottom of the view
  requestAnimationFrame(() => { if (S.places === P) fitAll(); });
}
function fitAll(card){
  const P = S.places; if (!P) return;
  // (a chapter's card takes the map to that chapter's places)
  const rs = card?.chapter ? P.cards.slice(P.cards.indexOf(card) + 1).filter((c, k, a) => !a.slice(0, k).some(x => x.intro)).flatMap(c => c.intro ? [] : c.refs) : P.bs;
  const pts = (rs.length ? rs : P.bs).map(refCentre), lons = pts.map(p => p[0]), lats = pts.map(p => p[1]);
  const cam = S.map.cameraForBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
    { padding: { top: 70, left: 16, right: 60, bottom: $('placesbar').offsetHeight + 24 }, maxZoom: 16 });
  if (cam) glide({ ...cam, bearing: S.map.getBearing(), pitch: S.map.getPitch() });
}
// a layer's groups (or a whole story layer or topic, by its id) as one set of cards, in the build's date order,
// item by item: each story at a place once (a building with two stories of the set has a card for each). A whole
// layer opens with its introduction. Returns false when there is nothing to show
export function showGroups(keys, title){
  const seen = new Set(), refs = [], hints = [], chaps = [];
  for (const k of keys) {
    const g = S.groups.get(k); if (!g) continue;
    const ch = chaps.length; if ((g.items || []).length) chaps.push({ title: g.title, text: g.intro || '' });
    for (const it of g.items || []) {
      const rs = typeof it[0] === 'number' ? [it[0]] : it[1], name = typeof it[0] === 'number' ? it[1] : it[0];
      const h = it[2] || {}, layer = h.layer || (g.layer.kind === 'stories' ? g.layer.id : h.person || h.plaque ? 'people' : null);
      for (const r of rs.map(x => typeof x === 'number' ? x : parseRef(String(x))))
        if (!seen.has(r + '|' + name)) { seen.add(r + '|' + name); refs.push(r); hints.push({ name, layer, when: h.when, person: h.person, ch }); }
    }
  }
  if (!refs.length) return false;
  const Ls = [...new Set(keys.map(k => S.groups.get(k)?.layer).filter(Boolean))];
  const whole = Ls.length === 1 && Ls[0].groups.filter(g => g.count > 0).every(g => keys.includes(g.key));
  // a thread or place (one layer) has its own small file with its cards
  const set = Ls.length === 1 ? loadSet(Ls[0].id) : null;
  // a thread of several chapters, shown whole: a card for each chapter, whose stories keep to it. One chapter alone
  // opens with its own introduction
  const several = whole && (Ls[0].kind === 'topics' || Ls[0].section === 'Places') && chaps.length > 1 && chaps.every(c => c.text);
  const alone = keys.length === 1 && chaps.length === 1 && chaps[0].text ? chaps[0].text : undefined;
  showPlaces(title, refs, hints, whole ? (Ls[0].intro || '') : alone, set, several ? chaps : undefined);
  return true;
}
// the set as a page, as the thread's share page tells it, scrolled through on the map's screen; each story's
// "Show on the map" goes back to the cards at its card
export function pageView(on){
  const P = S.places; if (!P) return;
  P.page = on;
  $('placesbar').classList.toggle('page', on);
  $('pPage').setAttribute('aria-pressed', String(on));
  $('pPage').setAttribute('aria-label', on ? 'Show as cards' : 'Show as a page');
  $('pCards').querySelectorAll('.pintro').forEach(el => { el.innerHTML = introHtml(P, P.cards[+el.dataset.i]); wire(el); });
  if (on) { loadAround(0); $('pCards').scrollTop = 0; }
  else goToCard(P.i, false);
}
$('pPage').onclick = () => pageView(!(S.places && S.places.page));
// From place to place as Google Earth flew: up and out (curve: higher is further out), across, and down again,
// slower the further it goes (speed: lower is slower), easing
// in and out (MapLibre's flyTo follows van Wijk and Nuij's "smooth and efficient zooming and panning", the same
// kind of flight). With reduced motion asked for, a short ease instead.
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
// easing in and out: the higher EASE, the slower the takeoff and landing (3 is the classic cubic; 2.7, a tenth quicker)
const EASE = 2.7;
const smooth = t => t < 0.5 ? Math.pow(2, EASE - 1) * Math.pow(t, EASE) : 1 - Math.pow(-2 * t + 2, EASE) / 2;
// Its length is set by how far it goes, and its speed grows with the distance: a hop along the street takes about
// a second and a half, across town about two and a half, and a flight to the edge of the map no more than about
// three and a half (a flight left to MapLibre's own pace that would take longer than its limit is not flown but
// jumped: Women's lives, from Mary Howitt's house in the town to Frances Bush's plaque 8 km away)
export const flightMs = (km, dz = 0) => Math.round(Math.min(3600, 1200 + 650 * Math.log2(1 + km) + 120 * Math.abs(dz)));
export function glide(camera){
  const pace = flightPace();
  if (!pace) return S.map.jumpTo(camera);
  if (reduced()) return S.map.easeTo({ ...camera, duration: 300 });
  const to = camera.center && maplibregl.LngLat.convert(camera.center);
  const km = to ? S.map.getCenter().distanceTo(to) / 1000 : 0;
  const dz = camera.zoom != null ? camera.zoom - S.map.getZoom() : 0;
  S.map.flyTo({ ...camera, curve: 1.9, easing: smooth, duration: Math.round(flightMs(km, dz) * pace), essential: true });
}
// how close a card takes the map to its place: near enough to pick out the building, with its street round it
const PLACE_ZOOM = 16;
const FLY_AFTER = 350;       // ms of the cards left still before the map flies
let flyWait;
export function setPlace(k, fly = true){
  const P = S.places; if (!P) return;
  P.i = k;
  const c = P.cards[k], n = P.cards.filter(x => !x.intro).length;
  $('pCount').textContent = c.intro ? (c.chapter ? `Chapter ${c.chapter.j} of ${c.chapter.m}` : `${n} ${n === 1 ? 'story' : 'stories'}`) : `${numOf(P, k)} of ${n}`;
  if (S.selectedId != null) fstate(S.selectedId, { sel:false });
  S.selectedId = !c.intro && isB(c.refs[0]) ? c.refs[0] : null;
  if (S.selectedId != null) fstate(S.selectedId, { sel:true });
  drawPins();
  $('pCards').querySelectorAll('.pcard').forEach(el => el.classList.toggle('on', +el.dataset.i === k));
  loadAround(k);
  // the flight starts once the cards are left still: swiping back and forth would otherwise start a new flight
  // from wherever the last one had got to, low and short, never rising
  clearTimeout(flyWait);
  if (fly) flyWait = setTimeout(() => {
    if (!S.places || S.places.i !== k) return;
    if (c.intro) return fitAll(c);
    const pts = c.refs.map(refCentre), pad = { top: 70, left: 30, right: 70, bottom: $('placesbar').offsetHeight + 20 };
    if (pts.length > 1) {
      const lons = pts.map(p => p[0]), lats = pts.map(p => p[1]);
      const cam = S.map.cameraForBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: pad, maxZoom: PLACE_ZOOM });
      if (cam) return glide({ ...cam, bearing: S.map.getBearing(), pitch: S.map.getPitch() });
    }
    glide({ center: pts[0], zoom: Math.max(S.map.getZoom(), PLACE_ZOOM), padding: { bottom: pad.bottom } });
  }, FLY_AFTER);
}
const still = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
export function goToCard(k, smooth = true){
  const card = $('pCards').querySelector(`[data-i="${k}"]`);
  if (!card) return;
  const first = $('pCards').querySelector('.pcard');
  $('pCards').scrollTo({ left: card.offsetLeft - first.offsetLeft, behavior: smooth && !still() ? 'smooth' : 'auto' });
  if (!smooth) setPlace(k);
}
export let scrollTimer;
$('pCards').addEventListener('scroll', () => {
  if (S.places?.page) return;
  clearTimeout(scrollTimer);
  scrollTimer = setTimeout(() => {
    const cs = $('pCards').querySelectorAll('.pcard'); if (cs.length < 2) return;
    const k = Math.round($('pCards').scrollLeft / Math.max(1, cs[1].offsetLeft - cs[0].offsetLeft));
    if (S.places && k !== S.places.i && k < S.places.cards.length) setPlace(k);
  }, 120);
});
// a tap on a card (not on its buttons or links): the map goes to its place
$('pCards').addEventListener('click', e => {
  const card = e.target.closest('.pcard');
  if (!card || e.target.closest('button, a') || !S.places || S.places.page) return;
  setPlace(+card.dataset.i);
});
$('pPrev').onclick = () => S.places && goToCard(Math.max(0, S.places.i - 1));
$('pNext').onclick = () => S.places && goToCard(Math.min(S.places.cards.length - 1, S.places.i + 1));
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
// numbers as a list, a run of consecutive ones as a range: [1, 2, 3, 7, 9, 10] -> "1–3, 7, 9–10"
export const runs = ns => ns.reduce((o, n) => { const l = o[o.length - 1]; if (l && n === l[1] + 1) l[1] = n; else o.push([n, n]); return o; }, [])
  .map(([a, b]) => a === b ? String(a) : `${a}–${b}`).join(', ');
// the pins carry their stories' numbers; pins too close to tell apart join as one, showing the numbers in it
// ("4–5, 9"), which opens out when tapped; it is lit only when one of its own stories is the open card
export function drawPins(){
  if (!S.map || !S.map.getSource('places')) return;
  const seen = new Set(), drawn = [], P = S.places, cur = P && !P.cards[P.i]?.intro ? numOf(P, P.i) : null;
  for (const f of S.map.querySourceFeatures('places')) {
    const pr = f.properties, cl = pr.cluster;
    // (a joined pin can come once from each map tile it lies across, under another id and a little apart: the
    // first is drawn)
    let key = cl ? 'c' + pr.cluster_id : `p${pr.k}-${pr.j}`;
    if (cl) {
      const at = S.map.project(f.geometry.coordinates);
      const twin = drawn.find(d => d.lo === pr.lo && d.hi === pr.hi && Math.hypot(d.x - at.x, d.y - at.y) < 80);
      if (twin) continue;
      drawn.push({ lo: pr.lo, hi: pr.hi, x: at.x, y: at.y });
    }
    if (seen.has(key)) continue;
    seen.add(key);
    const nums = cl ? [...new Set(String(pr.ns || '').split(',').filter(Boolean).map(Number))].sort((a, b) => a - b) : [pr.n];
    const label = cl ? (nums.length ? runs(nums) : pr.lo === pr.hi ? String(pr.lo) : `${pr.lo}, ${pr.hi}`) : String(pr.n);
    if (!S.pins[key]) {
      const el = document.createElement('button');
      el.className = cl ? 'pin cluster' : 'pin';
      el.textContent = label;
      el.setAttribute('aria-label', cl ? `Stories ${label} here: zoom in` : `Story ${pr.n}`);
      el.onclick = e => {
        e.stopPropagation();
        if (cl) S.map.getSource('places').getClusterExpansionZoom(pr.cluster_id)
          .then(z => S.map.easeTo({ center: f.geometry.coordinates, zoom: z + 0.3 }));
        else goToCard(pr.k);
      };
      S.pins[key] = new maplibregl.Marker({ element: el }).setLngLat(f.geometry.coordinates).addTo(S.map);
    }
    const el = S.pins[key].getElement();
    el.classList.toggle('on', cur != null && (cl ? (nums.length ? nums.includes(cur) : pr.lo <= cur && cur <= pr.hi) : pr.n === cur));
    if (cl) el.classList.toggle('wide', label.length > 2);
  }
  Object.keys(S.pins).forEach(k => { if (!seen.has(k)) { S.pins[k].remove(); delete S.pins[k]; } });
}
