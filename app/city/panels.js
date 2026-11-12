// Walk Through Time, city page: The Layers sheet and the Map sheet (base maps, the legend of eras).
import { $, CITY_ID, ERAS, PIN_LAYERS, SECTIONS, esc, fmt, store } from './util.js';
import { S } from './state.js';
import { hasPins, isArea, kindOf, marksBuildings, parseRef, saveActive } from './data.js';
import { addNls, buildingColour, setHills } from './map.js';
import { updateYear } from './timebar.js';
import { openRef } from './cards.js';
import { showPlaces } from './places.js';

// ================= Layers panel =================
export function renderLayers(){
  const html = [];
  for (const sec of SECTIONS) {
    const Ls = S.layers.filter(L => L.section === sec && L.groups.some(g => g.count > 0));
    if (!Ls.length) continue;
    html.push(`<div class="section"><div class="seclbl">${esc(sec)}</div>`);
    for (const L of Ls) {
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
          : PIN_LAYERS.includes(L.id) ? `<span class="sw dot" style="background:var(--p-${esc(L.id)})"></span>` : '';
        html.push(`<label class="lrow"${single ? '' : ' style="padding-left:14px"'}><input type="checkbox" data-g="${esc(g.key)}"${S.active.has(g.key) ? ' checked' : ''}>${sw}
          <span>${esc(title)}</span><span class="n">${fmt(g.count)}</span>
          ${single || g.items ? `<button class="more" data-info="g-${esc(g.key)}" aria-label="About ${esc(title)}" aria-expanded="false">ⓘ</button>` : ''}</label>
          <div class="linfo" id="info-g-${esc(g.key)}" hidden>${infoHtml(L, single || g.items ? g : null, single)}</div>`);
      }
    }
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
  $('lSections').querySelectorAll('[data-b]').forEach(btn => btn.onclick = e => {
    e.preventDefault();
    const bs = btn.dataset.b.split(',').map(parseRef);
    bs.length > 1 ? showPlaces(btn.dataset.name, bs) : openRef(bs[0]);
  });
  updateSummary();
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
  if (L.kind === 'stories') parts.push('<p class="src">Each entry is checked against its Wikipedia article.</p>');
  if (withIntro && (L.kind === 'stories' || L.kind === 'people'))
    parts.push(`<p class="src"><a href="../data/share/${CITY_ID}/layer-${encodeURIComponent(L.id)}.html">Read “${esc(L.title)}” as a page</a></p>`);
  else if (L.source) parts.push(`<p class="src">Source: <a href="${esc(L.source.url)}" target="_blank" rel="noopener">${esc(L.source.title)}</a></p>`);
  return parts.join('');
}
export function updateSummary(){
  const names = [...S.active].map(k => S.groups.get(k)).filter(Boolean)
    .map(g => g.layer.groups.filter(x => x.count > 0).length === 1 ? g.layer.title : g.title);
  $('lSummary').innerHTML = names.length
    ? `<b>${names.length} on:</b> ${esc(names.join(', '))}${[...S.active].some(marksBuildings) ? '<span class="key"><i style="background:var(--marked)"></i>in the layer, no date yet</span>' : ''}`
    : 'No layers on. Tick any to highlight them on the map.';
  $('lClear').hidden = !names.length;
  $('layerCount').hidden = !names.length;
  $('layerCount').textContent = names.length;
}
$('lClear').onclick = () => { S.active.clear(); saveActive(); renderLayers(); applyLayers(); };

export function applyLayers(){
  updateSummary();
  if (!S.map || !S.map.getLayer('b')) return;
  S.map.setPaintProperty('b', 'fill-extrusion-color', buildingColour());
  const pinGroups = [...S.active].filter(hasPins);
  S.map.setLayoutProperty('routes', 'visibility', S.active.has('routes') ? 'visible' : 'none');
  const basics = [...S.active].filter(k => kindOf(k) === 'points');
  S.map.setLayoutProperty('basics', 'visibility', basics.length ? 'visible' : 'none');
  S.map.setFilter('basics', ['in', ['get', 't'], ['literal', basics.length ? basics : ['none']]]);
  S.map.setLayoutProperty('storypins', 'visibility', pinGroups.length ? 'visible' : 'none');
  S.map.setFilter('storypins', ['in', ['get', 'group'], ['literal', pinGroups.length ? pinGroups : ['none']]]);
  const types = [...S.active].filter(isArea);
  const vis = types.length ? 'visible' : 'none';
  ['nature-fill', 'nature-line'].forEach(id => {
    S.map.setLayoutProperty(id, 'visibility', vis);
    S.map.setFilter(id, ['in', ['get', 't'], ['literal', types.length ? types : ['none']]]);
  });
}

// ================= Map panel =================
export function toggle(btn, fn){ btn.onclick = () => { const on = btn.getAttribute('aria-pressed') !== 'true'; btn.setAttribute('aria-pressed', on); fn(on); }; }
toggle($('tUnknown'), on => { S.showUnknown = on; updateYear(); });
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
export function drawLegend(){
  $('legend').innerHTML = ERAS.map(e => `<div><i style="background:${e[3]}"></i>${e[2]}</div>`).join('')
    + `<div><i style="background:var(--unknown)"></i>no date</div>`
    + `<div><i style="background:var(--marked)"></i>in a ticked layer, no date</div>`;
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
