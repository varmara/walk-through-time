// Walk Through Time, city page: Small helpers, colours and date wording: eras (their colours are --era-* in app/theme.css), $, esc, fetchJSON.


export const CITY_ID = document.body.dataset.city;
export const MAX_YEAR = new Date().getFullYear();

// Eras: [from, to, label, colour, note]. Warm = old, cool = new: the colours are --era-1 … --era-9 in
// app/theme.css. A city sets its own periods in cities/<city>.json ("periods": [{from, label, note}]), drawn from
// the city's history, and takes colours evenly from the nine; these are the default.
export const tok = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
export const PALETTE = [1, 2, 3, 4, 5, 6, 7, 8, 9].map(i => tok('--era-' + i));
export let ERAS = [[0, 1699, 'before 1700'], [1700, 1799, '1700s'], [1800, 1839, '1800–39'], [1840, 1879, '1840–79'],
  [1880, 1913, '1880–1913'], [1914, 1945, '1914–45'], [1946, 1979, '1946–79'], [1980, 1999, '1980–99'], [2000, 9999, '2000+']]
  .map((e, i) => [...e, PALETTE[i]]);
export const FADE = { exact: 0, approx: 0.2, century: 0.35, area: 0.45 };   // how far each precision fades towards the background
export const SECTIONS = ['Stories', 'Visit', 'People', 'Heritage', 'Nature', 'Today'];
export const AREA_TYPES = ['nnr', 'lnr', 'sssi', 'ancient', 'reserve', 'lws', 'conservation', 'parkgarden', 'article4', 'tpo'];   // areas drawn on the ground
export const PIN_LAYERS = ['attractions', 'art', 'boards'];   // pins with a colour of their own (--p-<layer>); other pins --marked
export const BASICS = ['toilets', 'water', 'benches'];                   // points drawn close up (--b-<key>)

export const $ = id => document.getElementById(id);
export const store = { get(k){ try { return localStorage.getItem(k); } catch { return null; } },
                set(k,v){ try { localStorage.setItem(k,v); } catch {} } };
export const say = t => { $('status').textContent = t || ''; };
export const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
export const fmt = n => n.toLocaleString('en-GB');
export function progress(p, step){ $('lpct').textContent = Math.round(p) + '%'; if (step) $('lstep').textContent = step; }

export async function fetchJSON(url, ms = 30000){
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    const r = await fetch(url, { cache:'no-cache', signal: ctrl.signal });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } catch (e) {
    throw new Error(e.name === 'AbortError' ? 'timed out' : e.message);
  } finally { clearTimeout(timer); }
}
// The data file is large, so read it as a stream and show how much has arrived.
export async function fetchData(url){
  const r = await fetch(url, { cache:'no-cache' });
  if (!r.ok) throw new Error(r.status === 404 ? 'the data file has not been built yet' : 'HTTP ' + r.status);
  if (!r.body || !window.TextDecoder) return r.json();
  const reader = r.body.getReader(), parts = [];
  let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parts.push(value); got += value.length;
    progress(5 + Math.min(60, got / 4e5), `loading map data… ${(got / 1e6).toFixed(1)} MB`);
  }
  const all = new Uint8Array(got);
  let o = 0; for (const p of parts) { all.set(p, o); o += p.length; }
  progress(66, 'reading buildings…');
  return JSON.parse(new TextDecoder().decode(all));
}

// ================= Colour and date wording =================
export function hexToRgb(h){ const n = parseInt(h.slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255]; }
export function mix(a, b, t){ const A = hexToRgb(a), B = hexToRgb(b);
  return '#' + A.map((v, i) => Math.round(v + (B[i] - v) * t).toString(16).padStart(2, '0')).join(''); }
export const eraOf = y => ERAS.find(e => y >= e[0] && y <= e[1]) || ERAS[ERAS.length - 1];
export function setPeriods(periods){
  if (!periods || periods.length < 2) return;
  const n = periods.length;
  ERAS = periods.map((p, i) => [p.from, i < n - 1 ? periods[i + 1].from - 1 : 9999, p.label,
    PALETTE[Math.round(i * (PALETTE.length - 1) / (n - 1))], p.note || '']);
}
export function colourFor(p){
  if (p.y == null) return tok('--unknown');
  return mix(eraOf(p.y)[3], tok('--bg'), FADE[p.f] || 0);
}
export function ordinal(n){ const s = ['th','st','nd','rd'], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }
export function dateText(y, f, per, dt){
  if (dt) return dt.charAt(0).toUpperCase() + dt.slice(1);    // as the listing words it: "Late 14th century"
  if (f === 'area') return 'probably ' + (per || y);
  if (f === 'century') return `${ordinal(Math.floor(y / 100) + 1)} century`;
  return (f === 'approx' ? 'c. ' : '') + y;
}
export const PRECISION = { exact: 'exact year', approx: 'approximate', century: 'only the century is known', area: 'estimate for the area' };
