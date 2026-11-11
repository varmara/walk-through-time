// Walk Through Time, city page: The year slider and Play.
import { $, MAX_YEAR, fmt } from './util.js';
import { S } from './state.js';

// ================= Year slider =================
// Piecewise scale: little was built before 1700, so the early centuries get a short stretch of the track.
export const SEG = [[0, 1100], [0.15, 1700], [0.45, 1850], [1, MAX_YEAR]];
export function s2y(t){ for (let i = 1; i < SEG.length; i++) if (t <= SEG[i][0]) {
  const [t0, y0] = SEG[i-1], [t1, y1] = SEG[i]; return Math.round(y0 + (t - t0) / (t1 - t0) * (y1 - y0)); } return MAX_YEAR; }
export function y2s(y){ for (let i = 1; i < SEG.length; i++) if (y <= SEG[i][1]) {
  const [t0, y0] = SEG[i-1], [t1, y1] = SEG[i]; return t0 + (y - y0) / (y1 - y0) * (t1 - t0); } return 1; }
export const yearIn = $('year');
export const curYear = () => s2y(+yearIn.value / 1000);
$('ticks').innerHTML = [1100, 1700, 1850, 1950, MAX_YEAR].map(y => `<span style="left:${(y2s(y) * 100).toFixed(1)}%">${y}</span>`).join('');
export function updateYear(){
  const Y = curYear();
  $('yearOut').textContent = +yearIn.value === 0 ? 'by ' + Y : Y;
  if (!S.map || !S.map.getLayer('b')) return;
  const f = ['any', ['all', ['has', 'y'], ['<=', ['get', 'y'], Y]]];
  if (S.showUnknown) f.push(['!', ['has', 'y']]);
  S.map.setFilter('b', f);
  // in the Map sheet, how many have a date: "2% have a date and 34% an estimate for their area"
  const pct = n => Math.round(n / S.stats.total * 100) + '%';
  $('dated').textContent = `Of ${fmt(S.stats.total)} buildings, ${pct(S.stats.known)} have a date`
    + (S.stats.estimated ? ` and ${pct(S.stats.estimated)} an estimate for their area.` : '.');
}
yearIn.addEventListener('input', updateYear);

// Play: the next year is drawn only once the map has finished drawing the last one, so the slider never runs
// ahead of the buildings. A slow phone takes bigger steps instead of falling behind; the whole run lasts ~25 s.
export const PLAY_MS = 25000;
export function stopPlay(){ S.playing = null; $('play').textContent = '▶'; }
$('play').onclick = () => {
  if (S.playing) return stopPlay();
  if (+yearIn.value >= 1000) yearIn.value = 0;
  $('play').textContent = '❚❚';
  const run = S.playing = {};
  let last = performance.now();
  const step = () => {
    if (S.playing !== run) return;
    const now = performance.now(), dt = Math.min(now - last, 1500); last = now;
    yearIn.value = Math.min(1000, +yearIn.value + Math.max(1, Math.round(dt / PLAY_MS * 1000)));
    updateYear();
    if (+yearIn.value >= 1000) return stopPlay();
    let done = false;
    const next = () => { if (!done) { done = true; setTimeout(step, 40); } };
    S.map.once('idle', next);
    setTimeout(next, 1500);   // never wait for ever (tiles still loading, tab in background)
  };
  step();
};
yearIn.addEventListener('pointerdown', () => S.playing && stopPlay());
