# Random Karaoke: notes for agents

Static site (GitHub Pages, served from `main`) that picks a random Billboard Year-End Hot 100 song
and plays a YouTube lyric video (guessing mode) or karaoke video (singing mode).

## Files

- `index.html`, `app.js`, `style.css`: the site. No build step.
- `<year>.json`: one file per year, 100 songs in rank order:
  `{"rank", "songTitle", "title", "artist", "lyricVideo", "karaoke"}`. A link can be `null` when no
  embeddable video exists; the site then shows the song's other video with a note.
- `years.json`: list of available years. The site reads it; never hardcode years in `app.js`.
- `main.py`: builds and repairs the year files (Billboard chart + YouTube search). See `--help`.
- `tests/`: `test_scoring.py` and `test_failsafe.py` (offline, run in under a second), and
  `browser_test.js` for the site.
- `tools/`: `audit_links.py` (health/quality report), `compare_links.py` (review a run's changes),
  `check_embeds.js` (load sampled videos in the real embedded player).
- `.github/workflows/refresh-songs.yml`: monthly refresh. Runs the offline tests, then `main.py`,
  then commits to `main`.

## Updating song data

Never commit data you haven't reviewed. A full update:

```bash
pip install -r requirements.txt
python -m unittest discover tests     # must pass before any scraper run
python main.py                        # ~4 min: re-checks every link, re-searches only bad ones
python tools/compare_links.py         # read the old/new titles of every changed link
python tools/audit_links.py           # must report every link at oEmbed 200, ranks contiguous
```

`python main.py --repick` re-searches every song (~40 min) and switches only to clearly better
videos. Use it after changing the scoring rules, then review the changes as above.
`python main.py --check` reports problems without writing anything.

Browser checks need Playwright (`npm install playwright && npx playwright install chromium`):
`node tests/browser_test.js --online` and `node tools/check_embeds.js`.

## How main.py chooses videos

Each rule in `score()` exists because of a real wrong pick, and each has a regression test in
`tests/test_scoring.py`. When you change a rule, add a test for the case that motivated it, and
check that a deliberately broken rule makes some test fail.

- **Embeddable only.** The site plays videos in an iframe. Many uploads block that, including most
  big karaoke channels (Sing King, KaraFun, karaoke SESH, Sing2Piano). Embeddability is checked
  with YouTube's oEmbed endpoint: 200 plays, 401 embedding disabled, 403 private/removed,
  404 deleted. These codes were verified against the real player; `tools/check_embeds.js`
  re-checks that.
- **Right song.** The title must appear as a whole phrase ("I Ain't Coming Back" ≠ "She Ain't
  Coming Back") and a credited artist must appear in the title or channel ("Hello" by Adele ≠ by
  Lionel Richie). Dotted names and titles (T.I., E.T., H.O.L.Y.) also match in compact form. A number
  after the title is a different song ("Te Bote 2"), unless it starts an artist name ("No Lie -
  2 Chainz"), or Billboard merged versions with "Or" in the credit ("Beat Box 3 ft. DaBaby").
- **Right type, ranked first.** A lyric video always outranks a music video, and a karaoke track
  always outranks an instrumental, however popular the other is. A bare "karaoke" earns full credit
  only with track-style wording ("(Karaoke Version)", "- Karaoke", "[Karaoke]") or a
  karaoke/instrumental channel, because "Vinny Karaoke 'I'm a Flirt'" is a person singing.
- **Then quality:** the artist's own channel or VEVO, view count and verified channel (search
  results only), a length near the typical length among matches, and penalties for covers,
  remixes, loops, sped-up, one-part duets ("you sing as Rumi"), multi-key videos, "lyrics in
  description", and Taylor's Version re-recordings.
- **Stability.** A good stored link is kept without searching. A working link is replaced only by a
  better type of video, or by the same type scoring `MARGIN` higher. Popularity counts only when
  both videos have view data.
- **Fail closed.** If YouTube or Billboard can't be checked, a chart parses implausibly short, or a
  year would lose more than `MAX_LOST_LINKS` links, nothing is written for that year and the script
  exits non-zero (`tests/test_failsafe.py`).

## Facts learned the hard way

- `billboard.py` raises `ValueError` for an unpublished year-end chart. The year-end chart appears
  near the end of the year; `main.py` picks it up automatically on the next run.
- Billboard's year-end pages omit 2011 #7 ("F**k You (Forget You)") and 2016 #87 ("All The Way
  Up"). They are restored from Wikipedia via `MISSING_FROM_BILLBOARD` so position always equals
  rank.
- Billboard sometimes changes artist capitalization between fetches, so entries are matched to
  stored data on a normalized key, not exact strings.
- YouTube search sometimes returns nothing for one phrasing and plenty for another ("All The Way
  BigXthaPlug ... lyric video"), hence the fallback queries.
- From cloud and datacenter IPs, `yt-dlp` flat search and oEmbed work, but full video extraction
  hits "Sign in to confirm you're not a bot". Don't build on full extraction; view counts come
  from search results.
- YouTube rejects embeds that send no referrer ("Error 153"). The iframe sets
  `referrerpolicy="strict-origin-when-cross-origin"`.
- About 1 in 15 videos that pass oEmbed is still region-locked somewhere. The site uses the YouTube
  IFrame API to detect playback errors and fall back to the song's other video, then to a
  "Watch on YouTube" link.
- The repo is public, so GitHub Actions on standard runners (`ubuntu-latest`) costs no minutes.

## Known trade-offs

- About 30 mostly rap songs have no embeddable karaoke version, so their karaoke link is an
  instrumental. 2006 #85 and 2023 #88 have none, and the site falls back to the lyric video.
- An ambiguous bare "karaoke" on a personal channel ranks like an instrumental. That's right for
  people singing, slightly unfair to home-made lyric karaoke tracks.
- Billboard sometimes lists a remix's credits under the original title (2018 "Te Bote"). The
  "remix" junk filter can then reject the actual charting remix; the original is picked instead.
