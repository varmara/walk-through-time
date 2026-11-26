// Walk Through Time, city page: The Layers sheet and the Map sheet (base maps, the legend of eras).
import { $, CITY_ID, ERAS, PIN_LAYERS, SECTIONS, STORY_LABELS, STORY_SECTIONS, esc, fmt, store } from './util.js';
import { S } from './state.js';
import { hasPins, isArea, isStorySet, isThread, kindOf, marksBuildings, parseRef, saveActive } from './data.js';
import { addNls, paintBuildings, setHills, setLand } from './map.js';
import { curYear, updateYear } from './timebar.js';
import { openRef } from './cards.js';
import { clearPlaces, showGroups, showPlaces } from './places.js';
import { closeSheet } from './sheet.js';

// places fold under their area's heading: all of an area's places together, the areas in the order their first
// place comes, each area's places in their own order (a place added later, with a higher order, joins its area's
// heading rather than starting a second one at the end)
function byArea(Ls){
  const areas = [...new Set(Ls.map(L => L.area || null))];
  return areas.flatMap(a => Ls.filter(L => (L.area || null) === a));
}
// ================= Layers panel =================
export function renderLayers(){
  renderStories();
  const html = [];
  for (const sec of SECTIONS.filter(s => !STORY_SECTIONS.includes(s))) {
    const Ls = byArea(S.layers.filter(L => L.section === sec && L.groups.some(g => g.count > 0)));
    if (!Ls.length) continue;
    html.push(`<div class="section"><div class="seclbl">${esc(sec)}</div>`);
    // places fold under small headings (The city, South of the Trent…), each open while one of its layers is on
    let area = null;
    for (const L of Ls) {
      if ((L.area || null) !== area) {
        if (area) html.push('</details>');
        area = L.area || null;
        if (area) {
          const on = Ls.some(x => x.area === area && x.groups.some(g => S.active.has(g.key)));
          html.push(`<details class="area"${on ? ' open' : ''}><summary>${esc(area)}<span class="n">${Ls.filter(x => x.area === area).length}</span></summary>`);
        }
      }
      const gs = L.groups.filter(g => g.count > 0);
      const single = gs.length === 1;
      if (!single) html.push(`<div class="lrow" style="cursor:default;border-bottom:0;padding-bottom:2px"><b>${esc(L.title)}</b>
        <button class="more" data-info="${esc(L.id)}" aria-label="About ${esc(L.title)}" aria-expanded="false">ⓘ</button></div>
        <div class="linfo" id="info-${esc(L.id)}" hidden>${infoHtml(L, null)}</div>`);
      for (const g of gs) {
        const title = single ? L.title : g.title;
        const sw = L.kind === 'areas' ? `<span class="sw" style="background:var(--n-${esc(g.key)})"></span>`
          : L.kind === 'points' ? `<span class="sw dot" style="background:var(--b-${esc(g.key)})"></span>`
          : L.kind === 'routes' ? '<span class="sw line" style="background:var(--route)"></span>'
          : L.kind === 'land' ? `<span class="sw${['brook', 'rail', 'canal'].includes(g.key) ? ' line' : g.key === 'oldsite' ? ' edge' : ''}" style="--c:var(--l-${esc(g.key)})"></span>`
          : PIN_LAYERS.includes(L.id) ? `<span class="sw dot" style="background:var(--p-${esc(L.id)})"></span>` : '';
        html.push(`<label class="lrow"${single ? '' : ' style="padding-left:14px"'}><input type="checkbox" data-g="${esc(g.key)}"${S.active.has(g.key) ? ' checked' : ''}>${sw}
          <span>${esc(title)}</span><span class="n">${fmt(g.count)}</span>
          ${single || g.items ? `<button class="more" data-info="g-${esc(g.key)}" aria-label="About ${esc(title)}" aria-expanded="false">ⓘ</button>` : ''}</label>
          <div class="linfo" id="info-g-${esc(g.key)}" hidden>${infoHtml(L, single || g.items ? g : null, single)}</div>`);
      }
    }
    if (area) html.push('</details>');
    html.push('</div>');
  }
  $('lSections').innerHTML = html.join('');
  $('lSections').querySelectorAll('input[data-g]').forEach(cb => cb.onchange = () => {
    cb.checked ? S.active.add(cb.dataset.g) : S.active.delete(cb.dataset.g);
    saveActive(); applyLayers();
  });
  $('lSections').querySelectorAll('.find').forEach(inp => inp.oninput = () => {
    const q = inp.value.trim().toLowerCase();
    inp.nextElementSibling.querySelectorAll('.item').forEach(b => { b.hidden = q && !b.dataset.name.toLowerCase().includes(q); });
  });
  $('lSections').querySelectorAll('[data-info]').forEach(btn => btn.onclick = e => {
    e.preventDefault(); e.stopPropagation();
    const box = $('info-' + btn.dataset.info), open = box.hidden;
    box.hidden = !open; btn.setAttribute('aria-expanded', open);
  });
  $('lSections').querySelectorAll('[data-cards]').forEach(btn => btn.onclick = e => {
    e.preventDefault();
    const k = btn.dataset.cards, L = S.layers.find(x => x.id === k && !S.groups.has(k));
    showGroups(L ? L.groups.filter(g => g.count > 0).map(g => g.key) : [k], btn.dataset.title);
  });
  $('lSections').querySelectorAll('[data-b]').forEach(btn => btn.onclick = e => {
    e.preventDefault();
    const bs = btn.dataset.b.split(',').map(parseRef);
    bs.length > 1 ? showPlaces(btn.dataset.name, bs) : openRef(bs[0]);
  });
  updateSummary();
}
// ================= Stories sheet =================
// The places (folded by area), the threads and the People's groups: a tap opens one as numbered cards. Its ⓘ
// says what it is and lists what is in it.
function storyCount(gs){
  return new Set(gs.flatMap(g => (g.items || []).flatMap(it => (typeof it[0] === 'number' ? [it[0]] : it[1]).map(r => r + '|' + it[0])))).size;
}
export function renderStories(){
  const html = [], row = (key, title, n, L, g, indent, parts) => `<div class="srow${indent ? ' sub' : ''}">
      ${parts ? `<button class="fold" data-fold="${esc(key)}" aria-expanded="false" aria-controls="parts-${esc(key)}" aria-label="Show the parts of ${esc(title)}"></button>` : indent ? '' : '<span class="nofold"></span>'}
      <button class="sopen" data-set="${esc(key)}" data-title="${esc(title)}"><span>${esc(title)}</span><span class="n">${fmt(n)}</span></button>
      <button class="more" data-sinfo="${esc(key)}" aria-label="About ${esc(title)}" aria-expanded="false">ⓘ</button></div>
    <div class="linfo" id="sinfo-${esc(key)}" hidden>${infoHtml(L, g, !g || !indent)}</div>`;
  for (const sec of STORY_SECTIONS) {
    const Ls = byArea(S.layers.filter(L => L.section === sec && L.groups.some(g => g.count > 0 && g.items?.length)));
    if (!Ls.length) continue;
    html.push(`<div class="section"><div class="seclbl">${esc(STORY_LABELS[sec] || sec)}</div>`);
    let area = null;
    for (const L of Ls) {
      if ((L.area || null) !== area) {
        if (area) html.push('</details>');
        area = L.area || null;
        if (area) html.push(`<details class="area"${S.places && Ls.some(x => x.area === area && x.title === S.places.name) ? ' open' : ''}><summary>${esc(area)}<span class="n">${Ls.filter(x => x.area === area).length}</span></summary>`);
      }
      const gs = L.groups.filter(g => g.count > 0 && g.items?.length);
      if (L.kind === 'people') { gs.forEach(g => html.push(row(g.key, g.title, g.items.length, L, g, false))); continue; }
      // a thread's chapters (a place's parts: Wilford's river and village), each its own set, folded under it
      html.push(row(L.id, L.title, storyCount(gs), L, null, false, gs.length > 1));
      if (gs.length > 1) html.push(`<div class="parts" id="parts-${esc(L.id)}" hidden>${gs.map(g => row(g.key, g.title, storyCount([g]), L, g, true)).join('')}</div>`);
    }
    if (area) html.push('</details>');
    html.push('</div>');
  }
  const box = $('stSections');
  box.innerHTML = html.join('');
  box.querySelectorAll('[data-set]').forEach(btn => btn.onclick = () => {
    const k = btn.dataset.set, L = !S.groups.has(k) && S.layers.find(x => x.id === k);
    closeSheet();
    showGroups(L ? L.groups.filter(g => g.count > 0).map(g => g.key) : [k], btn.dataset.title);
  });
  box.querySelectorAll('[data-fold]').forEach(btn => btn.onclick = () => {
    const el = $('parts-' + btn.dataset.fold), open = el.hidden;
    el.hidden = !open; btn.setAttribute('aria-expanded', open);
  });
  box.querySelectorAll('[data-sinfo]').forEach(btn => btn.onclick = e => {
    e.preventDefault(); e.stopPropagation();
    const el = $('sinfo-' + btn.dataset.sinfo), open = el.hidden;
    el.hidden = !open; btn.setAttribute('aria-expanded', open);
  });
  box.querySelectorAll('[data-cards]').forEach(btn => btn.onclick = e => {
    e.preventDefault();
    const k = btn.dataset.cards, L = S.layers.find(x => x.id === k && !S.groups.has(k));
    closeSheet();
    showGroups(L ? L.groups.filter(g => g.count > 0).map(g => g.key) : [k], btn.dataset.title);
  });
  box.querySelectorAll('[data-b]').forEach(btn => btn.onclick = e => {
    e.preventDefault();
    const bs = btn.dataset.b.split(',').map(parseRef);
    bs.length > 1 ? showPlaces(btn.dataset.name, bs) : openRef(bs[0]);
  });
}
export function infoHtml(L, g, withIntro = true){
  const parts = [];
  if (withIntro && L.intro) parts.push(`<p>${esc(L.intro)}</p>`);
  // items are [name, [buildings]] (older data: [building, name]); long lists sort ignoring a leading "The"
  const norm = it => typeof it[0] === 'number' ? [it[1], [it[0]]] : it;
  const sortKey = n => n.replace(/^the\s+/i, '').toLowerCase();
  let items = g && g.items ? g.items.map(norm) : [];
  if (L.kind === 'rule') items = items.slice().sort((a, b) => sortKey(a[0]).localeCompare(sortKey(b[0])));
  if (items.length > 20) parts.push(`<input class="find" type="search" placeholder="Find in ${items.length} names" aria-label="Find a name in this list">`);
  if (items.length) parts.push(`<div class="items">${items.map(it => {
    const [name, bs] = it;
    return `<button class="item" data-b="${bs.join(',')}" data-name="${esc(name)}">${esc(name)}${bs.length > 1 ? `<span class="cnt">${bs.length}</span>` : ''}</button>`;
  }).join('')}</div>`);
  // the places of a story layer's or a topic's group (or of the whole layer), as numbered cards in date order
  // (a place's, a thread's or a group of people's cards open from its row in the Stories sheet)

  if (isThread(L)) parts.push('<p class="src">Each story, person and plaque here is told on its own card, with its source.</p>');
  if (withIntro && (L.kind === 'stories' || L.kind === 'people' || L.kind === 'topics'))
    parts.push(`<p class="src"><a href="../data/share/${CITY_ID}/layer-${encodeURIComponent(L.id)}.html">Read “${esc(L.title)}” as a page</a></p>`);
  else if (L.source) parts.push(`<p class="src">Source: <a href="${esc(L.source.url)}" target="_blank" rel="noopener">${esc(L.source.title)}</a></p>`);
  return parts.join('');
}
export function updateSummary(){
  const names = [...S.active].map(k => S.groups.get(k)).filter(Boolean)
    .map(g => g.layer.groups.filter(x => x.count > 0).length === 1 ? g.layer.title : g.title);
  // numbered places on the map (a story's, a topic's, a person's) are not a layer, but they are what is shown: said
  // first, with a way to hide them
  // a story set open: only its places are shown on the map, the ticked layers wait until it is closed
  const places = S.places ? `<span class="placeson">Showing only <b>${esc(S.places.name)}</b>${names.length ? ': these layers come back when it is closed' : ''}.
    <button class="textbtn" id="lPlacesOff">Close it</button></span>` : '';
  $('lSummary').innerHTML = places + (names.length
    ? `<b>${names.length} on:</b> ${esc(names.join(', '))}${[...S.active].some(marksBuildings) ? '<span class="key"><i style="background:var(--marked)"></i>in the layer, no date yet</span>' : ''}`
    : places ? '' : 'No layers on. Tick any to highlight them on the map.');
  const off = $('lPlacesOff');
  if (off) off.onclick = () => { clearPlaces(true); updateSummary(); };
  $('lClear').hidden = !names.length && !S.places;
  $('layerCount').hidden = !names.length;
  $('layerCount').textContent = names.length;
}
$('lClear').onclick = () => { if (S.places) clearPlaces(true); S.active.clear(); saveActive(); renderLayers(); applyLayers(); };
$('bLayers').addEventListener('click', () => updateSummary());       // (the numbered places may have changed since)
$('bStories').addEventListener('click', () => renderStories());     // (the open set's area unfolds)

S.applyLayers = () => applyLayers();
export function applyLayers(){
  updateSummary();
  if (!S.map || !S.map.getLayer('b')) return;
  paintBuildings();
  // while a story set is open, only its places are shown: the ticked layers wait (S.active is kept)
  const active = S.places ? new Set() : S.active;
  const pinGroups = [...active].filter(hasPins);
  S.map.setLayoutProperty('routes', 'visibility', active.has('routes') ? 'visible' : 'none');
  const basics = [...active].filter(k => kindOf(k) === 'points');
  S.map.setLayoutProperty('basics', 'visibility', basics.length ? 'visible' : 'none');
  S.map.setFilter('basics', ['in', ['get', 't'], ['literal', basics.length ? basics : ['none']]]);
  S.map.setLayoutProperty('storypins', 'visibility', pinGroups.length ? 'visible' : 'none');
  S.map.setLayoutProperty('storypins-halo', 'visibility', pinGroups.length ? 'visible' : 'none');
  // a pin is in its own layer's group, and in any topic's groups it was put in (its T: ",war-1831,coal,")
  const topics = pinGroups.filter(k => kindOf(k) === 'topics');
  const pinFilter = ['any', ['in', ['get', 'group'], ['literal', pinGroups.length ? pinGroups : ['none']]],
    ...topics.map(k => ['in', ',' + k + ',', ['coalesce', ['get', 'T'], '']])];
  S.map.setFilter('storypins', pinFilter);
  S.map.setFilter('storypins-halo', ['all', ['has', 'approx'], pinFilter]);
  S.landTypes = [...active].filter(k => kindOf(k) === 'land');
  setLand(S.landTypes, curYear());
  const types = [...active].filter(isArea);
  const vis = types.length ? 'visible' : 'none';
  ['nature-fill', 'nature-line'].forEach(id => {
    S.map.setLayoutProperty(id, 'visibility', vis);
    S.map.setFilter(id, ['in', ['get', 't'], ['literal', types.length ? types : ['none']]]);
  });
}

// ================= Map panel =================
export function toggle(btn, fn){ btn.onclick = () => { const on = btn.getAttribute('aria-pressed') !== 'true'; btn.setAttribute('aria-pressed', on); fn(on); }; }
const offPeriod = key => key === NODATE ? !S.showUnknown : S.periodsOff.has(key);
function setPeriods(keys, on){
  for (const k of keys) {
    if (k === NODATE) S.showUnknown = on;
    else if (on) S.periodsOff.delete(k); else S.periodsOff.add(k);
  }
  store.set('periods', JSON.stringify([...S.periodsOff]));
  store.set('undated', S.showUnknown ? '' : 'off');
  $('legend').querySelectorAll('[data-per]').forEach(b => b.setAttribute('aria-pressed', !offPeriod(b.dataset.per)));
  updateYear();
}
try { for (const k of JSON.parse(store.get('periods') || '[]')) S.periodsOff.add(k); } catch {}
if (store.get('undated') === 'off') S.showUnknown = false;
// the hills: on unless this visitor turned them off (a slow phone, say)
toggle($('tHills'), on => { store.set('hills', on ? 'on' : 'off'); setHills(on); });
export function groundNote(){
  $('areaNote').hidden = !(S.stats && S.stats.estimated);     // only when some homes have an area estimate
  const G = S.data && S.data.ground;
  $('groundRow').hidden = !G;
  if (!G) return;
  $('tHills').setAttribute('aria-pressed', store.get('hills') !== 'off');
  $('groundNote').textContent = `The ground as it is today, from the Environment Agency's laser survey (to ${G.year}), `
    + `at true scale: from ${G.range[0]} to ${G.range[1]} m above sea level. Railway cuttings, the canal and filled-in land changed it over time.`;
}
document.querySelectorAll('[data-base]').forEach(btn => btn.onclick = () => setBase(btn.dataset.base));
// how the map flies between places: kept in this browser
const showFlight = () => { const k = store.get('flight') || 'normal';
  document.querySelectorAll('[data-flight]').forEach(b => b.setAttribute('aria-pressed', b.dataset.flight === k)); };
document.querySelectorAll('[data-flight]').forEach(b => b.onclick = () => { store.set('flight', b.dataset.flight); showFlight(); });
showFlight();
export function setBase(kind){
  document.querySelectorAll('[data-base]').forEach(b => b.setAttribute('aria-pressed', b.dataset.base === kind));
  $('keyRow').hidden = !(kind === 'nls' && !store.get('mtKey'));
  if (!S.map) return;
  S.map.setLayoutProperty('osm', 'visibility', kind === 'osm' ? 'visible' : 'none');
  if (S.map.getLayer('nls')) S.map.setLayoutProperty('nls', 'visibility', kind === 'nls' ? 'visible' : 'none');
  ['parks', 'water', 'waterline', 'roads'].forEach(l => S.map.setLayoutProperty(l, 'visibility', kind === 'none' ? 'visible' : 'none'));
}
$('mtSave').onclick = () => {
  const k = $('mtKey').value.trim(); if (!k) return;
  store.set('mtKey', k); addNls(k); setBase('nls');
};
// The legend's periods are switches: tap one to hide or show its buildings, or show all or none at once. The choice
// is remembered per visitor ('periods': the labels hidden; 'undated': off).
const NODATE = 'no date';
export function drawLegend(){
  const sw = (key, colour, label) => `<button type="button" class="per" data-per="${esc(key)}" aria-pressed="${!offPeriod(key)}">`
    + `<i style="background:${colour}"></i>${esc(label)}</button>`;
  $('legend').innerHTML = ERAS.map(e => sw(e[2], e[3], e[2])).join('')
    + sw(NODATE, 'var(--unknown)', 'no date')
    + `<div><i style="background:var(--marked)"></i>in a ticked layer, no date</div>`
    + `<span class="perall"><button type="button" class="linkish" data-all="1">Show all</button>`
    + `<button type="button" class="linkish" data-all="0">Hide all</button></span>`;
  $('legend').querySelectorAll('[data-per]').forEach(b => b.onclick = () => setPeriods([b.dataset.per], offPeriod(b.dataset.per)));
  $('legend').querySelectorAll('[data-all]').forEach(b => b.onclick = () => setPeriods([...ERAS.map(e => e[2]), NODATE], b.dataset.all === '1'));
  $('legendNotes')?.remove();
  const notes = ERAS.filter(e => e[4]);
  const src = (S.city && S.city.periodSources) || [];
  if (notes.length) $('legend').insertAdjacentHTML('afterend', `<details class="periods" id="legendNotes"><summary>What each period was in ${esc(S.city.name)}</summary>`
    + notes.map(e => `<p><i style="background:${e[3]}"></i><b>${esc(e[2])}</b> ${esc(e[4])}</p>`).join('')
    + (src.length ? `<p class="src">Sources: ${src.map(s => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a>`).join(' · ')}</p>` : '')
    + '</details>');
}
drawLegend();
$('legend').insertAdjacentHTML('afterend', '<p class="note" id="areaNote" hidden>Palest of all: no date for the building itself, only the period when most homes in its small area were built (Council Tax records).</p>');
