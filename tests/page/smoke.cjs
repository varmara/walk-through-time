// The page works: opens the map and taps through it in a headless browser, failing on any script error or on
// anything that does not show what it should. The build runs it on the site it is about to publish.
//   node tests/page/smoke.cjs http://localhost:8642/      (the folder served must hold the site: app, data, …)
// Needs Playwright (npm i playwright; npx playwright install chromium).
const { chromium } = require('playwright');
const BASE = (process.argv[2] || 'http://localhost:8642/').replace(/\/?$/, '/');
const CITY = process.argv[3] || 'nottingham';
// per city: a building to open by link, its title, and a building with a plaque on it
const KNOWN = { nottingham: { osm: 'way/120036353', title: 'The Bell Inn', plaque: 'way/122280349' } };   // Newdigate House: an Open Plaques plaque (the council's are off)
const known = KNOWN[CITY];
const failures = [];
let step = 'opening';      // (an error is reported with the check before it, to say where it came from)
const check = (ok, what) => { console.log((ok ? 'ok   ' : 'FAIL ') + what); if (!ok) failures.push(what); step = what; };

(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [];
  // after the offline check, the map reports tiles it asked for while offline as failed fetches, sometimes many
  // seconds later (a minute and more on GitHub's machines): those are expected, so for a while after the connection
// is back they are not counted
  let backOnline = 0;
  const lateOffline = msg => /Failed to fetch/.test(msg) && backOnline && Date.now() - backOnline < 90000;
  page.on('pageerror', e => lateOffline(e.message) || errors.push(`${e.message} (after "${step}"${e.stack ? ': ' + e.stack.split('\n').slice(1, 3).map(s => s.trim()).join(' ') : ''})`));
  // the page's own failures, not other sites' (fonts, the OpenStreetMap base map)
  page.on('console', m => m.type() === 'error' && !/Failed to load resource|net::ERR_/.test(m.text()) && !lateOffline(m.text()) && errors.push(`${m.text()} (console, after "${step}")`));
  // (a request cut off because the test moved on is not a failure)
  page.on('requestfailed', r => r.url().startsWith(BASE) && !/ABORTED/.test(r.failure()?.errorText || '')
    && errors.push('could not load ' + r.url().slice(BASE.length) + ' (' + r.failure()?.errorText + ')'));
  page.on('response', r => r.url().startsWith(BASE) && r.status() >= 400 && !/\.pbf/.test(r.url()) && errors.push(`${r.status()} ${r.url().slice(BASE.length)}`));
  const text = async sel => ((await page.textContent(sel)) || '').replace(/\s+/g, ' ').trim();
  // a card's counter changes once the strip has settled on the next card, which can take longer than a fixed pause
  // when the map flies far between pins: wait for the change (up to 10 s), not a set time
  const counterAfter = async action => {
    const before = await text('#pCount');
    await action();
    await page.waitForFunction(b => (document.getElementById('pCount')?.textContent || '').replace(/\s+/g, ' ').trim() !== b,
      before, { timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(200);
  };
  const open = async q => {
    await page.goto(`${BASE}${CITY}/${q}`, { waitUntil: 'load' });
    await page.waitForSelector('#loader.done', { timeout: 90000 });
    await page.waitForTimeout(2000);
  };

  await open('');
  check(/Of [\d,]+ buildings/.test(await page.evaluate(() => document.getElementById('dated').textContent)), 'the map loads and counts the buildings');
  await page.evaluate(() => { const y = document.getElementById('year'); y.value = 250; y.dispatchEvent(new Event('input')); });
  check(/^\d+$/.test(await text('#yearOut')) && (await text('#yearOut')) !== '2026', 'the year slider changes the year');

  // the Layers sheet: what is not a story (heritage, nature, visit…), ticked to highlight
  await page.click('#bLayers');
  const boxes = await page.$$('input[data-g]');
  check(boxes.length > 10, `the Layers sheet lists the layers (${boxes.length})`);
  check(!(await page.$('#lSections .seclbl:text-is("Places"), #lSections .seclbl:text-is("Threads")')), 'places and themes are not in the Layers sheet');
  if (boxes.length) { await boxes[0].check(); await page.waitForTimeout(300); }
  check(/^1 on/.test(await text('#lSummary')), 'ticking a layer turns it on');
  await boxes[0].uncheck(); await page.waitForTimeout(200);

  // the Stories sheet: places folded under headings, threads and people, each opening numbered cards
  await page.click('#bStories'); await page.waitForTimeout(300);
  const fold = await page.$('#stSections details.area > summary');
  check(!!fold && !(await page.$eval('#stSections details.area', d => d.open)), 'the places fold under headings');
  if (fold) { await fold.click(); await page.waitForTimeout(200); }
  const place = await page.$('#stSections details.area[open] [data-set]');
  if (place) { await place.click(); await page.waitForTimeout(3000); }
  check(/^\d+ stor(y|ies)$/.test(await text('#pCount')), "a place's stories open on their opening card");
  await page.click('#pClose'); await page.waitForTimeout(300);
  await page.click('#bStories'); await page.waitForTimeout(300);
  const many = await page.$('#stSections .linfo .item .cnt');
  if (many) {
    await page.evaluate(el => el.closest('.item').click(), many);
    await page.waitForTimeout(2500);
    check(/^1 of \d+$/.test(await text('#pCount')), 'a person with several places opens the places strip');
    // a person's card: who they were and their places (the People layer's first person)
    const name = await page.evaluate(async () => {
      const { S } = await import(new URL('../app/city/state.js', location.href).href);
      const g = S.layers.find(L => L.kind === 'people')?.groups.find(g => g.items && g.items.length);
      if (!g) return null;
      (await import(new URL('../app/city/cards.js', location.href).href)).showPerson(g.items[0][0]);
      return g.items[0][0];
    });
    if (name) {
      await page.waitForTimeout(800);
      check((await text('#sTitle')) === name && (await page.$$('#personPlaces a')).length > 0, "a person's card lists their places");
      check(await page.evaluate(() => !document.getElementById('sShare').hidden), "a person's card can be shared");
      await open('?person=' + encodeURIComponent(name));
      check((await text('#sTitle')) === name, "a shared person's link opens their card");
    }
  } else check(false, 'the Stories sheet lists a person with several places');

  // a thread's stories as numbered cards, from the Stories sheet
  await open('');
  await page.click('#bStories'); await page.waitForTimeout(300);
  const areaHeads = await page.$$eval('#stSections details.area > summary', els => els.map(e => e.childNodes[0].textContent.trim()));
  check(areaHeads.length > 0 && new Set(areaHeads).size === areaHeads.length, 'each area has one heading in the Stories sheet');
  const thread = await page.$('#stSections .section:has(.seclbl:text-is("Themes")) [data-set]');
  check(!!thread, 'the Stories sheet has threads');
  if (thread) {
    await thread.click();
    await page.waitForTimeout(3000);
    const n = +(/^(\d+) stor/.exec(await text('#pCount')) || [])[1];
    // (a thread of several chapters has a card for each chapter too, unnumbered, before its stories)
    const intros = (await page.$$('#pCards .pintro')).length;
    check(n > 0 && intros > 0 && (await page.$$('#pCards .pcard')).length === n + intros, "a thread opens on its opening card, then a card for each story (and each chapter)");
    if (intros > 1) { await counterAfter(() => page.click('#pNext')); check(/^Chapter 1 of \d+$/.test(await text('#pCount')) && /^Chapter 1 of/.test(await text('#pCards .pintro.on')), 'a thread of several chapters opens its first chapter on a card of its own'); }
    for (let i = 0; i < intros && !/^1 of /.test(await text('#pCount')); i++) { await counterAfter(() => page.click('#pNext')); }
    check(await text('#pCount') === `1 of ${n}`, "the next card is its first story, numbered");
    // Contents: the thread's chapters and stories down a line; a chapter's heading opens its full text; a story
    // there goes back to its card
    await page.click('#pPage'); await page.waitForTimeout(500);
    check(await page.$eval('#placesbar', el => el.classList.contains('page')) && (await page.$$('#pCards .crow, #pCards .cstory')).length > 0, 'Contents lists the thread');
    const head = await page.$('#pCards .chead');
    if (head) { await head.click(); await page.waitForTimeout(800); check((await page.$$('#pCards .cstory')).length > 0, "a chapter's heading opens its full text"); }
    const k2 = await page.evaluate(async () => (await import(new URL('../app/city/state.js', location.href).href)).S.places.cards.findIndex(c => !c.intro && c.n === 2));
    const back = await page.$(`#pCards .crow[data-go="${k2}"], #pCards .cstory[data-i="${k2}"] [data-map]`);
    if (back) { await counterAfter(() => back.click()); }
    check(!(await page.$eval('#placesbar', el => el.classList.contains('page'))) && await text('#pCount') === `2 of ${n}`, '"Show on the map" goes back to its card');
  }
  // a link to a place opens its cards, not a tickbox
  await open('?layer=castle');
  check(/^\d+ stor(y|ies)$/.test(await text('#pCount')), "a link to a place opens its cards");

  await page.click('#bMap').catch(() => {});
  await open('');
  await page.click('#bMap');
  check((await page.$$('#legend [data-per]')).length >= 5, 'the Map sheet shows the legend of periods');

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
    backOnline = Date.now();
    // offline, other files fail to load: expected. The map reports some of those failures a moment later (tiles
    // asked for just before the connection came back), so wait for them before counting errors again
    await page.waitForTimeout(2500);
    errors.length = quiet;
  }

  await open('?focus=a0');
  check(/Type/.test(await text('#cFacts')), 'a link to an area opens its card');

  // the graph, over the map page (app/city/graph.js, in a shadow root: Playwright's locators reach into it)
  const g = page.locator('#graphHost');
  const graphPoints = () => page.evaluate(() => +(document.getElementById('graphHost')?.shadowRoot?.getElementById('graph')?.dataset.points || 0));
  const graphOpen = () => page.evaluate(() => { const h = document.getElementById('graphHost'); return !!h && !h.hidden; });
  const cam = () => page.evaluate(async () => { const { S } = await import(new URL('../app/city/state.js', location.href).href); const m = S.map; return [m.getCenter().lng.toFixed(5), m.getCenter().lat.toFixed(5), m.getZoom().toFixed(2)].join(); });
  await page.waitForTimeout(500);
  const before = await cam();
  await page.click('#bGraph');
  await g.locator('#graph').waitFor({ timeout: 15000 });
  for (let i = 0; i < 60 && !(await graphPoints()); i++) await page.waitForTimeout(250);
  check((await graphPoints()) > 10, 'the graph opens over the map and draws its points');
  check(/#graph$/.test(page.url()), 'the graph has its own address (#graph)');
  await g.locator('#graph').click({ position: { x: 5, y: 400 } });     // a tap on empty space: no errors
  await g.locator('#back').click();
  await page.waitForTimeout(500);
  check(!(await graphOpen()) && !/#graph/.test(page.url()), '"← Map" closes the graph');
  check((await cam()) === before, 'the map is where it was after the graph');
  await page.click('#bGraph'); await page.waitForTimeout(500);
  check(await graphOpen(), 'the graph opens again');
  await page.goBack(); await page.waitForTimeout(500);
  check(!(await graphOpen()), "the phone's Back closes the graph");
  // "Show on the map" from a found person: the map opens their places in the page, Back returns to the graph
  await page.click('#bGraph'); await page.waitForTimeout(500);
  const person = await page.evaluate(() => {
    const c = document.getElementById('graphHost').shadowRoot.getElementById('graph');
    return (c.inspect().nodes.find(n => !/^b\d|^p\d|^a\d|^t:/.test(n[0])) || [])[0];
  });
  if (person) {
    const label = await page.evaluate(id => fetch(`../data/${document.body.dataset.city}-graph.json`).then(r => r.json()).then(d => d.nodes.find(n => n.id === id).label), person);
    await g.locator('#find').fill(label.slice(0, 12)); await page.waitForTimeout(800);
    await g.locator('#go').click();
    await page.waitForTimeout(2500);
    check(!(await graphOpen()) && /focus=/.test(page.url()), '"Show on the map" opens the places on the map, in the page');
    check(await page.evaluate(() => !document.getElementById('placesbar').hidden || !document.getElementById('sheet').hidden), 'the places are shown');
    await page.goBack(); await page.waitForTimeout(800);
    check(await graphOpen(), 'Back from those places returns to the graph');
  }
  // the old address of the graph page sends links to the graph over the map
  await page.goto(`${BASE}${CITY}/graph.html`, { waitUntil: 'load' });
  await page.waitForURL(/#graph$/, { timeout: 10000 }).catch(() => {});
  for (let i = 0; i < 80 && !(await graphPoints()); i++) await page.waitForTimeout(250);
  check((await graphPoints()) > 10, 'an old graph.html link opens the graph over the map');

  check(!errors.length, 'no errors' + (errors.length ? ': ' + [...new Set(errors)].slice(0, 5).join(' | ') : ''));
  await browser.close();
  if (failures.length) { console.log(`\n${failures.length} failed`); process.exit(1); }
})().catch(e => { console.error(e); process.exit(1); });
