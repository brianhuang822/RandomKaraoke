# Random Karaoke
Link: https://brianhuang822.github.io/RandomKaraoke/

Saw on a tiktok page where people are doing blind koraoke challenge. This helps randomize song based on billboard. You can also do lyric video for guessing songs as well as we just normal karaoke as well!

## Updating the song data

Each `<year>.json` holds Billboard's Year-End Hot 100 for that year, with a YouTube lyric video and karaoke video per song. `years.json` lists the available years and is what the site loads.

```bash
pip install -r requirements.txt
python main.py           # add any newly published year, fill gaps, replace broken or wrong links
python main.py --check   # report broken or mismatched links without changing anything
python main.py --years 2026
```

The script only picks videos that YouTube allows to be embedded on other sites (many karaoke channels block this) and whose title matches the song and artist. Links that still work are kept, so re-running it is cheap. Billboard publishes each year-end chart near the end of the year; once it is out, run the script to add that year, and the site picks it up from `years.json` automatically.

If YouTube or Billboard can't be reached, or a year would lose more than a few working links, the script stops without writing that year and exits with an error, so a bad run never damages the data.

### Automatic monthly refresh

`.github/workflows/refresh-songs.yml` runs `main.py` on the 2nd of every month and commits any changes, so dead videos get replaced and a new year appears once Billboard publishes it. Run it on demand from the repository's **Actions** tab ("Refresh song data" → "Run workflow"). A failed run changes nothing and GitHub emails you. GitHub pauses scheduled workflows in public repositories after 60 days without activity; if that happens, re-enable it on the Actions tab.
