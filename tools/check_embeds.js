#!/usr/bin/env node
// Load a random sample of stored videos in YouTube's real embedded player and report
// whether they play. oEmbed (used by main.py) agreed with this on every video checked
// so far; run it occasionally to make sure that is still true.
//
//   npm install playwright && npx playwright install chromium   (once)
//   node tools/check_embeds.js            # 20 random karaoke links
//   node tools/check_embeds.js 40 lyricVideo
//
// Exits non-zero if any sampled video fails to play.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const repo = path.join(__dirname, '..');
const count = Number(process.argv[2] || 20);
const kind = process.argv[3] || 'karaoke';
// YouTube refuses embeds without a referrer ("Error 153"), so send the site's own.
const referer = 'https://brianhuang822.github.io/';

const years = JSON.parse(fs.readFileSync(path.join(repo, 'years.json')));
const ids = years.flatMap((y) => JSON.parse(fs.readFileSync(path.join(repo, `${y}.json`))))
  .map((e) => /v=([\w-]{11})/.exec(e[kind] || '')).filter(Boolean).map((m) => m[1]);
const sample = ids.sort(() => Math.random() - 0.5).slice(0, count);

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({ extraHTTPHeaders: { Referer: referer } });
  await context.route(/\.(png|jpg|webp|woff2?)(\?|$)|googlevideo|doubleclick|googlesyndication/, (r) => r.abort());
  const results = {};
  const queue = [...sample];
  await Promise.all(Array.from({ length: 4 }, async () => {
    while (queue.length) {
      const id = queue.shift();
      const page = await context.newPage();
      try {
        await page.goto(`https://www.youtube.com/embed/${id}`, { waitUntil: 'load', timeout: 30000 });
        await page.waitForFunction(() => /Watch on|unavailable|disabled|private|removed|Sign in/i
          .test(document.body.innerText), null, { timeout: 15000 }).catch(() => {});
        const text = await page.evaluate(() => document.body.innerText.replace(/\s+/g, ' '));
        results[id] = /disabled by the video owner/i.test(text) ? 'embedding disabled'
          : /private/i.test(text) ? 'private'
          : /unavailable|removed|terminated/i.test(text) ? 'unavailable'
          : /Sign in/i.test(text) ? 'sign-in required'
          : /Watch on/i.test(text) ? 'ok' : 'unknown';
      } catch (e) {
        results[id] = 'load error';
      }
      await page.close();
    }
  }));
  await browser.close();
  const failed = Object.entries(results).filter(([, r]) => r !== 'ok');
  console.log(`${sample.length - failed.length}/${sample.length} ${kind} videos play when embedded`);
  for (const [id, r] of failed) console.log(`  ${r}: https://www.youtube.com/watch?v=${id}`);
  process.exit(failed.length ? 1 : 0);
})();
