#!/usr/bin/env python3
"""Build the <year>.json files for Random Karaoke.

Each file lists Billboard's Year-End Hot 100 for that year in rank order, with a
YouTube lyric video and a karaoke video for every song. Every link is checked to
be embeddable (the site plays videos in an iframe, and many uploads, most big
karaoke channels included, block that) and to actually match the song.

    python main.py                # add new years, fill gaps, replace broken or wrong links
    python main.py --check        # only report problems; change nothing
    python main.py --years 2024 2025
"""
import argparse
import concurrent.futures as cf
import datetime
import json
import os
import re
import sys
import threading
import time
import unicodedata
from dataclasses import dataclass, field, replace

import billboard
import requests
import yt_dlp

ROOT = os.path.dirname(os.path.abspath(__file__))
FIRST_YEAR = 2006
WATCH = "https://youtube.com/watch?v="
SEARCH_RESULTS = 10
GOOD = 8  # title + artist + keyword match: stop searching once a pick scores this
MARGIN = 2  # a working link is only swapped for one that scores at least this much higher
MIN_CHART_SIZE = 90  # fewer parsed songs means Billboard changed its page, not its chart
MAX_LOST_LINKS = 5   # refuse to write a year that would lose more working links than this

# Billboard's year-end pages silently omit a few songs. Restore them so a song's
# position in the file always equals its rank.
# Source: Wikipedia, "Billboard Year-End Hot 100 singles of <year>".
MISSING_FROM_BILLBOARD = {
    2011: {7: ("F**k You (Forget You)", "CeeLo Green")},
    2016: {87: ("All The Way Up", "Fat Joe & Remy Ma Featuring French Montana & Infared")},
}

# A bare "karaoke" in a title is as often someone singing ("Vinny Karaoke 'I'm a Flirt'")
# as a backing track. Full credit needs track-style wording ("(Karaoke Version)",
# "- Karaoke", "[Karaoke]", "... karaoke" at the end) or a karaoke/instrumental channel.
TRACK_KARAOKE = re.compile(r"(?:[(\[|:\-\u2013\u3010]|\bhd)\s*karaoke|karaoke\s*(?:version|instrumental|track|video|"
                           r"with\b|w/|con\b|lyrics|songs?\b|hd\b|\d|\+|[)\]|:/\-\u2013\u3010\u3011\u266a\u266c]|$)")
KARAOKE_CHANNEL = re.compile(r"kara|videoke|\bsing\b|sing2|instrumental|backing|minus ?one")

KINDS = {
    "lyricVideo": {
        "suffixes": ["lyric video", "lyrics"],
        "want": [(r"\blyric|\bletra", 4)],
        # "Morgan Wallen Style - ...", "(lyrics in description)": not a lyric video of this song
        "avoid": r"\b(karaoke|instrumental|backing track|style|in (?:the )?description)\b",
        "keyword_required": False,  # an official music video beats nothing for guessing
    },
    "karaoke": {
        "suffixes": ["karaoke", "karaoke version", "instrumental"],
        "want": [(r"\b(karaoke|videoke)\b", 4), (r"\b(instrumental|backing track|sing ?along|minus one)\b", 2)],
        "avoid": None,
        "keyword_required": True,  # a lyric video is not a karaoke track; the site falls back itself
    },
}
# Versions nobody wants for a sing-along. Matched only against the part of a video
# title that is not the song's own title or artist (think "Live Your Life").
JUNK = re.compile(r"\b(cover|covers|reaction|live|remix|sped up|slowed|reverb|nightcore|8d|1 hour|loop|"
                  r"tutorial|lesson|chords|mashup|parody|choreography|shorts|teaser|snippet|bass boosted|"
                  r"(?:pt|part) (?:2|3|ii|iii|two)|performs?|performing|performance|sings|singing)\b")
# Karaoke where you sing only one part of a duet: usable, but a full version is better.
ONE_PART = re.compile(r"\b(you sing|sing as|you as|part only|male part|female part|duet with you|without (?:male|female))\b")
# Several keys stitched into one video ("Lower Higher Female & Original Key"): awkward to sing along to.
MULTI_KEY = re.compile(r"\b(lower higher|higher lower|all keys|every key|\d+ keys)\b")
MINOR = re.compile(r"\b(part only|male part|female part|male key|female key|lower key|higher key|key of|"
                   r"acoustic|piano|guitar|taylors version)\b")  # Taylor's Version: a later re-recording
STOP = {"the", "a", "an", "and", "of", "ft", "feat", "featuring", "with", "x", "vs"}

class Unavailable(RuntimeError):
    """YouTube or Billboard could not be checked. Abort rather than guess."""


_local = threading.local()
_oembed_cache = {}
_oembed_lock = threading.Lock()


def norm(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = text.replace("&", " and ").replace("$", "s").replace("'", "")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def fold(text):
    """Lowercase and drop accents, keeping punctuation ("Karaoké♬ -" -> "karaoke♬ -")."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()


def tokens(text):
    words = norm(text).split()
    kept = [w for w in words if w not in STOP and (len(w) > 1 or w.isdigit())]
    return kept or words


def coverage(needle, haystack):
    return sum(w in haystack for w in needle) / len(needle) if needle else 0


def legacy_title(title, artist):
    # The display string the site has always used: title plus credited artists.
    artist = (artist.replace("Featuring", " ").replace("feat.", " ").replace(" and ", " ")
              .replace("&", " ").replace(" x ", " ").replace(" X ", " "))
    return " ".join(f"{title} {artist}".split())


@dataclass
class Song:
    rank: int
    title: str
    artist: str
    artists: list = field(init=False)
    core: list = field(init=False)

    def __post_init__(self):
        credits = re.sub(r"[()]", " ", self.artist)
        parts = re.split(r",\s*|\s+(?:Featuring|Feat\.?|With|Or|x|X|&|and|And)\s+", credits)
        self.artists = [p.strip() for p in parts if p.strip()]
        self.core = tokens(re.sub(r"\(.*?\)|\[.*?\]", " ", self.title)) or tokens(self.title)

    @property
    def song_title(self):
        return legacy_title(self.title, self.artist)

    @property
    def key(self):
        return norm(self.song_title)


@dataclass
class Fit:
    score: float
    artist: bool
    keyword: int
    clean: bool
    popularity: float = 0  # part of score from view count / verified channel (search results only)

    @property
    def base(self):
        return self.score - self.popularity

    def usable(self, kind):
        """Right kind of video; good enough to keep when nothing better can be found."""
        return self.clean and (self.keyword > 0 or not KINDS[kind]["keyword_required"])

    def acceptable(self, kind):
        """Good enough to pick from search results: also credits the right artist."""
        return self.artist and self.usable(kind)

    def good(self):
        return self.artist and self.clean and self.keyword >= 4 and self.score >= GOOD


def credits(artist, words):
    """Whether an artist's name appears among a video's title and channel words."""
    if coverage(tokens(artist), words) >= 0.5:
        return True
    compact = norm(artist).replace(" ", "")  # "T.I." is written "TI" too
    return len(compact) >= 2 and compact in words


def score(video, song, kind):
    """How well a video fits a song, or None when it is not even the right title."""
    title = video["title"]
    title_words = set(norm(title).split())
    compact_title = "".join(song.core)  # "E.T." and "H.O.L.Y." are often written "ET" and "HOLY"
    if coverage(song.core, title_words) < 0.75 and compact_title not in title_words:
        return None
    words = set(norm(f"{title} {video.get('channel') or ''}").split())
    artist_ok = any(credits(a, words) for a in song.artists)

    rest = f" {norm(title)} "
    for name in [song.title, " ".join(song.core)] + song.artists:
        if norm(name):
            rest = rest.replace(f" {norm(name)} ", " ")

    spec = KINDS[kind]
    keyword = max([w for rx, w in spec["want"] if re.search(rx, rest)], default=0)
    if kind == "karaoke" and keyword == 4 and not (TRACK_KARAOKE.search(fold(title))
                                                   or KARAOKE_CHANNEL.search(fold(video.get("channel") or ""))):
        keyword = 2  # probably someone singing, not a backing track
    avoided = bool(spec["avoid"] and re.search(spec["avoid"], rest))
    junk = bool(JUNK.search(rest))
    s = (4 if artist_ok else 0) + keyword
    if avoided:
        s -= 6
    if junk:
        s -= 5
    if MINOR.search(rest):
        s -= 1
    if ONE_PART.search(rest):
        s -= 3
    if MULTI_KEY.search(f"{rest} {norm(video.get('channel') or '')}"):
        s -= 3
    # The whole title, small words included, should appear as one phrase: "I Ain't Coming
    # Back" must not match "She Ain't Coming Back".
    phrase = norm(re.sub(r"\(.*?\)|\[.*?\]", " ", song.title)) or norm(song.title)
    # A number right after the title is a sequel or numbered remix ("Te Bote 2"), not this
    # song, unless it starts an artist's name ("No Lie - 2 Chainz"). When Billboard merged
    # versions into one entry ("SpotemGottem Featuring Pooh Shiesty Or DaBaby"), a numbered
    # version featuring one of those artists is part of the entry ("Beat Box 3 ft. DaBaby").
    sequel = re.search(rf" {re.escape(phrase)} ((?:[2-9]|ii|iii|iv)\b(?! (?:members?|hours?|hrs?|mins?|minutes?|keys?)\b).*)",
                       f" {norm(title)} ")
    merged = song.artists[1:] if re.search(r"\bOr\b", song.artist) else []
    if (sequel and not any(norm(a) and sequel.group(1).startswith(norm(a)) for a in song.artists)
            and not any(credits(a, title_words) for a in merged)):
        junk, s = True, s - 5
    if f" {phrase} " in f" {norm(title)} " or compact_title in title_words:
        s += 1
    else:
        s -= 2
    channel = video.get("channel") or ""
    from_artist = any(len(c) >= 3 and c in norm(channel).replace(" ", "")
                      for c in (norm(a).replace(" ", "") for a in song.artists))
    if keyword and from_artist:
        s += 2  # the artist's own lyric video (or official karaoke video) is the best there is
    elif kind == "lyricVideo" and "official" in rest:
        s += 1
    duration = video.get("duration")
    odd_length = duration is not None and not 60 <= duration <= 600
    if odd_length:
        s -= 4
    # Search results (not oEmbed) carry popularity: widely watched uploads are usually
    # the clean, well-synced ones, and they are taken down less often.
    views = video.get("view_count")
    popularity = 0
    if views is not None:
        popularity += 2 if views >= 1_000_000 else 1 if views >= 100_000 else -2 if views < 1_000 else 0
    if video.get("channel_is_verified"):
        popularity += 1
    return Fit(s + popularity, artist_ok, keyword, not (avoided or junk or odd_length), popularity)


def http():
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
    return _local.session


def oembed(video_id):
    """Return {"id", "title", "channel"} if the video can be embedded on other sites, else None.

    YouTube's oEmbed endpoint answers 401 when the owner disabled embedding,
    403 for private or removed videos and 404 for deleted ones. Anything else
    (rate limiting, outages, network errors) raises Unavailable, so a run never
    mistakes "could not check" for "broken" and throws good links away."""
    with _oembed_lock:
        if video_id in _oembed_cache:
            return _oembed_cache[video_id]
    for attempt in range(5):
        try:
            r = http().get("https://www.youtube.com/oembed",
                           params={"url": WATCH + video_id, "format": "json"}, timeout=20)
            if r.ok:
                data = r.json()
                result = {"id": video_id, "title": data.get("title", ""), "channel": data.get("author_name", "")}
                break
            if r.status_code in (400, 401, 403, 404):
                result = None
                break
        except (requests.RequestException, ValueError):
            pass
        time.sleep(2 ** attempt)
    else:
        raise Unavailable(f"YouTube oEmbed is not answering (video {video_id})")
    with _oembed_lock:
        _oembed_cache[video_id] = result
    return result


def search(query):
    if not hasattr(_local, "ydl"):
        _local.ydl = yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True,
                                       "skip_download": True, "noprogress": True})
    for attempt in range(4):
        try:
            info = _local.ydl.extract_info(f"ytsearch{SEARCH_RESULTS}:{query}", download=False)
            return [{"id": e["id"], "title": e.get("title") or "", "duration": e.get("duration"),
                     "channel": e.get("channel") or e.get("uploader") or "",
                     "view_count": e.get("view_count"), "channel_is_verified": e.get("channel_is_verified")}
                    for e in info.get("entries") or []
                    if e.get("id") and "/shorts/" not in (e.get("url") or "")]
        except yt_dlp.utils.DownloadError:
            time.sleep(2 ** attempt)
    raise Unavailable(f"YouTube search is failing (query {query!r})")


def video_id(url):
    m = re.search(r"(?:v=|youtu\.be/|embed/)([\w-]{11})", url or "")
    return m.group(1) if m else None


def judge_existing(url, song, kind):
    """Return (Fit, metadata) for a stored link; metadata is None if the link is broken."""
    vid = video_id(url)
    meta = oembed(vid) if vid else None
    if not meta:
        return None, None
    return score(meta, song, kind), meta


def by_score(scored):
    """Rank (Fit, video) pairs, docking videos whose length is far from the typical one.

    Among uploads that match the song, most share the song's real length; one that
    is much longer or shorter is usually an extended mix, a clip or a compilation."""
    lengths = sorted(v["duration"] for _, v in scored.values() if v.get("duration"))
    typical = lengths[len(lengths) // 2] if len(lengths) >= 3 else None
    ranked = []
    for fit, video in scored.values():
        d = video.get("duration")
        if typical and d and abs(d - typical) > 0.35 * typical:
            fit = replace(fit, score=fit.score - 3)
        ranked.append((fit, video))
    # The right type of video first (a lyric video over a music video, a karaoke track
    # over an instrumental), however popular the other one is; then by score.
    return sorted(ranked, key=lambda v: (-v[0].keyword, -v[0].score))


def pick(song, kind, old_url, exclude=None, repick=False):
    """Return (url, Fit, note) for the best embeddable video of this kind.

    A stored link that is still a good fit is kept without searching, unless repick
    is set. Otherwise YouTube is searched and the best embeddable, acceptable result
    replaces the stored link if it scores at least MARGIN higher (so links don't
    churn on noise); a stored link that still plays is kept when nothing beats it."""
    old_fit, old_meta = judge_existing(old_url, song, kind) if old_url else (None, None)
    old_usable = (old_meta is not None and old_meta["id"] != exclude
                  and old_fit is not None and old_fit.usable(kind))
    if old_usable and old_fit.good() and not repick:
        return old_url, old_fit, "kept"

    main = song.artists[0] if song.artists else song.artist
    names = [song.song_title, f"{main} {song.title}", f"{song.title} {main}"]
    queries = [f"{name} {suffix}" for suffix in KINDS[kind]["suffixes"] for name in names]

    scored = {}
    best = None
    for query in queries:
        for video in search(" ".join(query.split())):
            if video["id"] not in scored and video["id"] != exclude:
                fit = score(video, song, kind)
                if fit is not None and fit.acceptable(kind):
                    scored[video["id"]] = (fit, video)
        best = None
        for fit, video in by_score(scored):
            if video["id"] == (old_meta or {}).get("id") or oembed(video["id"]):
                best = (fit, video)
                break
        if best and best[0].good():
            break

    seen_old = False
    if old_usable:
        # Judge the stored link on the same evidence as the new one when the search saw it.
        for fit, video in by_score(scored):
            if video["id"] == old_meta["id"]:
                old_fit, seen_old = fit, True
                break
    if best and best[1]["id"] == (old_meta or {}).get("id"):
        return old_url, old_fit, "kept"
    if best and not (old_usable and old_fit.acceptable(kind)):
        return WATCH + best[1]["id"], best[0], "new"
    if best and best[0].keyword != old_fit.keyword:
        if best[0].keyword > old_fit.keyword:  # a better type of video always wins
            return WATCH + best[1]["id"], best[0], "new"
    elif best:
        # Same type: switch only for a clear gain. Without view data for the stored
        # link, compare on everything but popularity.
        new_score = best[0].score if seen_old else best[0].base
        if new_score >= old_fit.score + MARGIN:
            return WATCH + best[1]["id"], best[0], "new"
    if old_usable:
        return old_url, old_fit, "kept"
    return None, None, "none"


def fetch_chart(year):
    """Return the year-end chart as a list of Songs, or None if it isn't published."""
    for attempt in range(4):
        try:
            chart = billboard.ChartData("hot-100-songs", year=str(year))
            break
        except (ValueError, billboard.BillboardNotFoundException):
            return None  # billboard.py raises ValueError on an empty, unpublished chart
        except (requests.RequestException, billboard.BillboardParseException):
            time.sleep(2 ** attempt)
    else:
        raise Unavailable(f"could not fetch the {year} chart from Billboard")
    songs = {entry.rank: (entry.title, entry.artist) for entry in chart}
    songs.update(MISSING_FROM_BILLBOARD.get(year, {}))
    if not songs:
        return None
    if len(songs) < MIN_CHART_SIZE:
        raise Unavailable(f"only {len(songs)} songs parsed for {year}; Billboard's page format may have changed")
    gaps = sorted(set(range(1, max(songs) + 1)) - set(songs))
    if gaps:
        print(f"  warning: {year} chart is missing ranks {gaps}; add them to MISSING_FROM_BILLBOARD")
    return [Song(rank, *songs[rank]) for rank in sorted(songs)]


def load(year):
    path = os.path.join(ROOT, f"{year}.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return {norm(e["songTitle"]): e for e in json.load(f)}


def resolve(song, old, check_only, repick=False):
    entry = {"rank": song.rank, "songTitle": song.song_title, "title": song.title, "artist": song.artist}
    notes = []
    exclude = None
    for kind in KINDS:
        old_url = old.get(kind)
        if check_only:
            fit, meta = judge_existing(old_url, song, kind) if old_url else (None, None)
            status = ("missing" if not old_url else "broken" if not meta else
                      "wrong song" if fit is None else "ok" if fit.good() else
                      "weak" if fit.usable(kind) else "poor")
            entry[kind] = old_url
            notes.append((kind, status, fit))
            continue
        url, fit, note = pick(song, kind, old_url, exclude, repick)
        entry[kind] = url
        exclude = video_id(url)
        if url is None:
            status = "missing"
        elif url != old_url:
            status = "added" if not old_url else "replaced"
        else:
            status = "ok" if fit.good() else "weak"
        notes.append((kind, status, fit))
    return entry, notes


def process_year(year, workers, check_only, repick=False):
    """Update one year's file. Returns False if the year could not be written safely."""
    songs = fetch_chart(year)
    old = load(year)
    if songs is None:
        if old:
            print(f"{year}: ERROR Billboard returned no chart, but this year was scraped before")
            return False
        print(f"{year}: no year-end chart published yet")
        return True
    with cf.ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(lambda s: resolve(s, old.get(s.key, {}), check_only, repick), songs))
    tally = {}
    for song, (entry, notes) in zip(songs, results):
        for kind, status, fit in notes:
            tally[(kind, status)] = tally.get((kind, status), 0) + 1
            if status != "ok":
                shown = "-" if fit is None else f"{fit.score:g}"
                print(f"  {year} #{song.rank:<3} {kind:<10} {status:<10} score={shown:<4} "
                      f"{song.title} - {song.artist}  {entry[kind] or ''}", flush=True)
    summary = ", ".join(f"{k} {st}: {n}" for (k, st), n in sorted(tally.items()))
    print(f"{year}: {len(songs)} songs. {summary}", flush=True)
    lost = sum(1 for song, (entry, _) in zip(songs, results)
               for kind in KINDS if old.get(song.key, {}).get(kind) and not entry[kind])
    if not check_only and lost > MAX_LOST_LINKS:
        print(f"{year}: ERROR this run would remove {lost} links; not writing. "
              f"Check the log, then raise MAX_LOST_LINKS if the removals are real.")
        return False
    if not check_only:
        with open(os.path.join(ROOT, f"{year}.json"), "w") as f:
            json.dump([entry for entry, _ in results], f, indent=2, ensure_ascii=False)
            f.write("\n")
    return True


def write_manifest():
    years = sorted(int(m.group(1)) for name in os.listdir(ROOT) if (m := re.fullmatch(r"(\d{4})\.json", name)))
    with open(os.path.join(ROOT, "years.json"), "w") as f:
        json.dump(years, f)
        f.write("\n")
    print(f"years.json: {years[0]}-{years[-1]} ({len(years)} years)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--years", type=int, nargs="+", help="only these years (default: every year with a chart)")
    parser.add_argument("--check", action="store_true", help="report problems without changing any file")
    parser.add_argument("--repick", action="store_true",
                        help="search again even for links that look fine, and switch to clearly better "
                             "videos (slow: searches every song)")
    parser.add_argument("--workers", type=int, default=4, help="songs processed in parallel (default 4)")
    args = parser.parse_args()

    failed = []
    for year in args.years or range(FIRST_YEAR, datetime.date.today().year + 1):
        try:
            if not process_year(year, args.workers, args.check, args.repick):
                failed.append(year)
        except Unavailable as e:
            # YouTube or Billboard is down or blocking us: stop, keeping every file as it was.
            print(f"{year}: ERROR {e}. Stopping; files for years not yet processed are unchanged.")
            failed.append(year)
            break
    if not args.check:
        write_manifest()
    if failed:
        print(f"Failed: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
