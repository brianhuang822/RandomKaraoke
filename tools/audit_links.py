#!/usr/bin/env python3
"""Independent health and quality report for every link in the song files.

Checks each link with YouTube's oEmbed endpoint (does it still play when embedded
on another site?) and reports how many links are the right kind of video. Use it
after a scraper run, before committing data.

    python tools/audit_links.py            # all years
    python tools/audit_links.py 2024 2025  # some years

oEmbed status meanings, verified against the real embedded player: 200 plays
(about 1 in 15 may still be region-locked), 401 embedding disabled by the owner,
403 private or removed, 404 deleted.
"""
import collections
import concurrent.futures as cf
import json
import os
import re
import sys

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import main as m  # noqa: E402

KINDS = ("lyricVideo", "karaoke")


def check(url):
    for _ in range(3):
        try:
            r = requests.get("https://www.youtube.com/oembed", params={"url": url, "format": "json"}, timeout=20)
            return url, r.status_code, (r.json() if r.ok else {})
        except requests.RequestException:
            pass
    return url, "error", {}


def official_lyric_video(entry, meta):
    channel = m.norm(meta.get("author_name", "")).replace(" ", "")
    artists = (m.norm(a).replace(" ", "") for a in m.Song(entry["rank"], entry["title"], entry["artist"]).artists)
    from_artist = channel.endswith("vevo") or any(len(a) >= 3 and a in channel for a in artists)
    return from_artist and re.search(r"lyric", meta.get("title", ""), re.I)


def main():
    years = [int(y) for y in sys.argv[1:]] or json.load(open(os.path.join(REPO, "years.json")))
    entries = [(y, e) for y in years for e in json.load(open(os.path.join(REPO, f"{y}.json")))]
    urls = sorted({e[k] for _, e in entries for k in KINDS if e.get(k)})
    with cf.ThreadPoolExecutor(8) as pool:
        result = {u: (code, meta) for u, code, meta in pool.map(check, urls)}

    print(f"years {years[0]}-{years[-1]}: {len(entries)} songs, {len(urls)} unique links")
    print("oEmbed status:", dict(collections.Counter(code for code, _ in result.values())))
    bad_ranks = [y for y in years if [e["rank"] for yy, e in entries if yy == y] !=
                 list(range(1, 1 + sum(1 for yy, _ in entries if yy == y)))]
    print("ranks contiguous from 1 in every year:", not bad_ranks, bad_ranks or "")

    meta = lambda e, k: result.get(e.get(k), (None, {}))[1]  # noqa: E731
    lyric = [(e, meta(e, "lyricVideo")) for _, e in entries if e.get("lyricVideo")]
    karaoke = [(e, meta(e, "karaoke")) for _, e in entries if e.get("karaoke")]
    print(f"lyric links:   {len(lyric)}/{len(entries)} present, "
          f"{sum(bool(re.search(r'lyric|letra', v.get('title', ''), re.I)) for _, v in lyric)} are lyric videos, "
          f"{sum(bool(official_lyric_video(e, v)) for e, v in lyric)} from the artist's own channel")
    print(f"karaoke links: {len(karaoke)}/{len(entries)} present, "
          f"{sum('karaoke' in m.fold(v.get('title', '')) for _, v in karaoke)} karaoke, "
          f"{sum('karaoke' not in m.fold(v.get('title', '')) for _, v in karaoke)} instrumental-only")
    print("songs using one video for both:", sum(1 for _, e in entries if e.get("lyricVideo") and e["lyricVideo"] == e.get("karaoke")))
    broken = [(y, e["rank"], k, e[k], result[e[k]][0]) for y, e in entries for k in KINDS
              if e.get(k) and result[e[k]][0] != 200]
    for row in broken:
        print("  broken:", *row)
    sys.exit(1 if broken or bad_ranks else 0)


if __name__ == "__main__":
    main()
