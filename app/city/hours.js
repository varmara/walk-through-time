// Walk Through Time, city page: opening hours as OpenStreetMap writes them (opening_hours), read for a card:
// whether a place is open now (in Nottingham's time, wherever the phone is) and the hours in plain words.
//
// Reads the common forms: "24/7"; "Mo-Fr 09:00-17:00; Sa 10:00-16:00; Su off"; several times a day
// ("12:00-14:30,17:00-22:00"); past midnight ("18:00-02:00"); a rule with no days (every day). A later rule
// replaces an earlier one for its days, as in OpenStreetMap. Anything else (months, holidays only, sunrise, "by
// appointment") is shown as written, with no open-now line: a wrong "open" is worse than none.
const DAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
const NAMES = { Mo: 'Mon', Tu: 'Tue', We: 'Wed', Th: 'Thu', Fr: 'Fri', Sa: 'Sat', Su: 'Sun', PH: 'bank holidays' };
const TIME = /^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})\+?$/;
// rules: split at ; and at a comma that starts new days ("Tu-We 10:00-23:00, Th-Sa 10:00-01:00")
const rules = s => (s || '').replace(/(\d|off|closed),\s*(?=(?:Mo|Tu|We|Th|Fr|Sa|Su|PH)\b)/g, '$1;')
  .split(';').map(r => r.trim()).filter(Boolean);

// -> week: 7 lists (Monday first) of [from, to] in minutes, to > 1440 past midnight; or null if not understood
export function parseHours(s){
  s = (s || '').trim();
  if (!s) return null;
  if (s === '24/7') return DAYS.map(() => [[0, 1440]]);
  const week = DAYS.map(() => []);
  for (let rule of rules(s)) {
    rule = rule.trim().replace(/\s+open$/, '');
    if (!rule) continue;
    const m = rule.match(/^([A-Za-z,\- ]+?)\s+(.+)$/) || [null, '', rule];
    let daysPart = m[1].trim(), times = m[2].trim();
    if (!daysPart && /^[A-Za-z]/.test(times)) { daysPart = times; times = ''; }   // "Mo off" with nothing after
    let days = DAYS.map((_, i) => i);
    if (daysPart) {
      days = [];
      for (const part of daysPart.split(',').map(x => x.trim()).filter(Boolean)) {
        if (part === 'PH' || part === 'SH') continue;             // holidays: not known here, so left out
        const r = part.match(/^(Mo|Tu|We|Th|Fr|Sa|Su)(?:-(Mo|Tu|We|Th|Fr|Sa|Su))?$/);
        if (!r) return null;
        const a = DAYS.indexOf(r[1]), b = r[2] ? DAYS.indexOf(r[2]) : a;
        for (let d = a; ; d = (d + 1) % 7) { days.push(d); if (d === b) break; }
      }
      if (!days.length) continue;                                 // "PH off": nothing to say about ordinary days
    }
    let spans = [];
    if (/^(off|closed)$/i.test(times)) spans = [];
    else {
      for (const t of times.split(',').map(x => x.trim())) {
        const r = t.match(TIME);
        if (!r) return null;
        const from = +r[1] * 60 + +r[2];
        let to = +r[3] * 60 + +r[4];
        if (to <= from) to += 1440;
        spans.push([from, to]);
      }
    }
    for (const d of days) week[d] = spans;
  }
  return week;
}

// the day (0 = Monday) and minute it is now in Nottingham
function londonNow(now = new Date()){
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', weekday: 'short',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(now).map(p => [p.type, p.value]));
  const day = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].indexOf(parts.weekday);
  return [day, +parts.hour * 60 + +parts.minute];
}
const hhmm = m => `${String(Math.floor(m / 60) % 24).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;

// -> { open: bool, text: "Open now, until 23:00" | "Closed now, opens Tue 10:00" } or null
export function openNow(s, now){
  const week = parseHours(s);
  if (!week) return null;
  if (week.every(d => !d.length)) return { open: false, text: 'Closed' };
  const [d, m] = londonNow(now);
  const prev = week[(d + 6) % 7].find(([a, b]) => b > 1440 && m < b - 1440);
  const today = week[d].find(([a, b]) => m >= a && m < b);
  if (prev || today) {
    if (week.every(x => x.length === 1 && x[0][0] === 0 && x[0][1] >= 1440)) return { open: true, text: 'Open day and night' };
    return { open: true, text: `Open now, until ${hhmm(prev ? prev[1] - 1440 : today[1])}` };
  }
  for (let k = 0; k < 7; k++) {
    const day = (d + k) % 7;
    const next = week[day].filter(([a]) => k > 0 || a > m).sort((x, y) => x[0] - y[0])[0];
    if (next) return { open: false, text: `Closed now, opens ${k === 0 ? 'at' : k === 1 ? 'tomorrow at' : NAMES[DAYS[day]]} ${hhmm(next[0])}` };
  }
  return { open: false, text: 'Closed' };
}

// the hours in plain words, one rule a line: "Mon–Fri 09:00–17:00", "Sun closed"
export function hoursText(s){
  return rules(s).map(r => r
    .replace(/\b(Mo|Tu|We|Th|Fr|Sa|Su|PH)\b/g, d => NAMES[d])
    .replace(/(\w{3})-(\w{3})/g, '$1–$2')
    .replace(/(\d{2}:\d{2})-(\d{2}:\d{2})/g, '$1–$2')
    .replace(/\boff\b/g, 'closed').replace(/,(?=\S)/g, ', ')
    .replace(/^24\/7$/, 'Open day and night').replace(/^./, c => c.toUpperCase()));
}
