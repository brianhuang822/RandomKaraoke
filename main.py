import time

import billboard
import json
import os
from youtube_search import YoutubeSearch
something_found = True
while something_found:
    try:
        something_found = False
        for year in range(2006, 2024)[::-1]:
            print (year)
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
                song_title = (song.title + " " + song.artist.replace("Featuring", " ").replace("feat.", " ")
                              .replace(" and ", " ").replace("&"," ")
                              .replace(" x ", " ").replace(" X ", " ")).replace("  ", " ")
                results = "https://youtube.com/watch?v=" + YoutubeSearch(song_title + ' lyric video', max_results=1).videos[0]['id']
                results_karaoke =  "https://youtube.com/watch?v=" + YoutubeSearch(song_title + ' karaoke', max_results=1).videos[0]['id']
                song_parsed.append({"songTitle": song_title, "lyricVideo": results, "karaoke": results_karaoke})
                with open(f"{year}.json", "w+") as f1:
                    json.dump(song_parsed, f1, indent=2)
    except Exception as e:
        print (e)