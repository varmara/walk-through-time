// Walk Through Time, city page: cards for buildings, areas and plaques.
// Every card is one layout. A kind of card only says what goes in it (buildingCard, areaCard, pinCard); renderCard
// draws it into the slots of the sheet in <city>/index.html, in their order there, and hides the empty ones:
//   image + credit · summary · facts (rows) · Did you know · old pictures · more old pictures · stories · links
import { $, PRECISION, dateText, eraOf, esc } from './util.js';
import { S } from './state.js';
import { areaOf, centreOf, fstate, isB, loadCard, parseRef, pinOf, refOf, routeOf, saveActive, storyOf, tiled } from './data.js';
import { openSheet } from './sheet.js';
import { applyLayers, renderLayers } from './panels.js';
import { showPlaces } from './places.js';
import { hoursText, openNow } from './hours.js';

const J = v => typeof v === 'string' ? JSON.parse(v) : v;      // properties from vector tiles arrive as strings
const a = (href, text) => `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(text)}</a>`;
const link = s => a(s.url, s.title);
const filePage = f => 'https://commons.wikimedia.org/wiki/File:' + encodeURIComponent(f.replace(/ /g, '_'));
const credit = f => [f.author, f.licence].filter(Boolean).map(esc).join(' · ');
const host = u => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return u; } };
// a place's opening hours (open now, in Nottingham's time; the hours) and its website, from OpenStreetMap
export function openRows(list, title){
  return (list || []).map(o => {
    const st = o.oh && openNow(o.oh), lines = [];
    if (o.name && o.name !== title) lines.push(`<b>${esc(o.name)}</b>${o.what ? ` <span class="muted">${esc(o.what)}</span>` : ''}`);
    if (st) lines.push(`<span class="${st.open ? 'open' : 'shut'}">${esc(st.text)}</span>`);
    if (o.oh) lines.push(`<span class="muted">${hoursText(o.oh).map(esc).join('<br>')}</span>`);
    if (o.web) lines.push(a(o.web, host(o.web)));
    return [o.oh ? 'Opening hours' : 'Website', lines.join('<br>')];
  });
}
export const HOURS_NOTE = 'Opening hours from OpenStreetMap, which anyone can edit: worth checking before a special trip.';
export const layerTitle = id => S.layers.find(L => L.id === id)?.title || id;

// ================= The one layout =================
// card: { title, image: {src, alt, credit (html)}, summary (html), rows: [[label, html]], dyk: [{text, source}],
//         archive: [{file, year, author, licence}], coll: [{title, url}], stories: [story], after (html), links: [html] }
// story: { label, text, source, place, who, pin }: a story layer's entry, a plaque's words, an area's description
// ================= Footnotes: every source on a card, numbered once in reading order =================
// cite(source) -> a superscript number; html() -> the Sources list at the foot of the card
export function notes(){
  const list = [], at = new Map();
  const key = s => { try { return decodeURIComponent(s.url || '') || s.title; } catch { return s.url || s.title; } };
  const cite = s => {
    if (!s || !(s.url || s.title)) return '';
    let n = at.get(key(s));
    if (!n) { list.push(s); n = list.length; at.set(key(s), n); }
    return `<sup class="fn"><a href="#" data-fn="${n}" aria-label="Source ${n}">${n}</a></sup>`;
  };
  const one = s => (s.title && s.kind ? esc(s.kind) + ': ' : '') + (s.url ? a(s.url, s.title || s.kind) : esc(s.title || s.kind))
    + (s.note ? ` <span class="muted">${esc(s.note)}</span>` : '');
  const html = () => list.length ? '<h3>Sources</h3><ol class="notes">' + list.map((s, i) => `<li id="fn${i + 1}">${one(s)}</li>`).join('') + '</ol>' : '';
  return { cite, html };
}

// ================= People: everyone the People layer ties to a place, by name =================
let PEOPLE = null;
const NOT_PEOPLE = new Set(['people-events']);   // plaques to events and places
function people(){
  if (PEOPLE) return PEOPLE;
  PEOPLE = new Map();
  for (const L of S.layers.filter(L => L.kind === 'people'))
    for (const g of L.groups) if (!NOT_PEOPLE.has(g.key))
      for (const [name, refs] of g.items || []) if (!PEOPLE.has(name)) PEOPLE.set(name, { refs, group: g });
  return PEOPLE;
}
const ROLE = { 'people-architects': 'architect', 'people-writers': 'writer', 'people-science': 'scientist or engineer',
  'people-industry': 'industry and trade', 'people-sport': 'sport', 'people-arts': 'arts and performance',
  'people-faith': 'faith and charity', 'people-military': 'the military', 'people-public': 'public life' };
const whoLink = name => `<a href="#" class="who" data-who="${esc(name)}">${esc(name)}</a>`;
// the names of People-layer people in an escaped text become links to their places
function linkPeople(html){
  // and people with an article but no place on the map (an architect a story names on a bridge): to the article
  const names = [...new Set([...people().keys(), ...Object.keys(S.data.people || {})])]
    .filter(n => n.includes(' ')).sort((x, y) => y.length - x.length);
  const done = new Set();
  for (const n of names) {
    const e = esc(n);
    if (done.has(n) || !html.includes(e)) continue;
    const i = html.indexOf(e);
    if (html.lastIndexOf('<a', i) > html.lastIndexOf('</a>', i)) continue;   // already inside a link
    html = html.slice(0, i) + whoLink(n) + html.slice(i + e.length);
    done.add(n);
  }
  return html;
}
function openWho(name){
  const P = people().get(name), info = S.data.people && S.data.people[name];
  if (P && P.refs.length > 1) return showPlaces(name, P.refs.map(r => typeof r === 'number' ? r : parseRef(String(r))));
  if (P && P.refs.length === 1 && P.refs[0] !== S.selectedId) return openRef(P.refs[0]);
  if (info && info.url) window.open(info.url, '_blank', 'noopener');
}
// the people tied to a building: name, what they were, a link to their places (or article)
function connected(id){
  const out = [];
  for (const [name, P] of people()) if (P.refs.includes(id)) {
    const info = S.data.people && S.data.people[name];
    const many = P.refs.length > 1;
    const name_ = many || !info?.url ? whoLink(name) : a(info.url, name);
    out.push({ name, html: `${name_}${many ? ` <span class="muted">(${P.refs.length} places)</span>` : ''}`
      + `${ROLE[P.group.key] ? `<span class="muted">, ${ROLE[P.group.key]}</span>` : ''}${many && info?.url ? ' · ' + a(info.url, 'Wikipedia') : ''}` });
  }
  return out;
}

export function renderCard(c){
  const img = $('cImg');
  if (c.image) { img.src = c.image.src; img.alt = c.image.alt || ''; img.hidden = false; img.onerror = () => { img.hidden = true; $('cCredit').hidden = true; }; }
  else { img.hidden = true; img.removeAttribute('src'); }
  fill('cCredit', c.image && c.image.credit);
  const N = c.N || notes();
  fill('cSum', c.summary);
  $('cFacts').innerHTML = (c.rows || []).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');
  fill('cDyk', c.dyk && c.dyk.length && '<h3>Did you know?</h3>' + c.dyk.map(d =>
    `<p>${linkPeople(esc(d.text))}${N.cite(d.source)}</p>`).join(''));
  fill('cArch', c.archive && c.archive.length && archiveHtml(c.archive));
  fill('cColl', c.coll && c.coll.length && collHtml(c.coll));
  $('cStories').innerHTML = (c.stories || []).map(st => storyHtml(st, N)).join('') + (c.after || '') + N.html();
  const card = $('pCard');
  card.querySelectorAll('[data-ref]').forEach(x => x.onclick = e => { e.preventDefault(); openRef(parseRef(x.dataset.ref)); });
  card.querySelectorAll('.allplaces').forEach(btn => btn.onclick = () => showPlaces(btn.dataset.name, btn.dataset.b.split(',').map(parseRef)));
  card.querySelectorAll('[data-who]').forEach(x => x.onclick = e => { e.preventDefault(); openWho(x.dataset.who); });
  card.querySelectorAll('[data-fn]').forEach(x => x.onclick = e => {        // to the source, and show which
    e.preventDefault();
    const li = $('fn' + x.dataset.fn); if (!li) return;
    li.scrollIntoView({ behavior: 'smooth', block: 'center' });
    li.classList.remove('hit'); void li.offsetWidth; li.classList.add('hit');
  });
  $('cLinks').innerHTML = (c.links || []).join('');
  fill('cPhotos', '');
  openSheet('card', c.title);
  if (c.cat) morePhotos(c.cat, c.image && c.image.file, S.selectedId);
}

// more photos of the building: its Commons category, asked of Commons when the card opens (credited, linked)
async function morePhotos(cat, skip, id){
  const u = 'https://commons.wikimedia.org/w/api.php?action=query&format=json&origin=*&generator=categorymembers'
    + `&gcmtitle=${encodeURIComponent('Category:' + cat)}&gcmtype=file&gcmlimit=14&prop=imageinfo&iiprop=url|extmetadata`
    + '&iiurlwidth=320&iiextmetadatafilter=Artist|LicenseShortName';
  let pages;
  try { pages = Object.values((await (await fetch(u)).json()).query?.pages || {}); } catch { return; }
  if (S.selectedId !== id) return;                   // another card is open by now
  const strip = (h) => { const d = document.createElement('div'); d.innerHTML = h || ''; return d.textContent.trim(); };
  const shots = pages.filter(pg => pg.imageinfo && /\.(jpe?g|png|webp|tiff?)$/i.test(pg.title) && pg.title.replace(/^File:/, '') !== skip)
    .slice(0, 10).map(pg => {
      const ii = pg.imageinfo[0], m = ii.extmetadata || {};
      const cr = [strip(m.Artist?.value), m.LicenseShortName?.value].filter(Boolean).map(x => esc(x.slice(0, 60))).join(' · ');
      return `<a class="shot" href="${esc(ii.descriptionurl)}" target="_blank" rel="noopener" title="${esc(pg.title)}">
        <img loading="lazy" src="${esc(ii.thumburl || ii.url)}" alt="${esc(pg.title.replace(/^File:|\.\w+$/g, ''))}" onerror="this.parentNode.remove()">
        <span>${cr}</span></a>`;
    });
  if (shots.length) fill('cPhotos', `<h3>More photos</h3><div class="strip">${shots.join('')}</div>`
    + `<p class="src">From Wikimedia Commons: ${a('https://commons.wikimedia.org/wiki/Category:' + encodeURIComponent(cat.replace(/ /g, '_')), 'Category:' + cat)}</p>`);
}
// a page cached from before a section was added has no place for it: leave it out rather than stop the card
function fill(id, html){ const el = $(id); if (!el) return; el.hidden = !html; el.innerHTML = html || ''; }

const kinded = s => s && { ...s, kind: s.kind || 'Wikipedia' };
function storyHtml(s, N){
  const refs = N.cite(kinded(s.source)) + N.cite(kinded(s.place));
  return `<div class="story">${s.label ? `<div class="seclbl">${esc(s.label)}</div>` : ''}
    ${s.text ? `<p>${linkPeople(esc(s.text))}${refs}</p>` : refs ? `<p class="src">Source${refs}</p>` : ''}${s.note ? `<p class="src">${esc(s.note)}</p>` : ''}${aboutHtml(s.who, s.source, N)}
    ${s.pin ? `<p class="go"><a href="#" data-ref="${esc(s.pin)}">See the plaque on the map</a></p>` : ''}${seeHtml(J(s.see))}</div>`;
}
// "See also": other stories the story file links to (stories/<city>/*.md: see), each opening where it is
function seeHtml(see){
  if (!Array.isArray(see) || !see.length) return '';
  return `<p class="see">See also: ${see.map(([name, ref]) => `<a href="#" data-ref="${esc(ref)}">${esc(name)}</a>`).join(', ')}</p>`;
}
// old photographs, postcards and prints, oldest first, from Commons; each credited and linked to its page
function archiveHtml(arch){
  return '<h3>Old pictures</h3><div class="strip">' + arch.map(f => {
    const src = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + encodeURIComponent(f.file.replace(/ /g, '_')) + '?width=320';
    return `<a class="shot" href="${esc(filePage(f.file))}" target="_blank" rel="noopener" title="${esc(f.file)}">
      <img loading="lazy" src="${esc(src)}" alt="${esc(f.file.replace(/\.\w+$/, ''))}" onerror="const a=this.closest('#cArch');this.parentNode.remove();if(a&&!a.querySelector('.shot'))a.hidden=true">
      <span><b>${esc(f.year)}</b>${credit(f) ? ' · ' + credit(f) : ''}</span></a>`;
  }).join('') + '</div>';
}
// links to collections of old pictures that are not openly licensed (so not shown here): "More photos from
// <site>", the site named as stories/<city>/credits.md names it; several collections on one site are listed after it
function collHtml(cs){
  const host = u => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return ''; } };
  const sites = new Map();
  for (const c of cs){ const h = host(c.url); if (!sites.has(h)) sites.set(h, []); sites.get(h).push(c); }
  return [...sites].map(([h, list]) => {
    const name = (S.data.credits || {})[h] || h;
    return '<p>More photos from ' + (list.length === 1 ? a(list[0].url, name)
      : esc(name) + ': ' + list.map(c => a(c.url, c.title)).join(', ')) + '</p>';
  }).join('');
}
// who a person in the People layer was: the opening sentences of their Wikipedia article
function aboutHtml(who, source, N){
  const p = who && S.data.people && S.data.people[who];
  if (!p || !p.text) return '';
  const named = p.text.toLowerCase().includes(who.split(' ').pop().toLowerCase());   // "William Booth was…"
  return `<div class="about">${named ? '' : `<b>${esc(who)}:</b> `}<span>${esc(p.text)}</span>${N.cite({ kind: 'Wikipedia', title: p.title, url: p.url })}</div>`;
}

// ================= Buildings =================
// at: where the building was tapped, to move there at once; otherwise its centre, which is in its card file
export function selectBuilding(id, at){
  unlight();
  if (S.selectedId != null) fstate(S.selectedId, { sel:false });
  S.selectedId = id;
  fstate(id, { sel:true });
  const go = c => c && S.map.easeTo({ center:c, zoom:Math.max(S.map.getZoom(), 16.5), duration:700,
    padding: innerWidth >= 760 ? { right: 400 } : { bottom: innerHeight * 0.45 } });
  if (S.features[id].full || !tiled()) { if (at || centreOf(id)) go(at || centreOf(id)); return showCard(id); }
  // the card first, then the glide: moving the map (with hills, especially) loads tiles and keeps a phone busy,
  // and the card's file would wait behind them
  renderCard({ title: refName(id), rows: [['Loading…', '']] });     // the title at once, the details when their file arrives
  const t0 = performance.now();
  loadCard(id).then(() => {
    if (S.selectedId !== id) return;
    showCard(id);
    if (/[?&]timing\b/.test(location.search)) console.log(`card ${id}: ${Math.round(performance.now() - t0)} ms`);
    requestAnimationFrame(() => S.selectedId === id && go(at || centreOf(id)));
  }).catch(() => {
    if (S.selectedId !== id) return;
    go(at || centreOf(id));
    renderCard({ title: refName(id), rows: [['Could not load', 'Check the connection and tap the building again.']] });
  });
}
export function showCard(id){ renderCard(buildingCard(S.features[id].properties, id)); }

// where a date comes from, as a footnote: the record itself where the card knows it
const VOA = 'https://www.gov.uk/government/statistics/council-tax-stock-of-properties-2023';
const wikiTitle = u => { try { return decodeURIComponent(u.split('/wiki/')[1]).replace(/_/g, ' '); } catch { return u; } };
function dateSource(src, p){
  const osm = { kind: 'OpenStreetMap', url: 'https://www.openstreetmap.org/' + p.osm };
  if (!src) return null;
  if (/^Council Tax/.test(src)) return { kind: 'Valuation Office Agency', title: 'Council Tax: stock of properties, 2023 (homes by build period, small areas)', url: VOA };
  if (/^Historic England/.test(src)) return { kind: 'Historic England', title: `List entry ${p.listEntry || ''}`.trim(),
    url: p.listUrl || (p.listEntry && 'https://historicengland.org.uk/listing/the-list/list-entry/' + p.listEntry),
    note: 'the date as Wikipedia\'s lists of listed buildings give it' };
  if (src === 'Wikidata') return p.qid ? { kind: 'Wikidata', title: `${p.qid}, inception`, url: `https://www.wikidata.org/wiki/${p.qid}#P571` } : { kind: 'Wikidata', title: 'Wikidata' };
  if (/^Wikipedia/.test(src)) {
    const t = (/\((.+)\)/.exec(src) || [])[1];
    return t ? { kind: 'Wikipedia', title: t, url: 'https://en.wikipedia.org/wiki/' + encodeURIComponent(t.replace(/ /g, '_')) }
      : p.article ? { kind: 'Wikipedia', title: wikiTitle(p.article), url: p.article } : { kind: 'Wikipedia', title: 'Wikipedia' };
  }
  if (src === 'OpenStreetMap') return { ...osm, title: 'this building\'s start date' };
  return { ...osm, title: `this building's start date, citing ${src}` };    // start_date:source
}
const shortSrc = src => /^Historic England/.test(src) ? 'Historic England' : src.replace(/\s*\(.*\)$/, '');

// places with a story within 150 m, nearest first: buildings, and story and plaque pins
function nearby(id, xy){
  if (!xy) return [];
  const [x0, y0] = xy, kx = 111320 * Math.cos(y0 * Math.PI / 180), ky = 110540;
  const d = (x, y) => Math.hypot((x - x0) * kx, (y - y0) * ky);
  const out = [];
  for (const [i, x, y] of S.data.near || []) if (i !== id) { const m = d(x, y); if (m <= 150) out.push({ ref: i, m, name: S.features[i]?.properties.name }); }
  (S.data.pins?.features || []).forEach((f, k) => {
    const kind = S.groups.get(f.properties.group)?.layer.kind;
    if ((kind === 'stories' || kind === 'people') && +f.properties.on !== id) {
      const m = d(...f.geometry.coordinates); if (m <= 150) out.push({ ref: 'p' + k, m, name: f.properties.name });
    }
  });
  // one place in two outlines, or a building and its plaque, share a name: the nearer of them, once
  const seen = new Set();
  return out.filter(o => o.name).sort((p, q) => p.m - q.m)
    .filter(o => { const k = o.name.toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, 3);
}
const walkTo = ([x, y]) => /iPhone|iPad|Macintosh/.test(navigator.userAgent)
  ? `https://maps.apple.com/?daddr=${y},${x}&dirflg=w` : `https://www.google.com/maps/dir/?api=1&destination=${y},${x}&travelmode=walking`;

function buildingCard(p, id){
  const rows = [], N = notes();
  // the summary is read first, so its source is the first footnote
  const sumSrc = J(p.sumSrc);
  const summary = p.sum && `<p>${linkPeople(esc(p.sum))}${N.cite(sumSrc && { ...sumSrc, kind: sumSrc.kind || 'Source' })}</p>`;
  if (p.today && !(p.full && p.full.endsWith(p.today))) rows.push(['Today', esc(p.today)]);    // the current occupier; the title is what the building was
  const aka = J(p.aka);
  if (aka && aka.length) rows.push(['Other names', aka.map(esc).join(' · ')]);   // old names, Historic England's, alternatives
  const open = openRows(J(p.open), p.full || p.name);
  if (open.length) { rows.push(...open); if (open.some(r => r[0] === 'Opening hours')) open[open.length - 1][1] += `<div class="hint">${esc(HOURS_NOTE)}</div>`; }
  if (p.y != null) {
    // the year with its footnote; how exact it is; other dates, each with its own
    const era = eraOf(p.y), alts = J(p.alts) || (p.alt ? [p.alt] : []);
    const how = p.f === 'area' ? `No date for this building yet: ${esc(p.sh)}% of homes in its small area were built ${esc(p.per)}, according to Council Tax records.`
      : esc(PRECISION[p.f] || '') + (alts.length ? '' : `, from ${esc(shortSrc(p.src))}`);
    rows.push(['Built', `${esc(dateText(p.y, p.f, p.per, p.dt))}${N.cite(dateSource(p.src, p))}<span class="pill" style="border-color:${era[3]}">${esc(era[2])}</span>`
      + `<div class="muted">${how}</div>`
      + alts.map(x => `<div>${esc(dateText(x.y, x.f, null, x.text))}${N.cite(dateSource(x.src, p))} <span class="muted">${esc(shortSrc(x.src))}</span></div>`).join('')
      + (alts.length ? `<div class="hint">The first is from ${esc(shortSrc(p.src))}. Sources disagree; they may describe different moments, such as a founding and a rebuilding.</div>` : '')]);
  } else rows.push(['Built', '<span class="muted">not in open data yet</span>']);
  // the architects: each linked to their article, and to their other buildings when the People layer has them
  // (an older index has one architect, with archUrl)
  const archs = p.architects || (p.architect ? [[p.architect, p.archUrl]] : []);
  if (archs.length) rows.push([archs.length > 1 ? 'Architects' : 'Architect', archs.map(([name, url, unsure]) => {
    const n = people().get(name)?.refs.length || 0;
    return (url ? a(url, name) : esc(name)) + (unsure ? ' <span class="muted">(probably)</span>' : '')
      + (n > 1 ? ` <span class="muted">·</span> <a href="#" class="who" data-who="${esc(name)}">${n} buildings</a>` : '');
  }).join('<br>')]);
  const archNames = new Set(archs.map(x => x[0]));
  const who = connected(id).filter(w => !archNames.has(w.name));   // the architects have a row of their own
  if (who.length) rows.push(['People', who.map(w => w.html).join('<br>')]);
  if (p.grade) rows.push(['Listing', `Grade ${esc(p.grade)} listed`]);
  if (p.council) rows.push(['Council', esc(p.council)]);      // whose planning rules apply, near the city's edges
  if (p.kind !== 'bridge') rows.push(['Height', `≈ ${Math.round(p.h)} m${p.levels ? ' · ' + esc(p.levels) + (p.levels === '1' ? ' storey' : ' storeys') : ''}`]);
  if (p.kind && p.kind !== 'yes') rows.push(['Type (OSM)', esc(p.kind.replace(/_/g, ' '))]);

  const near = nearby(id, J(p.xy));
  if (near.length) rows.push(['Nearby', near.map(o => `<a href="#" data-ref="${esc(o.ref)}">${esc(o.name)}</a> <span class="muted">${Math.round(o.m / 10) * 10 || 10} m</span>`).join('<br>')]);
  const stories = (p.stories || []).map(storyOf).map(s => ({ ...s, label: layerTitle(s.layer) }));
  const after = (S.entitiesAt[id] || []).filter(m => !people().has(m.name)).map(m =>
    `<button class="textbtn allplaces" data-name="${esc(m.name)}" data-b="${m.bs.join(',')}">All ${m.bs.length} places: ${esc(m.name)}</button>`).join('');

  const links = [];
  if (p.listUrl || p.listEntry) links.push(a(p.listUrl || 'https://historicengland.org.uk/listing/the-list/list-entry/' + p.listEntry, 'Historic England list entry'));
  if (p.article) links.push(a(p.article, 'Wikipedia'));
  if (p.qid) links.push(a('https://www.wikidata.org/wiki/' + p.qid, 'Wikidata'));
  links.push(a('https://www.openstreetmap.org/' + p.osm, 'OpenStreetMap'));
  if (J(p.xy)) links.unshift(a(walkTo(J(p.xy)), 'Walking directions'));

  const cr = J(p.credit), file = p.image && decodeURIComponent(p.image.split('/Special:FilePath/')[1] || '').replace(/_/g, ' ');
  const image = p.image && { src: p.image.replace(/^http:/, 'https:') + '?width=640', alt: p.name || '', file,
    credit: `Photo${cr && credit(cr) ? ': ' + credit(cr) : ''} · <a href="${esc(filePage(file))}" target="_blank" rel="noopener">Wikimedia Commons</a>` };
  return { title: p.full || p.name || placeName(p), image, summary, rows, dyk: J(p.dyk), archive: J(p.archive), coll: J(p.coll),
           stories, after, links, N, cat: p.cat };    // the title, for landmarks: what it was · what it is
}

// ================= Areas =================
const AREA_TEXT = {
  parkgarden: { text: 'A designed landscape on Historic England\'s Register of Parks and Gardens of Special Historic Interest. '
    + 'Registration protects its character through the planning system; it does not open private grounds to the public.' },
  article4: { text: 'An Article 4 direction: here some changes that would not otherwise need planning permission, such as new '
    + 'windows and doors, need the council\'s permission, to keep the character of the street.' },
  tpo: { text: 'Trees protected by a tree preservation order: cutting them down, topping or lopping them needs the council\'s consent.' },
  conservation: { note: 'The outline is indicative. The council\'s own conservation area maps are definitive.' },
  lws: { text: 'A Local Wildlife Site: a place of local importance for wildlife, chosen by the county\'s Local Wildlife Sites '
    + 'partnership. Most are not nature reserves and have no legal protection, but planning decisions take them into account.' },
};
const AREA_TYPE = { parkgarden: 'Registered park or garden', article4: 'Article 4 area', tpo: 'Tree preservation order',
  conservation: 'Conservation area' };
export function showArea(p){ renderCard(areaCard(p)); }
function areaCard(p){
  const L = S.layers.find(x => x.id === p.t || x.groups.some(g => g.key === p.t));
  if (!p.source && L?.source) p = { ...p, source: L.source.title };   // an area only in the tiles: its layer says whose
  const type = AREA_TYPE[p.t] || ((S.groups.get(p.t) || {}).title || 'Nature area').replace(/s$/, '');
  const rows = [['Type', esc(type)]];
  if (p.designated) rows.push(['Designated', esc(p.designated)]);
  if (p.lpa) rows.push(['Council', esc(p.lpa)]);
  if (p.grade) rows.push(['Grade', `Grade ${esc(p.grade)}`]);
  rows.push(['Source', esc(p.source)]);
  const t = AREA_TEXT[p.t];
  const stories = t ? [{ ...t, note: t.note || p.credit }] : [];
  const links = [p.t === 'parkgarden' ? a(p.url || 'https://historicengland.org.uk/listing/the-list/list-entry/' + p.listEntry, 'Historic England list entry')
    : p.t === 'article4' || p.t === 'tpo' ? a(p.url || L?.source?.url || '#', `${p.source}: more about this`)
    : p.source === 'Natural England' ? a('https://designatedsites.naturalengland.org.uk/', 'Natural England designated sites')
    : p.source === 'Historic England' ? a('https://historicengland.org.uk/listing/what-is-designation/local/conservation-areas/', 'About conservation areas')
    : p.url ? a(p.url, `${p.source}: the map data`)
    : a('https://www.openstreetmap.org/copyright', 'OpenStreetMap')];
  return { title: p.name, rows, stories, links };
}

// ================= Plaques and other pins =================
export function showPin(p){
  renderCard(pinCard(p));
  plaqueOn(p.on == null || p.on === '' ? null : +p.on);
}
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const dayText = d => { const m = /^(\d{4})-(\d{2})(?:-(\d{2}))?$/.exec(d || '');     // 1921-09-08 -> 8 September 1921
  return m ? `${m[3] ? +m[3] + ' ' : ''}${MONTHS[+m[2] - 1]} ${m[1]}` : d; };
const WHEELCHAIR = { yes: 'Step-free access', limited: 'Limited step-free access', no: 'No step-free access' };
const fee = v => v === 'no' ? 'Free' : v === 'yes' ? 'There is a charge' : v;
const wikiUrl = wp => { const m = /^(\w+):(.+)$/.exec(wp || ''); return m && `https://${m[1]}.wikipedia.org/wiki/${encodeURIComponent(m[2].replace(/ /g, '_'))}`; };
// links every visitor place can have: its website, Art UK, Wikipedia, Wikidata, OpenStreetMap
function placeLinks(p, withWeb = true){
  const links = [];
  if (withWeb && p.web) links.push(a(p.web, host(p.web)));
  if (p.artuk) links.push(a('https://artuk.org/discover/artworks/' + p.artuk, 'Art UK'));
  else if (p.layer === 'art' && p.name && p.name.toLowerCase() !== (p.kind || '').toLowerCase())   // Art UK records public sculpture
    links.push(a('https://artuk.org/discover/artworks/search/keyword:' + encodeURIComponent(p.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')), 'Find on Art UK'));
  if (wikiUrl(p.wp)) links.push(a(wikiUrl(p.wp), 'Wikipedia'));
  if (p.wd) links.push(a('https://www.wikidata.org/wiki/' + p.wd, 'Wikidata'));
  if (p.osm) links.push(a('https://www.openstreetmap.org/' + p.osm, 'OpenStreetMap'));
  return links;
}
function pinCard(p){
  const rows = [['Layer', esc((S.groups.get(p.group) || {}).title || layerTitle(p.layer))]];
  if (p.artist) rows.push(['Artist', esc(p.artist)]);
  if (p.start) rows.push(['From', esc(dayText(p.start))]);
  const open = openRows(p.oh || p.web ? [{ oh: p.oh, web: p.web }] : [], p.name);
  if (open.length) { rows.push(...open); if (p.oh) open[0][1] += `<div class="hint">${esc(HOURS_NOTE)}</div>`; }
  if (p.fee) rows.push(['Admission', esc(fee(p.fee))]);
  if (WHEELCHAIR[p.wc]) rows.push(['Access', esc(WHEELCHAIR[p.wc])]);
  if (p.op || p.gov) rows.push(['Run by', esc(p.op || p.gov)]);
  if (p.acc) rows.push(['Accreditation', esc(p.acc)]);
  return { title: p.name, rows, stories: [{ text: p.text, source: J(p.source), place: J(p.place), who: p.who, see: p.see }], coll: J(p.coll),
           links: placeLinks(p, false) };
}

// ================= Walking routes, and toilets, water and benches =================
const NETWORK = { iwn: 'International walking route', nwn: 'National walking route', rwn: 'Regional walking route', lwn: 'Local walking route' };
// ================= the land: brooks, woods, old railways and canals… (pipeline/s06_land.py) =================
const LAND_KIND = { brook: 'Brook or stream', pond: 'Pond', wood: 'Wood', rail: 'Disused railway', canal: 'Lost canal',
  oldsite: 'Historic site', cemetery: 'Cemetery or churchyard', allot: 'Allotments', orchard: 'Orchard' };
// from the map: the tile's properties, with its named place's details (from the index) when it has one
export function showLand(p){
  const e = p.i != null && (S.data.land || [])[p.i];
  renderCard(landCard(e ? { ...p, ...e } : p));
}
function landCard(p){
  const type = p.k || LAND_KIND[p.t] || 'Place';
  const rows = [['Type', esc(type)]];
  const src = s => !s ? '' : /^https?:/.test(s) ? ` <span class="muted">(${a(s, host(s))})</span>` : ` <span class="muted">(${esc(s)})</span>`;
  if (p.t === 'rail' || p.t === 'canal') {
    if (p.from) rows.push(['Opened', esc(p.from) + src(p.fromSrc)]);
    if (p.to) rows.push(['Closed', esc(p.to) + src(p.toSrc)]);
    if (!p.from && !p.to) rows.push(['Years', '<span class="muted">Not recorded yet</span>']);
  }
  if (p.date) rows.push(['Date', esc(p.date)]);
  if (p.u) rows.push(['Runs', 'Underground here, in a culvert']);
  if (p.km) rows.push(['On this map', `${esc(p.km)} km`]);
  rows.push(['Source', 'OpenStreetMap']);
  const links = placeLinks({ wp: p.wp, wd: p.wd, osm: p.osm || p.o });
  return { title: p.name || type, rows, stories: [], links };
}

export function showRoute(i){ const r = routeOf('r' + i); if (r) renderCard(routeCard(r.properties)); }
function routeCard(p){
  const rows = [];
  if (NETWORK[p.network] || p.ref) rows.push(['Route', esc([NETWORK[p.network], p.ref].filter(Boolean).join(' · '))]);
  if (p.km) rows.push(['On this map', `${esc(p.km)} km`]);
  if (p.op) rows.push(['Looked after by', esc(p.op)]);
  return { title: p.name, rows, stories: p.text ? [{ text: p.text }] : [], links: placeLinks(p) };
}
const BASIC = { toilets: 'Public toilets', water: 'Drinking water', benches: 'Bench' };
export function showBasic(p){ renderCard(basicCard(p)); }
function basicCard(p){
  const rows = openRows(p.oh ? [{ oh: p.oh }] : [], '');
  if (p.fee) rows.push(['Charge', esc(fee(p.fee))]);
  if (p.t === 'toilets' && WHEELCHAIR[p.wc]) rows.push(['Access', esc(WHEELCHAIR[p.wc])]);
  if (p.ch) rows.push(['Baby changing', p.ch === 'yes' ? 'Yes' : p.ch === 'no' ? 'No' : esc(p.ch)]);
  if (p.acc === 'customers') rows.push(['Who can use them', 'Customers only']);
  if (p.bk) rows.push(['Backrest', p.bk === 'yes' ? 'Yes' : 'No']);
  return { title: p.name || BASIC[p.t] || 'Place', rows, links: placeLinks(p) };
}
// a plaque's building: lit up while the plaque is open, and shown inside the plaque's card
export function unlight(){ if (S.litOn != null && S.map) fstate(S.litOn, { hl:false }); S.litOn = null; }
export function plaqueOn(b){
  unlight();
  if (b == null || !S.features[b]) return;
  S.litOn = b; fstate(b, { hl:true });
  const box = document.createElement('div');
  box.className = 'onbuilding';
  $('cStories').appendChild(box);
  const draw = () => {
    const q = S.features[b].properties;
    const when = q.y != null ? dateText(q.y, q.f, q.per, q.dt) : null;
    box.innerHTML = `<div class="seclbl">On this building</div>
      <p><b>${esc(q.full || q.name || placeName(q))}</b>${when ? ` · ${esc(when)}` : ''}${q.grade ? ` · Grade ${esc(q.grade)} listed` : ''}</p>
      ${q.sum ? `<p>${esc(q.sum)}</p>` : ''}
      <p class="go"><a href="#">Open the building</a></p>`;
    box.querySelector('a').onclick = e => { e.preventDefault(); unlight(); selectBuilding(b); };
  };
  draw();
  loadCard(b).then(() => box.isConnected && draw()).catch(() => {});
}

// ================= Place references =================
// a building without a name: its address, or the street it stands on, or its listing's own words
export function placeName(p){
  if (p.where) return /^\d/.test(p.where) ? p.where : `A building on ${p.where}`;
  if (p.listName) return p.listName.replace(/\w\S*/g, w => w.length > 2 && w === w.toUpperCase() ? w[0] + w.slice(1).toLowerCase() : w);
  return 'A building';
}
export function refName(r){
  if (isB(r)) { const p = S.features[r].properties; return p.name || placeName(p); }
  return refOf(r).properties.name;
}
export function openRef(r){
  if (isB(r)) return selectBuilding(r);
  if (r[0] === 'p') return showPin(pinOf(r).properties);
  const f = refOf(r), bb = f.bb, key = r[0] === 'r' ? 'routes' : f.properties.t;
  if (!S.active.has(key)) { S.active.add(key); saveActive(); renderLayers(); applyLayers(); }
  S.map.fitBounds([[bb[0], bb[1]], [bb[2], bb[3]]],
    { padding: innerWidth >= 760 ? { top: 60, bottom: 60, left: 60, right: 420 } : { top: 80, left: 30, right: 70, bottom: innerHeight * 0.45 }, maxZoom: 17, duration: 800 });
  r[0] === 'r' ? renderCard(routeCard(f.properties)) : r[0] === 'l' ? renderCard(landCard(f.properties)) : showArea(f.properties);
}
