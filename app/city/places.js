// Walk Through Time, city page: Places: a thread, a place or a person with several buildings, as numbered pins and
// cards that swipe sideways one at a time, or the same cards one under another as a page.
import { $, citedText, dateText, esc, flightPace, whenText } from './util.js';
import { S } from './state.js';
import { fstate, isB, isThread, loadCard, loadSet, parseRef, refCentre, refOf, storyFor, tiled } from './data.js';
import { groundAt, paintBuildings } from './map.js';
import { closeSheet } from './sheet.js';
import { openRef, openWho, refName } from './cards.js';
import { chapterColour, footnotes, relatedOf, shareStory, storyCard, storyLink, yearOf } from './story.js';

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
      who: pp.who && !pp.own ? pp.who : null, at: refName(b), approx: pp.approx };
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
  if (ch) {
    const k = P.cards.indexOf(card), yrs = chapterYears(ch.title, chapterCards(P, k));
    return `<p class="pmeta pchap" style="color:${ch.colour}">Chapter ${ch.j} of ${ch.m}${yrs ? ' · ' + yrs : ''}</p><h3 class="ptitle">${esc(ch.title)}</h3>${ch.text ? citedText(ch.text, P.cites) : ''}
      <div class="plist">${chapterCards(P, k).map(c => `<button data-go="${P.cards.indexOf(c)}"><span class="snum" style="background:${c.colour}">${c.n}</span><span class="pdate">${esc(dateOf(c))}</span><span class="pname">${esc(c.hint?.name || refName(c.refs[0]))}</span></button>`).join('')}</div>`;
  }
  const n = P.cards.filter(c => !c.intro).length;
  // a thread of chapters: its chapters to choose from, each with its years; else how many stories, and Start
  const chaps = P.cards.map((c, k) => [c, k]).filter(([c]) => c.chapter);
  return `<h3 class="ptitle">${esc(P.name)}</h3>${P.intro ? citedText(P.intro, P.cites) : ''}
    ${chaps.length ? `<div class="plist chaps">${chaps.map(([c, k]) => `<button data-go="${k}"><i style="background:${c.chapter.colour}"></i><span class="pdate">${esc(chapterYears(c.chapter.title, chapterCards(P, k)).split('–')[0])}</span><span class="pname">${esc(c.chapter.title)}</span></button>`).join('')}</div>`
      : `<p class="pmeta">${n} ${n === 1 ? 'story' : 'stories'}</p><button class="textbtn pnext" data-first>Start</button>`}`;
}
// a story's date in a list: the thread's, else its own (not a year the build took from its words: Addensburgh's
// 1774 is its ferry, not its name)
function dateOf(c){
  const t = ready(c.refs) ? told(c.refs[0], S.places.name, c.hint) : {};
  return c.hint?.when || t.when || '';
}
// a chapter's years: those its title ends with ("The Reform riots, 1831"), else its stories'
function chapterYears(title, cs){
  const m = /\b(\d{3,4}(?:[–-]\d{2,4})?)$/.exec(title || '');
  return m ? m[1] : span(cs);
}
// the years of a run of cards: "1831", "1842–1847"
function span(cs){
  const ys = cs.map(c => Number.isFinite(c.hint?.y) ? c.hint.y : yearOf(c.hint?.when)).filter(Number.isFinite);
  if (!ys.length) return '';
  const a = Math.min(...ys), b = Math.max(...ys);
  return a === b ? String(a) : `${a}–${b}`;
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
  // A person's card, unless the thread dates it, is dated by their life (1785–1806), as the thread orders them by
  // their birth: not by a year borrowed from their place's story, its building or their text
  const who = S.data.people?.[hint?.person ? name : ts.find(x => x.who)?.who];
  const life = hint?.person && !hint.when && who?.life;
  if (life) wt = who.life;
  else if (hint?.person && !hint.when && first.layer !== 'people' && !first.who) wt = '';
  const at = [...new Set(ts.map(x => x.at).filter(a => a && a !== title))];
  const meta = [wt, at.length ? (/^(Plaque|Statue|Memorial)\b/.test(at[0]) ? '' : 'At ') + at.join(', ') : ''].filter(Boolean);
  // a pin not placed exactly (its halo on the map)
  const ap = ts.find(x => x.approx)?.approx;
  if (ap) meta.push(`place approximate, within about ${ap} m`);
  // its words (several places of one story, as a person's two plaques: each one's words once), and their sources
  const seen = new Set(), texts = ts.filter(x => x.text && !seen.has(x.text) && seen.add(x.text));
  const st = { ...first, text: texts.map(x => x.text).join('\n\n'),
    sources: [...(Array.isArray(first.sources) ? first.sources : []), ...texts.slice(1).map(x => x.source).filter(Boolean)],
    here: texts.map(x => x.here).filter(Boolean).join(' ') };
  const ch = card.chapter || (P.chapterList && hint?.ch != null ? P.chapterList[hint.ch] : null);
  const about = refs.map(r => `<button class="textbtn" data-open="${r}">About ${esc(refName(r))} ›</button>`).join('');
  return storyCard({ n, colour: card.colour, title,
    chapter: ch ? `Chapter ${hint.ch + 1} of ${P.chapterList.length} · ${ch.title}` : '',
    meta: meta.join(' · '), s: st, who: who?.text ? { text: who.text, url: who.url, title: who.title } : null,
    rel: relatedOf(st, refs, { title, thread: P.thread, self: hint?.person ? name : null }),
    share: P.thread ? storyLink(P.thread, title) : '',
    extra: `<div class="pbtns">${about}<button class="textbtn pmap" data-map>Show on the map</button></div>` });
}
const numOf = (P, k) => P.cards[k].n;       // a story's number: the opening cards (the set's, each chapter's) have none
function wire(el){
  el.querySelectorAll('[data-open]').forEach(btn => btn.onclick = () => openRef(parseRef(btn.dataset.open)));
  el.querySelectorAll('[data-ref]').forEach(x => x.onclick = e => { e.preventDefault(); openRef(parseRef(x.dataset.ref)); });
  el.querySelectorAll('[data-who]').forEach(x => x.onclick = e => { e.preventDefault(); openWho(x.dataset.who); });
  el.querySelectorAll('[data-thread]').forEach(x => x.onclick = e => { e.preventDefault(); showThread(x.dataset.thread); });
  el.querySelectorAll('[data-share]').forEach(x => x.onclick = e => { e.stopPropagation(); shareStory(x.dataset.share, x.dataset.title); });
  el.querySelectorAll('[data-go]').forEach(x => x.onclick = e => { e.stopPropagation(); pageView(false); goToCard(+x.dataset.go); });
  el.querySelectorAll('[data-chap]').forEach(x => x.onclick = () => openChapter(+x.dataset.chap));
  el.querySelectorAll('[data-fn]').forEach(x => x.onclick = e => {        // to the source in the card's own list
    e.preventDefault(); e.stopPropagation();
    const li = document.getElementById('fn' + x.dataset.fn); if (!li) return;
    li.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    li.classList.remove('hit'); void li.offsetWidth; li.classList.add('hit');
  });
  el.querySelectorAll('[data-map]').forEach(btn => btn.onclick = () => { pageView(false); goToCard(+el.dataset.i); });
  el.querySelectorAll('[data-first]').forEach(btn => btn.onclick = () => { pageView(false); goToCard(+el.dataset.i + 1); });
}
function fillCard(k){
  const P = S.places; if (!P) return;
  const c = P.cards[k]; if (!c.intro && !ready(c.refs)) return;
  if (P.page) { const x = $('pCards').querySelector(`.cstory[data-i="${k}"]`); if (x && x.querySelector('.pwait')) { x.innerHTML = cardHtml(c, c.n, P); wire(x); } return; }
  const el = $('pCards').querySelector(`.pcard[data-i="${k}"]`);
  if (!el || el.dataset.full) return;
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
export function showPlaces(name, bs, hints, intro, set, chapters, cites, thread){
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
      .then(() => showPlaces(name, bs, hints, intro, set && need.some(b => !S.features[b].full) ? null : set, chapters, cites, thread));
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
      const c = chapters[ch]; if (c) cards.push({ intro: true, chapter: { ...c, j: ch + 1, m: chapters.length, n: 0, colour: chapterColour(ch + 1, chapters.length) } });
    }
    if (h && last && !last.intro && last.hint?.name === h.name && h.ch === last.hint.ch) last.refs.push(b);
    else cards.push({ refs: [b], hint: h });
  });
  let num = 0, open = null;
  cards.forEach(c => { if (!c.intro) { c.n = ++num; if (open) open.n++; } else { c.n = 0; open = c.chapter || null; } });
  // each story in its chapter's colour (pin, number, label); a set without chapters in one
  cards.forEach(c => { if (!c.intro) c.colour = chapters && c.hint?.ch != null ? chapterColour(c.hint.ch + 1, chapters.length) : 'var(--hl)'; });
  // a story at the place the card before it showed, and only there: the map, there already, stays
  let before = null;
  cards.forEach(c => {
    if (c.intro) { before = null; return; }
    // (a place by where it is: the same pin comes once for each layer that tells of it)
    const at = x => isB(x) ? 'b' + x : refCentre(x).map(v => v.toFixed(5)).join();
    const r = c.refs.length === 1 ? at(c.refs[0]) : null;
    c.same = !!r && before === r;
    before = r;
  });
  const P = S.places = { name, intro, cites, thread, chapterList: chapters || null, bs, cards, chapters: chapters ? chapters.length : 0, i: 0, page: false, set: need.length && set ? set : null };
  if (P.set) P.set.catch(() => {}).then(() => { if (S.places !== P) return; P.set = null;
    P.cards.forEach((c, k) => fillCard(k)); loadAround(P.i); });
  bs.filter(isB).forEach(b => fstate(b, { hl:true }));
  if (S.applyLayers) S.applyLayers(); else paintBuildings();
  // every place of a story carries the story's number
  S.map.getSource('places').setData({ type:'FeatureCollection', features: cards.flatMap((c, k) => c.intro ? [] :
    c.refs.map((b, j) => ({ type:'Feature', properties:{ n: numOf(P, k), k, j }, geometry:{ type:'Point', coordinates: refCentre(b) } }))) });
  // the approximate ones (", approximate" in their notes) with a halo of their radius
  S.map.getSource('approx')?.setData({ type:'FeatureCollection', features: cards.flatMap(c => c.intro ? [] :
    c.refs.filter(b => !isB(b) && refOf(b).properties?.approx).map(b => ({ type:'Feature',
      properties:{ approx: refOf(b).properties.approx }, geometry:{ type:'Point', coordinates: refCentre(b) } }))) });
  $('pName').textContent = name;
  strip(P);
  $('placesbar').hidden = false; $('timebar').hidden = true;
  $('placesbar').classList.remove('page'); $('pPage').setAttribute('aria-pressed', 'false');
  $('pCards').scrollLeft = 0;
  setPlace(0, false);
  // all the places in view first; a card tapped (or swiped to) then goes to its place. Measured once the strip
  // has its cards: its height is the bottom of the view
  requestAnimationFrame(() => { if (S.places === P) fitAll(); });
}
// the strip of cards
function strip(P){
  $('pCards').innerHTML = P.cards.map((c, k) => `<article class="pcard${c.intro ? ' pintro' : ''}" data-i="${k}">${cardHtml(c, numOf(P, k), P)}</article>`).join('');
  $('pCards').querySelectorAll('.pcard').forEach(el => { if (el.querySelector('.pwait') == null) el.dataset.full = '1'; wire(el); });
}
// a whole thread, by its id
function showThread(id){
  const L = S.layers.find(x => x.id === id); if (!L) return;
  showGroups(L.groups.filter(g => g.count > 0).map(g => g.key), L.title);
}
// the story cards of the chapter whose opening card is card k (up to the next chapter's)
function chapterCards(P, k){
  const out = [];
  for (const c of P.cards.slice(k + 1)) { if (c.intro) break; out.push(c); }
  return out;
}
// the room the cards leave for the map: one padding for every card, so going from card to card never shifts it
const cardPad = () => ({ top: 70, left: 16, right: 60, bottom: $('placesbar').offsetHeight + 24 });
function fitAll(card){
  const P = S.places; if (!P) return;
  // (a chapter's card takes the map to that chapter's places)
  glide({ ...introCamera(P, card), bearing: S.map.getBearing(), pitch: S.map.getPitch() });
}
const introCamera = (P, card) => {
  const rs = card?.chapter ? chapterCards(P, P.cards.indexOf(card)).flatMap(c => c.refs) : P.bs;
  return fitCamera((rs.length ? rs : P.bs).map(refCentre), cardPad(), 16);
};
// where the cards either side of card k take the map: the ground's height there read now, so a flight to them
// need not wait for it (on a slow connection it came too late, and the place jumped at the end)
function warmNext(P, k){
  for (const j of [k + 1, k - 1]) {
    const c = P.cards[j]; if (!c) continue;
    const at = c.intro ? introCamera(P, c).center : c.refs.length === 1 ? refCentre(c.refs[0]) : fitCamera(c.refs.map(refCentre), cardPad(), PLACE_ZOOM).center;
    groundAt(at);
  }
}
// the camera that shows all of pts inside the padding, worked out here rather than by the map's cameraForBounds:
// that works from the camera as it is, and from close in at a tilt it gave a point miles off at a far lower zoom.
// The tilt squeezes the ground's depth, so the height allowed is stretched by it, and widens what is near, so the
// width allowed is narrowed (pitch: the camera's, kept)
function fitCamera(pts, pad, maxZoom){
  const merc = ([lon, lat]) => [(lon + 180) / 360, (1 - Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)) / Math.PI) / 2];
  const xs = pts.map(p => merc(p)[0]), ys = pts.map(p => merc(p)[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const c = S.map.getCanvas(), w = c.clientWidth - pad.left - pad.right, h = c.clientHeight - pad.top - pad.bottom;
  const tilt = Math.max(0.35, Math.cos(S.map.getPitch() * Math.PI / 180));
  const fit = Math.min(w * tilt ** 0.75 / Math.max(x1 - x0, 1e-9), h / tilt / Math.max(y1 - y0, 1e-9)) / 512;
  const zoom = Math.min(maxZoom, Math.max(S.map.getMinZoom(), Math.log2(fit)));
  const lon = (x0 + x1) / 2 * 360 - 180, lat = Math.atan(Math.sinh(Math.PI * (1 - (y0 + y1)))) * 180 / Math.PI;
  return { center: [lon, lat], zoom, padding: pad };
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
        if (!seen.has(r + '|' + name)) { seen.add(r + '|' + name); refs.push(r); hints.push({ name, layer, when: h.when, y: h.y, person: h.person, ch }); }
    }
  }
  if (!refs.length) return false;
  const Ls = [...new Set(keys.map(k => S.groups.get(k)?.layer).filter(Boolean))];
  const whole = Ls.length === 1 && Ls[0].groups.filter(g => g.count > 0).every(g => keys.includes(g.key));
  // a thread or place (one layer) has its own small file with its cards
  const set = Ls.length === 1 ? loadSet(Ls[0].id) : null;
  // a thread of several chapters, shown whole: a card for each chapter, whose stories keep to it. One chapter alone
  // opens with its own introduction
  const several = whole && isThread(Ls[0]) && chaps.length > 1 && chaps.every(c => c.text);
  const alone = keys.length === 1 && chaps.length === 1 && chaps[0].text ? chaps[0].text : undefined;
  showPlaces(title, refs, hints, whole ? (Ls[0].intro || '') : alone, set, several ? chaps : undefined, Ls.length === 1 ? Ls[0].cites : undefined,
    whole && isThread(Ls[0]) && Ls[0].section === 'Threads' ? Ls[0].id : undefined);
  return true;
}
// Contents: the set as a list down a line, a chapter's year by it, each story numbered under its chapter; a chapter's
// heading opens its full text in place (its introduction, then each story's card); Open all opens every chapter
export function pageView(on){
  const P = S.places; if (!P) return;
  P.page = on;
  $('placesbar').classList.toggle('page', on);
  $('pPage').setAttribute('aria-pressed', String(on));
  $('pPage').setAttribute('aria-label', on ? 'Back to the cards' : 'Contents');
  if (on) { P.open = P.open || new Set(); loadAround(0); contents(P); $('pCards').scrollTop = 0; }
  else { strip(P); goToCard(P.i, false); }
}
function contents(P){
  const groups = [];                       // [{ chapter card index or -1, its cards }]
  P.cards.forEach((c, k) => { if (c.intro) { if (c.chapter) groups.push({ k, c, cards: [] }); } else { if (!groups.length) groups.push({ k: -1, c: null, cards: [] }); groups[groups.length - 1].cards.push([c, k]); } });
  const row = ([c, k]) => `<button class="crow${k === P.i ? ' here' : ''}" data-go="${k}"><span class="snum" style="background:${c.colour}">${c.n}</span><span class="pname">${esc(c.hint?.name || refName(c.refs[0]))}</span>${k === P.i ? '<span class="muted">you are here</span>' : ''}</button>`;
  const full = g => (g.c?.chapter.text ? citedText(g.c.chapter.text, P.cites) : '') + g.cards.map(([c, k]) => `<article class="cstory" data-i="${k}">${ready(c.refs) ? cardHtml(c, c.n, P) : '<p class="pwait">Loading…</p>'}</article>`).join('');
  const html = groups.map((g, j) => {
    const open = P.open.has(j) || !g.c, yrs = g.c ? chapterYears(g.c.chapter.title, g.cards.map(([c]) => c)) : span(g.cards.map(([c]) => c));
    const colour = g.c ? g.c.chapter.colour : 'var(--hl)';
    return `<section class="cchap"><b class="cyr" style="color:${colour}">${esc(yrs.split('–')[0])}</b><i class="cdot" style="background:${colour}"></i>
      <div class="cbody">${g.c ? `<button class="chead" data-chap="${j}" aria-expanded="${open}"><span>${esc(g.c.chapter.title)}</span><span class="chev">${open ? '▾' : '▸'}</span></button>` : ''}
      ${open ? full(g) : g.cards.map(row).join('')}</div></section>`;
  }).join('');
  $('pCards').innerHTML = `<div class="contents"><div class="chd"><b>${esc(P.name)}</b>${groups.some(g => g.c) ? `<button class="textbtn" data-chap="-1">${P.open.size === groups.length ? 'Close all' : 'Open all'}</button>` : ''}</div>
    ${P.intro ? citedText(P.intro, P.cites) : ''}${html}</div>`;
  wire($('pCards'));
  $('pCards').querySelectorAll('.cstory').forEach(wire);
}
function openChapter(j){
  const P = S.places; if (!P) return;
  const n = P.cards.filter(c => c.chapter).length;
  if (j < 0) P.open = P.open.size === n ? new Set() : new Set([...Array(n).keys()]);
  else P.open.has(j) ? P.open.delete(j) : P.open.add(j);
  const y = $('pCards').scrollTop; contents(P); $('pCards').scrollTop = y;
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
  const run = ++glideRun;          // (a later glide wins)
  if (!camera.center || !S.map.getTerrain()) return glideNow(camera);
  // On the hills the camera works with one height for the ground and keeps it through a flight. A place higher than
  // that shows where flat ground further on would, so the camera is aimed there, and the place lands in the middle
  // of the view (MapLibre settles the camera's height onto the ground afterwards without the view moving). Without
  // this, flying from the whole city (ground taken as 0 m) onto a place on a hill (Broxtowe, 90 m) the place swung
  // down towards the middle and then rose well above it: the twitch
  const to = maplibregl.LngLat.convert(camera.center);
  Promise.race([groundAt([to.lng, to.lat]), new Promise(r => setTimeout(() => r(null), 1200))]).then(h => {
    if (run !== glideRun) return;
    if (h == null) return glideNow(camera);
    const pitch = (camera.pitch ?? S.map.getPitch()) * Math.PI / 180, bearing = (camera.bearing ?? S.map.getBearing()) * Math.PI / 180;
    const d = (h - S.map.getCameraTargetElevation()) * Math.tan(pitch);     // metres on, away from the camera
    const lat = to.lat + d * Math.cos(bearing) / 111320, lng = to.lng + d * Math.sin(bearing) / (111320 * Math.cos(to.lat * Math.PI / 180));
    glideNow({ ...camera, center: [lng, lat] });
  });
}
let glideRun = 0;
function glideNow(camera){
  const pace = flightPace();
  if (!pace) return S.map.jumpTo(camera);
  if (reduced()) return S.map.easeTo({ ...camera, duration: 300, freezeElevation: true });
  const to = camera.center && maplibregl.LngLat.convert(camera.center);
  const km = to ? S.map.getCenter().distanceTo(to) / 1000 : 0;
  const dz = camera.zoom != null ? camera.zoom - S.map.getZoom() : 0;
  // The flight rises to see both ends at once; from the whole city it would rise to the furthest out the map goes
  // (its minZoom) or beyond. The map then holds the height but not the path worked out for it: the place ran off to
  // a corner, waited there and jumped back (the twitch onto and off a chapter's card, seen on a phone). Such a
  // flight is kept just under the limit (flyTo's minZoom: the curve is worked out from it); one with both ends at
  // the limit already, as from the thread's card to a chapter's, has no room to rise, and glides across
  const floor = S.map.getMinZoom() + 0.05;
  const low = to && camera.zoom != null && peakZoom(to, camera.zoom, 1.9) < floor;
  const how = { ...camera, easing: smooth, duration: Math.round(flightMs(km, dz) * pace), essential: true, freezeElevation: true };
  if (low && Math.min(S.map.getZoom(), camera.zoom) < floor + 0.25) return S.map.easeTo(how);
  S.map.flyTo({ ...how, ...(low ? { minZoom: floor } : { curve: 1.9 }) });
}
// the zoom at the top of a flight to `to` with this curve, as MapLibre's flyTo works it out (van Wijk and Nuij)
function peakZoom(to, z1, rho){
  const merc = ll => [(ll.lng + 180) / 360, (1 - Math.log(Math.tan(Math.PI / 4 + ll.lat * Math.PI / 360)) / Math.PI) / 2];
  const z0 = S.map.getZoom(), a = merc(S.map.getCenter()), b = merc(to), c = S.map.getCanvas();
  const u1 = Math.hypot(b[0] - a[0], b[1] - a[1]) * 512 * 2 ** z0;
  if (u1 < 1e-6) return Math.min(z0, z1);
  const w0 = Math.max(c.clientWidth, c.clientHeight), w1 = w0 / 2 ** (z1 - z0), rho2 = rho * rho;
  const r = i => { const q = (w1 * w1 - w0 * w0 + (i ? -1 : 1) * rho2 * rho2 * u1 * u1) / (2 * (i ? w1 : w0) * rho2 * u1); return Math.log(Math.sqrt(q * q + 1) - q); };
  const r0 = r(0), r1 = r(1), top = r0 < 0 && r1 > 0 ? 0 : Math.abs(r0) < Math.abs(r1) ? r0 : r1;
  return z0 - Math.log2(Math.cosh(r0) / Math.cosh(top));
}
// how close a card takes the map to its place: near enough to pick out the building, with its street round it
const PLACE_ZOOM = 16;
const FLY_AFTER = 350;       // ms of the cards left still before the map flies
let flyWait;
export function setPlace(k, fly = true){
  const P = S.places; if (!P) return;
  const from = P.i;
  P.i = k;
  const c = P.cards[k], n = P.cards.filter(x => !x.intro).length;
  $('pCount').textContent = c.intro ? (c.chapter ? `Chapter ${c.chapter.j} of ${c.chapter.m}` : `${n} ${n === 1 ? 'story' : 'stories'}`) : `${numOf(P, k)} of ${n}`;
  if (S.selectedId != null) fstate(S.selectedId, { sel:false });
  S.selectedId = !c.intro && isB(c.refs[0]) ? c.refs[0] : null;
  if (S.selectedId != null) fstate(S.selectedId, { sel:true });
  drawPins();
  $('pCards').querySelectorAll('.pcard').forEach(el => el.classList.toggle('on', +el.dataset.i === k));
  loadAround(k);
  if (S.map.getTerrain()) warmNext(P, k);
  // the flight starts once the cards are left still: swiping back and forth would otherwise start a new flight
  // from wherever the last one had got to, low and short, never rising
  clearTimeout(flyWait);
  if (fly) flyWait = setTimeout(() => {
    if (!S.places || S.places.i !== k) return;
    if (c.intro) return fitAll(c);
    // the same place as the card before, come to from it: the map is there already
    if (c.same && from === k - 1) return;
    const pts = c.refs.map(refCentre), pad = cardPad();
    if (pts.length > 1) return glide({ ...fitCamera(pts, pad, PLACE_ZOOM), bearing: S.map.getBearing(), pitch: S.map.getPitch() });
    glide({ center: pts[0], zoom: Math.max(S.map.getZoom(), PLACE_ZOOM), padding: pad });
  }, FLY_AFTER);
}
const still = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
export function goToCard(k, smooth = true){
  const card = $('pCards').querySelector(`.pcard[data-i="${k}"]`);
  if (!card) return;
  // (the card already open: no scroll to wait for, so the map goes back to it now)
  if (S.places && S.places.i === k && !S.places.page) return setPlace(k);
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
  S.map?.getSource('approx')?.setData({ type:'FeatureCollection', features:[] });
  Object.keys(S.pins).forEach(k => { S.pins[k].remove(); delete S.pins[k]; });
  $('placesbar').hidden = true;
  if (showTime) $('timebar').hidden = false;
}
// the pins carry their stories' numbers. Pins too close to tell apart join as one, which shows one number (the open
// card's, if it is one of them, else the first) and a dot with how many more it holds; tapped, it lists them to
// choose from, the open one marked
export function drawPins(){
  if (!S.map || !S.map.getSource('places')) return;
  const seen = new Set(), drawn = [], P = S.places, cur = P && !P.cards[P.i]?.intro ? numOf(P, P.i) : null;
  // on a chapter's opening card, the other chapters' pins are faded
  const chap = P && P.cards[P.i]?.chapter ? new Set(chapterCards(P, P.i).map(c => c.n)) : null;
  for (const f of S.map.querySourceFeatures('places')) {
    const pr = f.properties, cl = pr.cluster;
    // (a joined pin can come once from each map tile it lies across, under another id and a little apart: the
    // first is drawn)
    const key = cl ? 'c' + pr.cluster_id : `p${pr.k}-${pr.j}`;
    if (cl) {
      const at = S.map.project(f.geometry.coordinates);
      const twin = drawn.find(d => d.lo === pr.lo && d.hi === pr.hi && Math.hypot(d.x - at.x, d.y - at.y) < 80);
      if (twin) continue;
      drawn.push({ lo: pr.lo, hi: pr.hi, x: at.x, y: at.y });
    }
    if (seen.has(key)) continue;
    seen.add(key);
    const nums = cl ? [...new Set(String(pr.ns || '').split(',').filter(Boolean).map(Number))].sort((a, b) => a - b) : [pr.n];
    if (!nums.length) nums.push(pr.lo);
    const mine = cur != null && nums.includes(cur), shown = mine ? cur : nums[0], more = nums.length - 1;
    if (!S.pins[key]) {
      const el = document.createElement('button');
      S.pins[key] = new maplibregl.Marker({ element: el }).setLngLat(f.geometry.coordinates).addTo(S.map);
    }
    const el = S.pins[key].getElement();
    // (set only when it changes: the pins are redrawn as the map moves)
    // (classes toggled, not set: the map's own classes on the marker place it)
    const html = `${shown}${more ? `<span class="more">+${more}</span>` : ''}`;
    el.classList.add('pin'); el.classList.toggle('joined', !!more); el.classList.toggle('on', mine);
    el.classList.toggle('dim', !!chap && !nums.some(x => chap.has(x)));
    el.style.setProperty('--pc', (P && P.cards[cardOf(shown)]?.colour) || 'var(--hl)');     // its chapter's colour
    if (el.innerHTML !== html) el.innerHTML = html;
    el.setAttribute('aria-label', more ? `Stories ${nums.join(', ')} here` : `Story ${shown}`);
    el.onclick = e => {
      e.stopPropagation();
      if (!more) return goToCard(cardOf(nums[0]));
      pinMenu(f.geometry.coordinates, nums);
    };
  }
  Object.keys(S.pins).forEach(k => { if (!seen.has(k)) { S.pins[k].remove(); delete S.pins[k]; } });
}
// the card of a story's number
const cardOf = n => S.places.cards.findIndex(c => !c.intro && c.n === n);
// a joined pin's stories, to choose from
let menu = null;
function pinMenu(xy, nums){
  menu?.remove();
  const P = S.places, box = document.createElement('div'), now = !P.cards[P.i]?.intro ? numOf(P, P.i) : null;
  box.className = 'pinmenu';
  box.innerHTML = nums.map(n => { const c = P.cards[cardOf(n)];
    return `<button data-n="${n}"${n === now ? ' class="on" aria-current="true"' : ''}><b>${n}</b> ${esc(c?.hint?.name || (c ? refName(c.refs[0]) : ''))}</button>`; }).join('');
  box.onclick = e => { const b = e.target.closest('[data-n]'); if (!b) return; menu?.remove(); menu = null; goToCard(cardOf(+b.dataset.n)); };
  // (it opens upwards, over the map: below the pin the cards would cover it; it scrolls when long)
  const at = S.map.project(xy), top = at.y, w = S.map.getContainer().clientWidth;
  const anchor = at.x < w / 3 ? 'bottom-left' : at.x > w * 2 / 3 ? 'bottom-right' : 'bottom';   // (and stays on the screen)
  box.style.maxHeight = Math.max(110, top - 80) + 'px';
  menu = new maplibregl.Popup({ closeButton: false, offset: 18, maxWidth: '260px', anchor, className: 'pinpop' }).setLngLat(xy).setDOMContent(box).addTo(S.map);
}
