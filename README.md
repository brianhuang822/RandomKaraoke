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
