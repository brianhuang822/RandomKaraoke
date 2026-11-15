#!/usr/bin/env node
// Browser tests for the site (index.html + app.js), at phone width.
//
//   npm install playwright && npx playwright install chromium   (once)
//   node tests/browser_test.js           # page logic, YouTube blocked (works offline)
//   node tests/browser_test.js --online  # also the automatic fallback, against real YouTube
//
// Serves the repository itself on a local port, so it tests the working tree.
const fs = require('fs');
const http = require('http');
const path = require('path');
const { chromium } = require('playwright');

const repo = path.join(__dirname, '..');
const online = process.argv.includes('--online');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json' };
let failures = 0;

function check(name, ok, detail = '') {
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${name}${detail ? `  (${detail})` : ''}`);
  if (!ok) failures += 1;
}

function serve() {
  const server = http.createServer((req, res) => {
    const file = path.join(repo, decodeURIComponent(req.url.split('?')[0]).replace(/^\/$/, '/index.html'));
    if (!file.startsWith(repo) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.writeHead(404).end();
      return;
    }
    res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise((resolve) => server.listen(0, () => resolve(server)));
}

async function pageLogic(browser, base) {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.route(/youtube\.com/, (r) => r.abort());
  await page.goto(base);
  await page.waitForSelector('#songDisplay h3');
  const years = JSON.parse(fs.readFileSync(path.join(repo, 'years.json')));
  check('year bounds come from years.json',
    await page.getAttribute('#yearFrom', 'min') === String(years[0]) &&
    await page.getAttribute('#yearTo', 'max') === String(years[years.length - 1]));

  const pick = async (from, to, top, skip) => {
    await page.fill('#yearFrom', String(from)); await page.fill('#yearTo', String(to));
    await page.fill('#topX', String(top)); await page.fill('#skipY', String(skip));
    await page.click('#randomBtn');
    return page.innerText('#songDisplay');
  };
  const ranks = new Set();
  for (let i = 0; i < 40; i++) ranks.add(Number(/Rank (\d+)/.exec(await pick(years[0], years[years.length - 1], 20, 30))[1]));
  check('ranks stay inside the skip/top window', Math.min(...ranks) >= 31 && Math.max(...ranks) <= 50, [...ranks].sort((a, b) => a - b).join(','));
  check('2011 #7 is restored (missing from Billboard)', /F\*\*k You.*Rank 7 in 2011/s.test(await pick(2011, 2011, 1, 6)));
  check('2016 #87 is restored (missing from Billboard)', /All The Way Up.*Rank 87 in 2016/s.test(await pick(2016, 2016, 1, 86)));
  check('a reversed year range still works', /Rank \d+ in 202[45]/.test(await pick(2025, 2024, 5, 0)));
  check('an empty range shows a message', /No songs match/.test(await pick(2024, 2024, 5, 100)));
  await page.fill('#skipY', '0');
  await page.selectOption('#preset', 'hard');
  check('presets fill the fields', await page.inputValue('#topX') === '20' && await page.inputValue('#skipY') === '30');
  const noKaraoke = JSON.parse(fs.readFileSync(path.join(repo, '2006.json'))).find((e) => !e.karaoke);
  if (noKaraoke) {
    const text = await pick(2006, 2006, 1, noKaraoke.rank - 1);
    check('a song without karaoke shows its lyric video with a note', /No embeddable karaoke version/.test(text) &&
      (await page.getAttribute('iframe', 'src')).includes(/v=([\w-]{11})/.exec(noKaraoke.lyricVideo)[1]));
  }
  const iframe = await page.$('iframe');
  check('embeds send a referrer', iframe && await iframe.getAttribute('referrerpolicy') === 'strict-origin-when-cross-origin');
  check('no page errors', errors.length === 0, errors.join('; '));
  await page.close();
}

async function runtimeFallback(browser, base) {
  // Real videos: one that plays, one whose owner disabled embedding, one that was deleted.
  const OK = 'dQw4w9WgXcQ'; const NO_EMBED = 'OndurWrYr1Y'; const GONE = 'ToOQd-i7z_Q';
  const watch = (id) => id && `https://youtube.com/watch?v=${id}`;
  const cases = [
    ['karaoke blocked -> lyric video', { karaoke: NO_EMBED, lyricVideo: OK }, OK, /won't play on this site, so here is the lyric video/],
    ['both blocked -> message and link', { karaoke: NO_EMBED, lyricVideo: GONE }, null, /videos won't play on this site/],
    ['karaoke missing -> lyric video', { karaoke: null, lyricVideo: OK }, OK, /No embeddable karaoke version/],
    ['plays normally', { karaoke: OK, lyricVideo: GONE }, OK, null],
  ];
  for (const [name, links, expectId, expectNote] of cases) {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.route('**/years.json', (r) => r.fulfill({ json: [2006] }));
    await page.route('**/2006.json', (r) => r.fulfill({ json: [{
      rank: 1, songTitle: 'Test', title: 'Test Song', artist: 'Tester',
      karaoke: watch(links.karaoke), lyricVideo: watch(links.lyricVideo),
    }] }));
    await page.goto(base);
    await page.waitForSelector('#songDisplay h3');
    await page.waitForTimeout(12000); // let the player report errors and the page react
    const src = await page.getAttribute('iframe', 'src').catch(() => null);
    const note = await page.textContent('.note').catch(() => null);
    const idOk = expectId ? (src || '').includes(expectId) : src === null;
    const noteOk = expectNote ? expectNote.test(note || '') : note === null;
    check(`runtime fallback: ${name}`, idOk && noteOk, `iframe=${src && src.slice(30, 41)} note=${note}`);
    await context.close();
  }
}

(async () => {
  const server = await serve();
  const base = `http://localhost:${server.address().port}/`;
  const browser = await chromium.launch();
  try {
    await pageLogic(browser, base);
    if (online) await runtimeFallback(browser, base);
  } finally {
    await browser.close();
    server.close();
  }
  console.log(failures ? `${failures} failed` : 'all passed');
  process.exit(failures ? 1 : 0);
})();
