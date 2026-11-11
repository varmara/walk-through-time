// The page works: opens the map and taps through it in a headless browser, failing on any script error or on
// anything that does not show what it should. The build runs it on the site it is about to publish.
//   node tests/page/smoke.cjs http://localhost:8642/      (the folder served must hold the site: app, data, …)
// Needs Playwright (npm i playwright; npx playwright install chromium).
const { chromium } = require('playwright');
const BASE = (process.argv[2] || 'http://localhost:8642/').replace(/\/?$/, '/');
const CITY = process.argv[3] || 'nottingham';
// per city: a building to open by link, its title, and a building with a plaque on it
const KNOWN = { nottingham: { osm: 'way/120036353', title: 'The Bell Inn', plaque: 'way/268513978' } };
const known = KNOWN[CITY];
const failures = [];
const check = (ok, what) => { console.log((ok ? 'ok   ' : 'FAIL ') + what); if (!ok) failures.push(what); };

(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  // the page's own failures, not other sites' (fonts, the OpenStreetMap base map)
  page.on('console', m => m.type() === 'error' && !/Failed to load resource|net::ERR_/.test(m.text()) && errors.push(m.text()));
  // (a request cut off because the test moved on is not a failure)
  page.on('requestfailed', r => r.url().startsWith(BASE) && !/ABORTED/.test(r.failure()?.errorText || '')
    && errors.push('could not load ' + r.url().slice(BASE.length) + ' (' + r.failure()?.errorText + ')'));
  page.on('response', r => r.url().startsWith(BASE) && r.status() >= 400 && !/\.pbf/.test(r.url()) && errors.push(`${r.status()} ${r.url().slice(BASE.length)}`));
  const text = async sel => ((await page.textContent(sel)) || '').replace(/\s+/g, ' ').trim();
  const open = async q => {
    await page.goto(`${BASE}${CITY}/${q}`, { waitUntil: 'load' });
    await page.waitForSelector('#loader.done', { timeout: 90000 });
    await page.waitForTimeout(2000);
  };

  await open('');
  check(/Of [\d,]+ buildings/.test(await page.evaluate(() => document.getElementById('dated').textContent)), 'the map loads and counts the buildings');
  await page.evaluate(() => { const y = document.getElementById('year'); y.value = 250; y.dispatchEvent(new Event('input')); });
  check(/^\d+$/.test(await text('#yearOut')) && (await text('#yearOut')) !== '2026', 'the year slider changes the year');

  await page.click('#bLayers');
  const boxes = await page.$$('input[data-g]');
  check(boxes.length > 10, `the Layers sheet lists the layers (${boxes.length})`);
  if (boxes.length) { await boxes[0].check(); await page.waitForTimeout(300); }
  check(/^1 on/.test(await text('#lSummary')), 'ticking a layer turns it on');
  const many = await page.$('.item .cnt');
  if (many) {
    await page.evaluate(el => el.closest('.item').click(), many);
    await page.waitForTimeout(2500);
    check(/^1 of \d+$/.test(await text('#pCount')), 'a person with several places opens the places strip');
  } else check(false, 'a layer lists a person or story with several places');

  await page.click('#bMap').catch(() => {});
  await open('');
  await page.click('#bMap');
  check((await page.$$('#legend div')).length >= 5, 'the Map sheet shows the legend of periods');

  if (known) {
    await open('?osm=' + known.osm);
    check((await text('#sTitle')) === known.title, `a link to a building opens its card (${known.title})`);
    check(/Built/.test(await text('#cFacts')), 'the card shows when it was built');
    await open('?osm=' + known.plaque);
    const plaque = await page.$('#cStories [data-ref]');
    check(!!plaque, 'a building with a plaque quotes it');
    if (plaque) {
      await plaque.click(); await page.waitForTimeout(1500);
      check(/On this building/.test(await text('#cStories')), 'the plaque card shows its building');
    }
  }

  if (known) {           // what was loaded stays on the phone (sw.js): the same building opens with no connection
    await open('?osm=' + known.osm);
    check(await page.evaluate(() => !!navigator.serviceWorker && !!navigator.serviceWorker.controller), 'the page keeps what it loads (service worker)');
    await page.context().setOffline(true);
    const quiet = errors.length;
    try {
      await open('?osm=' + known.osm);
      check((await text('#sTitle')) === known.title, 'a building already seen opens offline');
    } catch (e) { check(false, 'a building already seen opens offline (' + e.message.split('\n')[0] + ')'); }
    await page.context().setOffline(false);
    errors.length = quiet;    // offline, other files fail to load: expected
  }

  await open('?focus=a0');
  check(/Type/.test(await text('#cFacts')), 'a link to an area opens its card');

  await page.goto(`${BASE}${CITY}/graph.html`, { waitUntil: 'load' });
  await page.waitForTimeout(3000);
  check((await page.$$('svg circle, svg .node')).length > 10, 'the graph page draws its points');

  check(!errors.length, 'no errors' + (errors.length ? ': ' + [...new Set(errors)].slice(0, 5).join(' | ') : ''));
  await browser.close();
  if (failures.length) { console.log(`\n${failures.length} failed`); process.exit(1); }
})().catch(e => { console.error(e); process.exit(1); });
