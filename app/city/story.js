// Walk Through Time, city page: one story card, the same wherever a story is told: in a thread's strip of cards, on
// a building's card, in a thread's contents. Its number (in a thread) in its chapter's colour; its title and a way to
// share it; its date and place; its words, plain, with their footnotes numbered; what it is related to, one line
// for each kind (people, places, events, threads); and its sources, listed under it.
// Links live in Related only: a [[link]] in a note's words is shown as words (it still makes the graph's line and
// the Related entry).
import { CITY_ID, esc } from './util.js';
import { S } from './state.js';
import { isB, isThread, parseRef, refOf } from './data.js';

// ================= Colours: a thread's chapters take the era washes in turn, oldest first =================
export function chapterColour(j, m){
  if (!m || m < 2) return 'var(--hl)';
  return `var(--era-${1 + Math.round((j - 1) * 8 / (m - 1))})`;
}

// ================= Footnotes: numbered on one card; each card has its own list =================
// cite(source) -> its number as a link to the list; html() -> the list, under the story
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const readDate = d => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d || ''); return m ? `${+m[3]} ${MONTHS[m[2] - 1]} ${m[1]}` : d; };
let cardSeq = 0;
export function footnotes(){
  const id = 'c' + (++cardSeq) + '-', list = [], at = new Map();
  const key = s => s.url || s.title;
  const cite = s => {
    if (!s || !(s.url || s.title)) return '';
    let n = at.get(key(s));
    if (!n) { list.push(s); n = list.length; at.set(key(s), n); }
    return `<sup class="fn"><a href="#" data-fn="${id}${n}" aria-label="Source ${n}">${n}</a></sup>`;
  };
  const one = s => (s.title && s.kind && s.title !== s.kind ? esc(s.kind) + ': ' : '')
    + (s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title || s.kind)}</a>` : esc(s.title || s.kind))
    + (s.read ? ` <span class="muted">(read ${esc(readDate(s.read))})</span>` : '') + (s.note ? ` <span class="muted">${esc(s.note)}</span>` : '');
  const html = () => list.length ? `<div class="ssrc"><p class="slbl">Sources</p><ol>${list.map((s, i) => `<li id="fn${id}${i + 1}">${one(s)}</li>`).join('')}</ol></div>` : '';
  return { cite, html };
}
const J = v => { try { return typeof v === 'string' ? JSON.parse(v) : v; } catch { return null; } };
const kinded = s => s && { ...s, kind: s.kind || 'Wikipedia' };

// ================= Related: what a story ties to, from what the notes say =================
// every name the People layer or the people's notes know, longest first (to find them in a story's words)
let NAMES = null;
function peopleNames(){
  if (NAMES) return NAMES;
  const ns = new Set(Object.keys(S.data.people || {}));
  for (const L of S.layers.filter(L => L.kind === 'people'))
    for (const g of L.groups) if (g.key !== 'people-events') for (const it of g.items || []) ns.add(it[0]);
  return (NAMES = [...ns].sort((a, b) => b.length - a.length));
}
// the threads (theme threads, not places) each story and person is in: their names to the threads' ids
let THREADS = null;
export function threadsOf(name){
  if (!THREADS) {
    THREADS = new Map();
    for (const L of S.layers) if (isThread(L) && L.section === 'Threads')
      for (const g of L.groups) for (const it of g.items || []) {
        const nm = typeof it[0] === 'number' ? it[1] : it[0];
        if (!THREADS.has(nm)) THREADS.set(nm, new Set());
        THREADS.get(nm).add(L.id);
      }
  }
  return [...(THREADS.get(name) || [])];
}
// a place's name in Related: its own name, else its address (the build's place names), else what the map calls it
function placeName(r){
  const n = (S.data.placeNames || {})[String(r)];
  if (n && (n[0] || n[1])) return n[0] || n[1];
  if (isB(r)) return S.features[r]?.properties.name || 'A building';
  return refOf(r)?.properties?.name || 'A place';
}
// people: the notes it links to who are people, and the people its words name in full; places: its own (unless
// shown as its title already), then the places of the stories it links to; events: those stories; threads: the
// theme threads it is in (not the one being read)
export function relatedOf(s, refs, opts = {}){
  const text = String(s.text || ''), names = peopleNames(), known = new Set(names);
  const words = new Map((J(s.weblinks) || []).filter(([, u]) => String(u).startsWith('note:')).map(([w, u]) => [u.slice(5), w]));
  const people = [];
  const add = n => { if (n && known.has(n) && !people.some(p => p[0] === n) && n !== opts.self) people.push([n, words.get(n) || n]); };
  (J(s.links) || []).forEach(add);
  if (s.who) add(s.who);
  for (const n of names) if (n.includes(' ') && text.includes(n)) add(n);
  const see = (J(s.see) || []).filter(([, r]) => r && r !== 'who');
  const seeWho = (J(s.see) || []).filter(([, r]) => r === 'who').map(([n]) => n);
  seeWho.forEach(add);
  const places = [];
  const addPlace = r => { const k = String(r); if (!places.some(p => String(p) === k)) places.push(r); };
  (refs || []).forEach(r => { if (placeName(r) !== opts.title) addPlace(r); });
  see.forEach(([, r]) => addPlace(typeof r === 'number' ? r : parseRef(String(r))));
  const threads = threadsOf(s.nm || opts.title).filter(id => id !== opts.thread);
  return { people, places, events: see, threads };
}
export function relatedHtml(rel){
  const line = (k, xs) => xs.length ? `<p><span class="rk">${k}:</span> ${xs.join(' · ')}</p>` : '';
  const html = line('People', rel.people.map(([n, w]) => `<a href="#" data-who="${esc(n)}">${esc(w)}</a>`))
    + line('Places', rel.places.map(r => `<a href="#" data-ref="${esc(String(r))}">${esc(placeName(r))}</a>`))
    + line('Events', rel.events.map(([n, r]) => `<a href="#" data-ref="${esc(String(r))}">${esc(n)}</a>`))
    + line('Threads', rel.threads.map(id => S.layers.find(L => L.id === id)).filter(Boolean)
      .map(L => `<a href="#" data-thread="${esc(L.id)}">${esc(L.title)}</a>`));
  return html ? `<div class="srel"><p class="slbl">Related</p>${html}</div>` : '';
}

// ================= The card =================
// o: { n (its number in a thread), colour, chapter (a label above it), title, meta, s (the story: text, source,
// sources, place, cites, whenSrc), who (a person's opening line: { text, url, title, life }), rel, share (a link),
// extra (html: buttons under it), N (footnotes, else its own) }
export function storyCard(o){
  const N = o.N || footnotes(), s = o.s || {};
  const cites = J(s.cites) || {};
  const paras = String(s.text || '').split(/\n\n+/).filter(Boolean);
  const inText = new Set([...String(s.text || '').matchAll(/\[\^([\w-]+)\]/g)].map(m => cites[m[1]]?.url).filter(Boolean));
  const ws = J(s.whenSrc);
  const meta = o.meta ? `<p class="smeta">${esc(o.meta)}${ws ? N.cite(kinded(ws)) : ''}</p>` : '';
  const who = o.who && o.who.text ? `<p class="swho"><i>${esc(o.who.text)}</i>${N.cite({ kind: 'Wikipedia', title: o.who.title, url: o.who.url })}</p>` : '';
  const tail = [s.source, s.place, ...(J(s.sources) || [])].filter(x => x && (x.url || x.title) && !inText.has(x.url)).map(x => N.cite(kinded(x))).join('');
  const body = paras.map((t, i) => `<p class="stext">${esc(t).replace(/\[\^([\w-]+)\]/g, (all, k) => cites[k] ? N.cite(kinded(cites[k])) : '')}${i === paras.length - 1 ? tail : ''}</p>`).join('')
    || (tail ? `<p class="stext muted">Source${tail}</p>` : '');
  const here = s.here ? `<p class="shere">${esc(s.here)}</p>` : '';
  const num = o.n ? `<span class="snum" style="background:${o.colour || 'var(--hl)'}">${o.n}</span>` : '';
  const share = o.share ? `<button class="sshare" data-share="${esc(o.share)}" data-title="${esc(o.title)}" aria-label="Share this story" title="Share"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4l6 6-6 6"/><path d="M20 10h-8a8 8 0 0 0-8 8"/></svg></button>` : '';
  return `${o.chapter ? `<p class="schap" style="color:${o.colour || 'var(--muted)'}">${esc(o.chapter)}</p>` : ''}
    <div class="shead2">${num}<h3 class="stitle">${esc(o.title || '')}</h3>${share}</div>${meta}${who}${body}${here}
    ${o.rel ? relatedHtml(o.rel) : ''}${o.N ? '' : N.html()}${o.extra || ''}`;
}
// a share link for a story in a thread (?layer=…&story=…), else its place's
export function storyLink(thread, name){
  const site = new URL('../', location.href).href;
  return `${site}${CITY_ID}/?layer=${encodeURIComponent(thread)}&story=${encodeURIComponent(name)}`;
}
export async function shareStory(url, title){
  title = title + ' · Walk Through Time';
  if (navigator.share) { try { await navigator.share({ title, url }); } catch (e) { /* closed */ } return; }
  try { await navigator.clipboard.writeText(url); } catch (e) { prompt('Copy this link', url); }
}

// ================= A line to scale: dated things as dots on a line, years at its ends and at the chosen one =================
// pts: [{ y, colour, label }], sorted
export function timeLine(pts, cur){
  pts = pts.filter(p => Number.isFinite(p.y));
  if (pts.length < 2) return '';
  const a = pts[0].y, b = pts[pts.length - 1].y; if (a === b) return '';
  const x = y => `calc(8px + (100% - 16px) * ${((y - a) / (b - a)).toFixed(4)})`;
  const dots = pts.map((p, i) => `<span class="tdot${i === cur ? ' on' : ''}" style="left:${x(p.y)};background:${p.colour}" title="${esc(p.label || String(p.y))}"></span>`).join('');
  const yr = (y, k) => `<span class="tyr ${k}" style="left:${x(y)}">${y}</span>`;
  return `<div class="tline${cur != null ? ' cur' : ''}" aria-hidden="true">${dots}${yr(a, 'start')}${yr(b, 'end')}${cur != null ? yr(pts[cur].y, 'mid') : ''}</div>`;
}
// the first year a date or a text tells of ("c. 1450", "1831", "the 12th century")
export function yearOf(w){
  if (w === 'Roman times') return 43;
  const bc = /(\d{3,4})(?:–\d{3,4})? BC/.exec(w || '');
  if (bc) return -bc[1];
  const c = /(\d{1,2})(?:st|nd|rd|th) century/i.exec(w || '');
  if (c) return (+c[1] - 1) * 100;
  const m = /\b(1[0-9]{3}|20[0-9]{2}|[5-9][0-9]{2})\b/.exec(w || '');
  return m ? +m[1] : NaN;
}
