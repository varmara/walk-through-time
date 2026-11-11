// Walk Through Time, city page: The sheet that slides up for layers, map options and cards; sharing a building.
import { $, CITY_ID } from './util.js';
import { S } from './state.js';
import { fstate } from './data.js';
import { unlight } from './cards.js';
import { setPlace } from './places.js';

// ================= The sheet =================
export const sheet = $('sheet');
export function openSheet(kind, title){
  S.sheetKind = kind;
  $('sShare').hidden = !(kind === 'card' && S.selectedId != null && S.features[S.selectedId]?.properties.osm);
  $('sTitle').textContent = title;
  ['pLayers', 'pMap', 'pCard'].forEach(id => $(id).hidden = true);
  $({ layers:'pLayers', map:'pMap', card:'pCard' }[kind]).hidden = false;
  sheet.hidden = false; sheet.scrollTop = 0;
  $('bLayers').setAttribute('aria-expanded', kind === 'layers');
  $('bMap').setAttribute('aria-expanded', kind === 'map');
}
// Share a building: named buildings get a small page of their own with a preview (pipeline/s09_share.py),
// the rest a plain link to the map. The phone's share sheet where there is one, else the link is copied.
export function shareLink(p){
  const site = new URL('../', location.href).href, osm = p.osm || '';
  return p.name ? `${site}data/share/${CITY_ID}/${osm.replace('/', '-')}.html` : `${site}${CITY_ID}/?osm=${osm}`;
}
export function toast(text){ const t = $('toast'); t.textContent = text; t.hidden = false; clearTimeout(t._h); t._h = setTimeout(() => t.hidden = true, 2200); }
$('sShare').onclick = async () => {
  const p = S.features[S.selectedId]?.properties; if (!p) return;
  const url = shareLink(p), title = (p.name || 'A building') + ' · Walk Through Time';
  if (navigator.share) { try { await navigator.share({ title, url }); } catch (e) { /* closed */ } return; }
  try { await navigator.clipboard.writeText(url); toast('Link copied'); }
  catch (e) { prompt('Copy this link', url); }
};
export function closeSheet(){
  sheet.hidden = true; S.sheetKind = null;
  unlight();
  $('bLayers').setAttribute('aria-expanded', false);
  $('bMap').setAttribute('aria-expanded', false);
  if (S.places) { setPlace(S.places.i, false); return; }   // back to the places strip, its building still selected
  if (S.selectedId != null && S.map) { fstate(S.selectedId, { sel:false }); S.selectedId = null; }
}
$('sClose').onclick = closeSheet;
addEventListener('keydown', e => { if (e.key === 'Escape' && !sheet.hidden) closeSheet(); });
$('bLayers').onclick = () => S.sheetKind === 'layers' ? closeSheet() : openSheet('layers', 'Layers');
$('bMap').onclick = () => S.sheetKind === 'map' ? closeSheet() : openSheet('map', 'Map');
$('bHome').onclick = () => S.map && S.map.easeTo({ ...S.city.home, duration:900 });
$('bNorth').onclick = () => S.map && S.map.easeTo({ bearing: 0, duration: 600 });
// the needle points to north as the map turns
export const turnNeedle = () => { $('needle').style.transform = `rotate(${-S.map.getBearing()}deg)`; };
