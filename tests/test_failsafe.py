"""main.py must never damage the data when YouTube or Billboard misbehave.

Runs process_year() against a scratch copy of 2025.json with Billboard and YouTube
faked, and checks the file is left byte-for-byte unchanged. Offline.

    python -m unittest discover tests
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import main as m  # noqa: E402

YEAR = 2025


class FakeEntry:
    def __init__(self, rank, title, artist):
        self.rank, self.title, self.artist = rank, title, artist


def chart_from_file(n=None):
    with open(os.path.join(REPO, f"{YEAR}.json")) as f:
        entries = [FakeEntry(e["rank"], e["title"], e["artist"]) for e in json.load(f)]
    return lambda *a, **k: entries[:n] if n else entries


class DeadSession:
    def get(self, *a, **k):
        raise requests.ConnectionError("network down")


class FailClosed(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        shutil.copy(os.path.join(REPO, f"{YEAR}.json"), self.dir)
        self.path = os.path.join(self.dir, f"{YEAR}.json")
        with open(self.path, "rb") as f:
            self.before = f.read()
        m._oembed_cache.clear()
        self.patches = [mock.patch.object(m, "ROOT", self.dir),
                        mock.patch.object(m.time, "sleep", lambda s: None),
                        mock.patch.object(m.billboard, "ChartData", chart_from_file())]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.dir)

    def assertUnchanged(self):
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), self.before, "the year file was modified")

    def test_youtube_unreachable(self):
        with mock.patch.object(m, "http", lambda: DeadSession()):
            with self.assertRaises(m.Unavailable):
                m.process_year(YEAR, 4, False)
        self.assertUnchanged()

    def test_search_blocked(self):
        def blocked(query):
            raise m.Unavailable("search blocked")
        with mock.patch.object(m, "oembed", lambda vid: None), mock.patch.object(m, "search", blocked):
            with self.assertRaises(m.Unavailable):
                m.process_year(YEAR, 4, False)
        self.assertUnchanged()

    def test_mass_link_loss_is_refused(self):
        # Every stored link reported broken and nothing found: looks like an outage, not reality.
        with mock.patch.object(m, "oembed", lambda vid: None), mock.patch.object(m, "search", lambda q: []):
            self.assertFalse(m.process_year(YEAR, 4, False))
        self.assertUnchanged()

    def test_truncated_billboard_chart(self):
        with mock.patch.object(m.billboard, "ChartData", chart_from_file(50)):
            with self.assertRaises(m.Unavailable):
                m.process_year(YEAR, 4, False)
        self.assertUnchanged()

    def test_known_year_missing_from_billboard(self):
        def gone(*a, **k):
            raise ValueError("min() iterable argument is empty")  # what billboard.py raises for an empty page
        with mock.patch.object(m.billboard, "ChartData", gone):
            self.assertFalse(m.process_year(YEAR, 4, False))
        self.assertUnchanged()


if __name__ == "__main__":
    unittest.main()
