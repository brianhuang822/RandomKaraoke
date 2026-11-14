import time

import billboard
import json
import os
from youtube_search import YoutubeSearch


def find_video(names, suffixes, retries=3):
    # YouTube sometimes returns "no results" for one phrasing but not another, and the
    # scraper intermittently fails to parse a response, so retry and fall back through
    # every name/suffix combination. The first combination is the original query.
    queries = [" ".join(f"{name} {suffix}".split()) for suffix in suffixes for name in names]
    for query in queries:
        for _ in range(retries):
            try:
                videos = YoutubeSearch(query, max_results=1).videos
            except Exception as e:
                print(f"  search error for {query!r}: {e}")
                time.sleep(2)
                continue
            if videos:
                return "https://youtube.com/watch?v=" + videos[0]['id']
            break
    raise LookupError(f"no YouTube results for any of {queries}")


something_found = True
failures = 0
while something_found:
    try:
        something_found = False
        for year in range(2006, 2026)[::-1]:
            print(year)
            file_name = f"./{year}.json"
            chart_data = billboard.ChartData("hot-100-songs", year=str(year))

            start = 0
            song_parsed = []
            if os.path.exists(file_name):
                with open(f"{year}.json", "r+") as f:
                    song_parsed = json.load(f)
                    start = len(song_parsed)
            for i in range(start, len(chart_data)):
                something_found = True
                song = chart_data[i]
                print("parsing " + song.title)
                artist = (song.artist.replace("Featuring", " ").replace("feat.", " ")
                          .replace(" and ", " ").replace("&", " ")
                          .replace(" x ", " ").replace(" X ", " "))
                song_title = (song.title + " " + artist).replace("  ", " ")
                main_artist = song.artist.split(" Featuring ")[0]
                names = [song_title, artist + " " + song.title, song.title + " " + main_artist]
                results = find_video(names, ["lyric video", "lyrics"])
                results_karaoke = find_video(names, ["karaoke", "karaoke version"])
                song_parsed.append({"songTitle": song_title, "lyricVideo": results, "karaoke": results_karaoke})
                with open(f"{year}.json", "w+") as f1:
                    json.dump(song_parsed, f1, indent=2)
    except Exception as e:
        print(e)
        failures += 1
        if failures >= 10:
            raise SystemExit("giving up after 10 failed passes")
