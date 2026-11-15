#!/usr/bin/env python3
"""Show every link a scraper run changed, old next to new, to review before committing.

Compares the working-tree song files with a git revision (default HEAD) and prints
each changed link's channel and title, so wrong songs, music videos posing as lyric
videos, or people singing posing as karaoke tracks are easy to spot.

    python tools/compare_links.py                # working tree vs HEAD, all years
    python tools/compare_links.py --rev main 2025
    python tools/compare_links.py --sample 40    # a random sample of the changes
"""
import argparse
import concurrent.futures as cf
import json
import os
import random
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import main as m  # noqa: E402


def at_rev(rev, year):
    out = subprocess.run(["git", "-C", REPO, "show", f"{rev}:{year}.json"], capture_output=True, text=True)
    return json.loads(out.stdout) if out.returncode == 0 else []


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("years", type=int, nargs="*")
    parser.add_argument("--rev", default="HEAD")
    parser.add_argument("--sample", type=int, help="show only this many random changes")
    args = parser.parse_args()
    years = args.years or json.load(open(os.path.join(REPO, "years.json")))

    changes = []
    for year in years:
        old = {e["rank"]: e for e in at_rev(args.rev, year)}
        for new in json.load(open(os.path.join(REPO, f"{year}.json"))):
            for kind in ("lyricVideo", "karaoke"):
                before = old.get(new["rank"], {}).get(kind)
                if before != new.get(kind):
                    changes.append((year, new, kind, before, new.get(kind)))
    print(f"{len(changes)} changed links "
          f"(lyric {sum(c[2] == 'lyricVideo' for c in changes)}, karaoke {sum(c[2] == 'karaoke' for c in changes)}, "
          f"removed {sum(1 for c in changes if not c[4])})")
    if args.sample and len(changes) > args.sample:
        changes = random.sample(changes, args.sample)

    ids = {m.video_id(u) for c in changes for u in c[3:] if u}
    with cf.ThreadPoolExecutor(8) as pool:
        meta = dict(zip(ids, pool.map(m.oembed, ids)))

    def show(url):
        v = meta.get(m.video_id(url)) if url else None
        return "-" if not v else f"{v['channel'][:22]:<22} {v['title'][:70]}"

    for year, entry, kind, before, after in sorted(changes, key=lambda c: (c[0], c[1]["rank"], c[2])):
        print(f"{year} #{entry['rank']:<3} {kind:<10} {entry['title']} - {entry['artist']}")
        print(f"    old {show(before)}")
        print(f"    new {show(after)}")


if __name__ == "__main__":
    main()
