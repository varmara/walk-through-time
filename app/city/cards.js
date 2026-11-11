// Walk Through Time, city page: cards for buildings, areas and plaques.
// Every card is one layout. A kind of card only says what goes in it (buildingCard, areaCard, pinCard); renderCard
// draws it into the slots of the sheet in <city>/index.html, in their order there, and hides the empty ones:
//   image + credit · summary · facts (rows) · Did you know · old pictures · more old pictures · stories · links
import { $, PRECISION, dateText, eraOf, esc } from './util.js';
import { S } from './state.js';
import { areaOf, centreOf, fstate, isB, loadCard, parseRef, pinOf, saveActive, storyOf, tiled } from './data.js';
import { openSheet } from './sheet.js';
import { applyLayers, renderLayers } from './panels.js';
import { showPlaces } from './places.js';

const J = v => typeof v === 'string' ? JSON.parse(v) : v;      // properties from vector tiles arrive as strings
const a = (href, text, arrow = false) => `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(text)}${arrow ? ' →' : ''}</a>`;
const link = s => a(s.url, s.title);
const filePage = f => 'https://commons.wikimedia.org/wiki/File:' + encodeURIComponent(f.replace(/ /g, '_'));
const credit = f => [f.author, f.licence].filter(Boolean).map(esc).join(' · ');
export const layerTitle = id => S.layers.find(L => L.id === id)?.title || id;

// ================= The one layout =================
// card: { title, image: {src, alt, credit (html)}, summary (html), rows: [[label, html]], dyk: [{text, source}],
//         archive: [{file, year, author, licence}], coll: [{title, url}], stories: [story], after (html), links: [html] }
// story: { label, text, source, place, who, pin }: a story layer's entry, a plaque's words, an area's description
export function renderCard(c){
  const img = $('cImg');
  if (c.image) { img.src = c.image.src; img.alt = c.image.alt || ''; img.hidden = false; img.onerror = () => { img.hidden = true; $('cCredit').hidden = true; }; }
  else { img.hidden = true; img.removeAttribute('src'); }
  fill('cCredit', c.image && c.image.credit);
  fill('cSum', c.summary);
  $('cFacts').innerHTML = (c.rows || []).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');
  fill('cDyk', c.dyk && c.dyk.length && '<h3>Did you know?</h3>' + c.dyk.map(d =>
    `<p>${esc(d.text)} <span class="src">${a(d.source.url, d.source.kind || 'Source')}</span></p>`).join(''));
  fill('cArch', c.archive && c.archive.length && archiveHtml(c.archive));
  fill('cColl', c.coll && c.coll.length && collHtml(c.coll));
  $('cStories').innerHTML = (c.stories || []).map(storyHtml).join('') + (c.after || '');
  $('cStories').querySelectorAll('[data-ref]').forEach(x => x.onclick = e => { e.preventDefault(); openRef(x.dataset.ref); });
  $('cStories').querySelectorAll('.allplaces').forEach(btn => btn.onclick = () => showPlaces(btn.dataset.name, btn.dataset.b.split(',').map(parseRef)));
  $('cLinks').innerHTML = (c.links || []).join('');
  openSheet('card', c.title);
}
function fill(id, html){ $(id).hidden = !html; $(id).innerHTML = html || ''; }

function storyHtml(s){
  const src = s.source ? `<p class="src">${esc(s.source.kind || 'Wikipedia')}: ${link(s.source)}`
    + (s.place ? ` · ${esc(s.place.kind || 'Wikipedia')}: ${link(s.place)}` : '') + '</p>' : '';
  return `<div class="story">${s.label ? `<div class="seclbl">${esc(s.label)}</div>` : ''}
    ${s.text ? `<p>${esc(s.text)}</p>` : ''}${src}${s.note ? `<p class="src">${esc(s.note)}</p>` : ''}${aboutHtml(s.who, s.source)}
    ${s.pin ? `<p class="go"><a href="#" data-ref="${esc(s.pin)}">See the plaque on the map →</a></p>` : ''}</div>`;
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
// links to collections of old pictures that are not openly licensed (so not shown here), with each site's credit
// once (stories/<city>/credits.md)
function collHtml(cs){
  const host = u => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return ''; } };
  const credits = [...new Set(cs.map(c => (S.data.credits || {})[host(c.url)]).filter(Boolean))];
  return '<h3>More old pictures</h3><p>' + cs.map(c => a(c.url, c.title, true)).join(' ') + '</p>'
    + (credits.length ? credits.map(t => `<p class="src">${esc(t)}</p>`).join('')
      : '<p class="src">Linked, not shown, as the pictures are not openly licensed.</p>');
}
// who a person in the People layer was: the opening sentences of their Wikipedia article
function aboutHtml(who, source){
  const p = who && S.data.people && S.data.people[who];
  if (!p || !p.text) return '';
  const same = source && source.url === p.url;
  const named = p.text.toLowerCase().includes(who.split(' ').pop().toLowerCase());   // "William Booth was…"
  return `<div class="about">${named ? '' : `<b>${esc(who)}:</b> `}<span>${esc(p.text)}</span>
    <p class="src">${same ? '' : 'Wikipedia: '}<a href="${esc(p.url)}" target="_blank" rel="noopener">${same ? 'Read more on Wikipedia' : esc(p.title)}</a></p></div>`;
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
  if (at || centreOf(id)) go(at || centreOf(id));
  else loadCard(id).then(() => S.selectedId === id && go(centreOf(id))).catch(() => {});
  if (S.features[id].full || !tiled()) return showCard(id);
  renderCard({ title: refName(id), rows: [['Loading…', '']] });     // the title at once, the details when their file arrives
  loadCard(id).then(() => S.selectedId === id && showCard(id))
    .catch(() => { if (S.selectedId === id) renderCard({ title: refName(id), rows: [['Could not load', 'Check the connection and tap the building again.']] }); });
}
export function showCard(id){ renderCard(buildingCard(S.features[id].properties, id)); }

function buildingCard(p, id){
  const rows = [];
  if (p.today && !(p.full && p.full.endsWith(p.today))) rows.push(['Today', esc(p.today)]);    // the current occupier; the title is what the building was
  const aka = J(p.aka);
  if (aka && aka.length) rows.push(['Other names', aka.map(esc).join(' · ')]);   // old names, Historic England's, alternatives
  if (p.y != null) {
    const era = eraOf(p.y);
    rows.push(['Built', `${esc(dateText(p.y, p.f, p.per, p.dt))}<span class="pill" style="border-color:${era[3]}">${esc(era[2])}</span>`]);
    if (p.f === 'area') rows.push(['Date', `<span class="muted">No date for this building yet. ${esc(p.sh)}% of homes in its small `
      + `area were built ${esc(p.per)}, according to Council Tax records (Valuation Office Agency).</span>`]);
    else rows.push(['Date', `${esc(PRECISION[p.f] || '')} · from ${esc(p.src)}`]);
    const alts = p.alts || (p.alt ? [p.alt] : []);
    if (alts.length) rows.push(['Other dates', alts.map(x => `${esc(dateText(x.y, x.f, null, x.text))} <span class="muted">from ${esc(x.src)}</span>`).join('<br>')
      + '<div class="hint">Sources disagree. They may describe different moments, such as a founding and a rebuilding.</div>']);
  } else rows.push(['Built', '<span class="muted">not in open data yet</span>']);
  if (p.architect) rows.push(['Architect', esc(p.architect)]);
  if (p.grade) rows.push(['Listing', `Grade ${esc(p.grade)} listed`]);
  if (p.council) rows.push(['Council', esc(p.council)]);      // whose planning rules apply, near the city's edges
  if (p.kind !== 'bridge') rows.push(['Height', `≈ ${Math.round(p.h)} m${p.levels ? ' · ' + esc(p.levels) + (p.levels === '1' ? ' storey' : ' storeys') : ''}`]);
  if (p.kind && p.kind !== 'yes') rows.push(['Type (OSM)', esc(p.kind.replace(/_/g, ' '))]);

  const sumSrc = J(p.sumSrc);
  const summary = p.sum && `<p>${esc(p.sum)}</p><p class="src">${esc(sumSrc?.kind || '')}${sumSrc?.url ? ': ' + link(sumSrc)
    : sumSrc?.title ? ' (' + esc(sumSrc.title) + ')' : ''}</p>`;
  const stories = (p.stories || []).map(storyOf).map(s => ({ ...s, label: layerTitle(s.layer) }));
  const after = (S.entitiesAt[id] || []).map(m =>
    `<button class="textbtn allplaces" data-name="${esc(m.name)}" data-b="${m.bs.join(',')}">All ${m.bs.length} places: ${esc(m.name)} →</button>`).join('');

  const links = [];
  if (p.listUrl || p.listEntry) links.push(a(p.listUrl || 'https://historicengland.org.uk/listing/the-list/list-entry/' + p.listEntry, 'Historic England list entry', true));
  if (p.article) links.push(a(p.article, 'Wikipedia', true));
  if (p.qid) links.push(a('https://www.wikidata.org/wiki/' + p.qid, 'Wikidata'));
  links.push(a('https://www.openstreetmap.org/' + p.osm, 'OpenStreetMap'));

  const cr = J(p.credit), file = p.image && decodeURIComponent(p.image.split('/Special:FilePath/')[1] || '').replace(/_/g, ' ');
  const image = p.image && { src: p.image.replace(/^http:/, 'https:') + '?width=640', alt: p.name || '',
    credit: `Photo${cr && credit(cr) ? ': ' + credit(cr) : ''} · <a href="${esc(filePage(file))}" target="_blank" rel="noopener">Wikimedia Commons</a>` };
  return { title: p.full || p.name || placeName(p), image, summary, rows, dyk: J(p.dyk), archive: J(p.archive), coll: J(p.coll),
           stories, after, links };    // the title, for landmarks: what it was · what it is
}

// ================= Areas =================
const AREA_TEXT = {
  conservation: { note: 'The outline is indicative. The council\'s own conservation area maps are definitive.' },
  lws: { text: 'A Local Wildlife Site: a place of local importance for wildlife, chosen by the county\'s Local Wildlife Sites '
    + 'partnership. Most are not nature reserves and have no legal protection, but planning decisions take them into account.' },
};
export function showArea(p){ renderCard(areaCard(p)); }
function areaCard(p){
  const type = (S.groups.get(p.t) || {}).title || 'Nature area';
  const rows = [['Type', esc(type.replace(/s$/, ''))]];
  if (p.designated) rows.push(['Designated', esc(p.designated)]);
  if (p.lpa) rows.push(['Council', esc(p.lpa)]);
  rows.push(['Source', esc(p.source)]);
  const t = AREA_TEXT[p.t];
  const stories = t ? [{ ...t, note: t.note || p.credit }] : [];
  const links = [p.source === 'Natural England' ? a('https://designatedsites.naturalengland.org.uk/', 'Natural England designated sites', true)
    : p.source === 'Historic England' ? a('https://historicengland.org.uk/listing/what-is-designation/local/conservation-areas/', 'About conservation areas', true)
    : p.url ? a(p.url, `${p.source}: the map data`, true)
    : a('https://www.openstreetmap.org/copyright', 'OpenStreetMap')];
  return { title: p.name, rows, stories, links };
}

// ================= Plaques and other pins =================
export function showPin(p){
  renderCard(pinCard(p));
  plaqueOn(p.on == null || p.on === '' ? null : +p.on);
}
function pinCard(p){
  return { title: p.name, rows: [['Layer', esc((S.groups.get(p.group) || {}).title || layerTitle(p.layer))]],
           stories: [{ text: p.text, source: J(p.source), place: J(p.place), who: p.who }], coll: J(p.coll) };
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
      <p class="go"><a href="#">Open the building →</a></p>`;
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
  return (r[0] === 'p' ? pinOf(r) : areaOf(r)).properties.name;
}
export function openRef(r){
  if (isB(r)) return selectBuilding(r);
  if (r[0] === 'p') return showPin(pinOf(r).properties);
  const f = areaOf(r), bb = f.bb;
  if (!S.active.has(f.properties.t)) { S.active.add(f.properties.t); saveActive(); renderLayers(); applyLayers(); }
  S.map.fitBounds([[bb[0], bb[1]], [bb[2], bb[3]]],
    { padding: innerWidth >= 760 ? { top: 60, bottom: 60, left: 60, right: 420 } : { top: 80, left: 30, right: 70, bottom: innerHeight * 0.45 }, maxZoom: 17, duration: 800 });
  showArea(f.properties);
}
