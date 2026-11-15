"""Offline regression tests for how main.py judges and picks YouTube videos.

Every case here is a real mistake the scraper made, or nearly made, while it was
being built. If you change a rule in main.py, run these first:

    python -m unittest discover tests

No network access is needed: search and oEmbed are replaced with fakes.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as m  # noqa: E402

Song = m.Song


def fit(title, song, kind, channel="", duration=200, **extra):
    return m.score({"title": title, "channel": channel, "duration": duration, **extra}, song, kind)


def acceptable(title, song, kind, **kw):
    f = fit(title, song, kind, **kw)
    return f is not None and f.acceptable(kind)


class RightSong(unittest.TestCase):
    def test_same_title_by_another_artist_is_rejected(self):
        adele = Song(1, "Hello", "Adele")
        self.assertFalse(acceptable("Hello - Lionel Richie (Karaoke)", adele, "karaoke"))
        self.assertTrue(acceptable("Adele - Hello (Karaoke Version)", adele, "karaoke"))

    def test_small_words_in_the_title_matter(self):
        # "I" is too short to be a search token, but "She Ain't Coming Back" is another song.
        song = Song(72, "I Ain't Coming Back", "Morgan Wallen Featuring Post Malone")
        self.assertFalse(acceptable("Morgan Wallen Style - She Ain't Coming Back (Official Lyric Video)",
                                    song, "lyricVideo"))
        self.assertTrue(acceptable("Morgan Wallen ft. Post Malone- I ain't coming back- lyrics video",
                                   song, "lyricVideo"))

    def test_near_miss_title_by_same_artist_loses_clearly(self):
        song = Song(72, "I Ain't Coming Back", "Morgan Wallen Featuring Post Malone")
        right = fit("Morgan Wallen - I Ain't Coming Back (Lyrics)", song, "lyricVideo").score
        near_miss = fit("Morgan Wallen - She Ain't Coming Back (Lyrics)", song, "lyricVideo").score
        self.assertGreater(right - near_miss, m.MARGIN)  # so the near miss can never replace it

    def test_dotted_and_symbol_titles_match(self):
        cases = [
            ("E.T.", "Katy Perry Featuring Kanye West", "Katy Perry - E.T. ft. Kanye West (Lyrics)"),
            ("E.T.", "Katy Perry Featuring Kanye West", "Katy Perry - ET ft. Kanye West (Lyrics)"),
            ("S&M", "Rihanna", "Rihanna - S&M (Lyrics)"),
            ("U.O.E.N.O.", "Rocko Featuring Future & Rick Ross", "Rocko - UOENO ft. Future, Rick Ross (Lyrics)"),
            ("G.D.F.R.", "Flo Rida Featuring Sage The Gemini & Lookas", "Flo Rida - GDFR ft. Sage The Gemini (Lyrics)"),
            ("H.O.L.Y.", "Florida Georgia Line", "Florida Georgia Line - H.O.L.Y. (Lyric Video)"),
            ("X", "Nicky Jam x J Balvin", "Nicky Jam x J. Balvin - X (EQUIS) Letra / Lyrics"),
            ("Ca$h Out", "Ca$h Out", "Ca$h Out - Cashin' Out (Lyrics)"),
            ("Turnin Me On", "Keri Hilson Featuring Lil Wayne", "Keri Hilson - Turnin' Me On ft. Lil Wayne (Lyrics)"),
        ]
        for title, artist, video in cases:
            with self.subTest(title=title, video=video):
                self.assertTrue(acceptable(video, Song(1, title, artist), "lyricVideo"))

    def test_dotted_artist_names_match(self):
        self.assertTrue(fit("T.I. - What You Know Lyrics", Song(47, "What You Know", "T.I."), "lyricVideo").artist)
        self.assertTrue(fit("TI - What You Know (Karaoke)", Song(47, "What You Know", "T.I."), "karaoke").artist)

    def test_artist_credits_are_split(self):
        self.assertEqual(Song(49, "I'm A Flirt", "R. Kelly Or Bow Wow (Featuring T.I. & T-Pain)").artists,
                         ["R. Kelly", "Bow Wow", "T.I.", "T-Pain"])
        self.assertEqual(Song(1, "x", "Lil Nas X").artists, ["Lil Nas X"])

    def test_words_from_the_song_title_are_not_junk(self):
        # "Live" and "Does" are junk words only outside the song's own title.
        self.assertTrue(fit("T.I. ft. Rihanna - Live Your Life (Lyrics)",
                            Song(1, "Live Your Life", "T.I. Featuring Rihanna"), "lyricVideo").good())
        self.assertTrue(fit("Ylvis - The Fox Lyrics (What Does The Fox Say?) [Official Lyrics video HD]",
                            Song(73, "The Fox", "Ylvis"), "lyricVideo").good())

    def test_numbered_sequel_is_another_song(self):
        te_bote = Song(81, "Te Bote", "Casper Magico, Nio Garcia, Darell, Nicky Jam, Ozuna & Bad Bunny")
        self.assertFalse(acceptable("Te Bote 2 - KARAOKE con LETRA Casper Magico, Nio Garcia, JLo, Wisin",
                                    te_bote, "karaoke", channel="Karaoke Pro"))
        self.assertTrue(acceptable("Casper Magico, Nio Garcia, Darell, Nicky Jam, Ozuna & Bad Bunny - Te Bote (Karaoke)",
                                   te_bote, "karaoke", channel="KaraKing Karaoke"))
        self.assertTrue(acceptable("Ed Sheeran - 2step (Lyrics)", Song(1, "2step", "Ed Sheeran"), "lyricVideo"))
        # Billboard merged numbered versions into one entry: those featuring a listed artist count.
        beat_box = Song(44, "Beat Box", "SpotemGottem Featuring Pooh Shiesty Or DaBaby")
        self.assertTrue(acceptable("SPOTEMGOTTEM ft. DaBaby - Beat Box 3 (Official Lyric Video)", beat_box, "lyricVideo"))
        self.assertFalse(acceptable("SPOTEMGOTTEM ft. NLE Choppa - Beat Box 4 (First Day Out) [Official Lyric Video]",
                                    beat_box, "lyricVideo"))
        # Counts like "8 Members Ver." are not sequels.
        self.assertTrue(fit('BTS (방탄소년단) "Butter" 8 Members Ver. (Karaoke)', Song(11, "Butter", "BTS"), "karaoke").clean)
        # ...and a number that starts the artist's name is not a sequel.
        self.assertTrue(acceptable("No Lie - 2 Chainz ft. Drake (Lyrics)", Song(54, "No Lie", "2 Chainz Featuring Drake"),
                                   "lyricVideo"))
        self.assertTrue(acceptable("She Got It - 2 Pistols ft. T-Pain & Tay Dizm (Lyrics)",
                                   Song(100, "She Got It", "2 Pistols Featuring T-Pain & Tay Dizm"), "lyricVideo"))

    def test_part_two_is_another_song(self):
        self.assertFalse(acceptable("PARTYNEXTDOOR & Drake - SOMEBODY LOVES ME PT. 2 (Instrumental)",
                                    Song(85, "Somebody Loves Me", "PARTYNEXTDOOR & Drake"), "karaoke"))
        self.assertTrue(acceptable("Kendrick Lamar - Somebody Pt. 2 (Karaoke)",
                                   Song(1, "Somebody Pt. 2", "Kendrick Lamar"), "karaoke"))


class RightKindOfVideo(unittest.TestCase):
    song = Song(1, "Lose Control", "Teddy Swims")

    def test_lyric_video_is_not_karaoke_and_vice_versa(self):
        self.assertFalse(acceptable("Teddy Swims - Lose Control (Lyric Video)", self.song, "karaoke"))
        self.assertFalse(acceptable("Teddy Swims - Lose Control (Karaoke Version)", self.song, "lyricVideo"))

    def test_covers_loops_and_performances_are_rejected(self):
        for title in ("Lose Control - Teddy Swims cover by Jane (lyrics)",
                      "Teddy Swims - Lose Control (sped up) lyrics",
                      "Teddy Swims - Lose Control 1 hour loop lyrics"):
            with self.subTest(title=title):
                self.assertFalse(acceptable(title, self.song, "lyricVideo"))
        self.assertFalse(acceptable("Tanisha performs Let It Go - Keyshia Cole karaoke",
                                    Song(65, "Let It Go", "Keyshia Cole"), "karaoke"))

    def test_lyrics_only_in_the_description_is_not_a_lyric_video(self):
        lollipop = Song(4, "Lollipop", "Lil Wayne Featuring Static Major")
        self.assertFalse(acceptable("Lil Wayne - Lollipop (dirty with lyrics in description)", lollipop, "lyricVideo"))
        self.assertTrue(acceptable("Lil Wayne - Lollipop ft. Static Major (Official Lyric Video)", lollipop, "lyricVideo"))

    def test_re_recording_ranks_below_the_original(self):
        style = Song(29, "Style", "Taylor Swift")
        self.assertGreater(fit("Style - Taylor Swift (Karaoke Version)", style, "karaoke").score,
                           fit("Style (Taylor's Version) [Karaoke Version] - Taylor Swift", style, "karaoke").score)

    def test_backing_tracks_get_full_karaoke_credit(self):
        cases = [
            (Song(1, "Roxanne", "Arizona Zervas"), "Karaoke♬ ROXANNE - Arizona Zervas 【No Guide Melody】 Instrumental", "EdKara"),
            (Song(1, "Rompe", "Daddy Yankee"), "Daddy Yankee - Rompe KARAOKE con LETRA", "Karaoke Pro"),
            (Song(1, "Love Nwantiti (Ah Ah Ah)", "CKay"), "Elgrande Toto ft Ckay - Love Nwantiti | karaoké", "Kara Oke"),
            (Song(1, "Espresso", "Sabrina Carpenter"), "Sabrina Carpenter - Espresso (Karaoke Version)", "PARTY TYME KARAOKE"),
            (Song(1, "Girls Like You", "Maroon 5 Featuring Cardi B"), "Girls Like You feat. Cardi B - Maroon 5 Karaoke 【With Guide Melody】", "x"),
        ]
        for song, title, channel in cases:
            with self.subTest(title=title):
                self.assertEqual(fit(title, song, "karaoke", channel=channel).keyword, 4)

    def test_people_singing_karaoke_do_not(self):
        # A bare "karaoke" on a personal channel is usually someone singing, not a track.
        self.assertEqual(fit('Vinny Karaoke "I\'m a Flirt" R Kelly', Song(49, "I'm A Flirt", "R. Kelly"),
                             "karaoke", channel="Vincent Ellis White").keyword, 2)
        self.assertEqual(fit("krystal & april karaoke let it go by keisha cole", Song(65, "Let It Go", "Keyshia Cole"),
                             "karaoke", channel="krystal smith").keyword, 2)

    def test_full_version_beats_one_part_and_multi_key(self):
        free = Song(92, "Free", "Rumi, Jinu, EJAE & Andrew Choi")
        self.assertGreater(fit("Free - RUMI (EJAE) & JINU (Andrew Choi) | Karaoke Version", free, "karaoke").score,
                           fit("Free (Karaoke, you sing as Rumi) - KPop Demon Hunters", free, "karaoke").score)
        daisies = Song(60, "Daisies", "Justin Bieber")
        self.assertGreater(fit("Justin Bieber - Daisies - Karaoke Instrumental Studio Version", daisies, "karaoke",
                               channel="Karaokey").score,
                           fit("Justin Bieber - DAISIES Karaoke Instrumental Lower Higher Female & Original Key",
                               daisies, "karaoke", channel="Karaoke All Keys").score)


class Ranking(unittest.TestCase):
    def test_lyric_video_beats_popular_music_video(self):
        song = Song(48, "Whatchu Kno About Me", "GloRilla & Sexyy Red")
        music_video = fit("GloRilla - WHATCHU KNO ABOUT ME ft. Sexyy Red (Official Music Video)", song, "lyricVideo",
                          channel="GloRillaVEVO", view_count=20_000_000, channel_is_verified=True)
        fan_lyrics = fit("GloRilla - WHATCHU KNO ABOUT ME ft  Sexyy Red(Lyrics)", song, "lyricVideo",
                         channel="NeW GeN X", view_count=800)
        ranked = m.by_score({"mv": (music_video, {"id": "mv"}), "fan": (fan_lyrics, {"id": "fan"})})
        self.assertEqual(ranked[0][1]["id"], "fan")

    def test_artist_channel_lyric_video_beats_fan_upload(self):
        song = Song(10, "Gives You Hell", "The All-American Rejects")
        self.assertGreater(fit("The All-American Rejects - Gives You Hell (Lyric Video)", song, "lyricVideo",
                               channel="The All-American Rejects").score,
                           fit("The All-American Rejects - Gives You Hell (Lyrics)", song, "lyricVideo",
                               channel="Darling").score)
        taste = Song(19, "Taste", "Sabrina Carpenter")
        self.assertGreater(fit("Sabrina Carpenter - Taste (Official Lyric Video)", taste, "lyricVideo",
                               channel="SabrinaCarpenterVEVO").score,
                           fit("Sabrina Carpenter - Taste (Lyrics)", taste, "lyricVideo", channel="Fan").score)

    def test_odd_length_is_ranked_down(self):
        song = Song(1, "Espresso", "Sabrina Carpenter")
        scored = {str(i): (fit(f"Sabrina Carpenter - Espresso (Karaoke Version) {i}", song, "karaoke", duration=d),
                           {"id": str(i), "duration": d})
                  for i, d in enumerate((175, 178, 180, 182, 420))}
        self.assertEqual(m.by_score(scored)[-1][1]["duration"], 420)

    def test_popularity(self):
        song = Song(1, "Espresso", "Sabrina Carpenter")
        title = "Sabrina Carpenter - Espresso (Karaoke Version)"
        low = fit(title, song, "karaoke", view_count=500)
        high = fit(title, song, "karaoke", view_count=3_000_000, channel_is_verified=True)
        self.assertLess(low.score, high.score)
        self.assertEqual(low.base, high.base)


class PickDecisions(unittest.TestCase):
    """pick() with fake search and oEmbed: when a stored link is kept or replaced."""
    song = Song(1, "Espresso", "Sabrina Carpenter")

    def run_pick(self, stored_title, results, repick=True, kind="karaoke"):
        catalog = {"old00000000": {"id": "old00000000", "title": stored_title, "channel": "Old Channel"}}
        for r in results:
            catalog[r["id"]] = {"id": r["id"], "title": r["title"], "channel": r.get("channel", "")}
        with mock.patch.object(m, "search", lambda q: results), \
                mock.patch.object(m, "oembed", lambda vid: catalog.get(vid)):
            return m.pick(self.song, kind, m.WATCH + "old00000000", repick=repick)

    def result(self, vid, title, **extra):
        return {"id": vid, "title": title, "duration": 180, "channel": "", **extra}

    def test_good_link_is_kept_without_searching(self):
        with mock.patch.object(m, "search", side_effect=AssertionError("searched")), \
                mock.patch.object(m, "oembed", lambda vid: {"id": vid, "channel": "Zoom Karaoke",
                                                            "title": "Sabrina Carpenter - Espresso (Karaoke Version)"}):
            url, _, note = m.pick(self.song, "karaoke", m.WATCH + "old00000000")
        self.assertEqual(note, "kept")

    def test_small_gain_does_not_churn(self):
        url, _, note = self.run_pick("Sabrina Carpenter - Espresso (Karaoke Version)",
                                     [self.result("new00000000", "Sabrina Carpenter - Espresso (Karaoke)",
                                                  view_count=200_000)])
        self.assertEqual(note, "kept")  # popularity alone doesn't count when the stored link has no view data

    def test_better_type_always_wins(self):
        url, _, note = self.run_pick("Sabrina Carpenter - Espresso (Instrumental)",
                                     [self.result("new00000000", "Sabrina Carpenter - Espresso (Karaoke Version)",
                                                  view_count=500)])
        self.assertEqual((note, url), ("new", m.WATCH + "new00000000"))

    def test_worse_type_never_wins(self):
        url, _, note = self.run_pick("Sabrina Carpenter - Espresso (Karaoke Version)",
                                     [self.result("new00000000", "Sabrina Carpenter - Espresso (Instrumental)",
                                                  view_count=50_000_000, channel_is_verified=True)])
        self.assertEqual(note, "kept")

    def test_broken_link_is_replaced_and_hopeless_one_dropped(self):
        results = [self.result("new00000000", "Sabrina Carpenter - Espresso (Karaoke Version)")]
        with mock.patch.object(m, "search", lambda q: results), \
                mock.patch.object(m, "oembed", lambda vid: None if vid == "old00000000" else
                                  {"id": vid, "title": results[0]["title"], "channel": ""}):
            self.assertEqual(m.pick(self.song, "karaoke", m.WATCH + "old00000000")[2], "new")
        with mock.patch.object(m, "search", lambda q: []), mock.patch.object(m, "oembed", lambda vid: None):
            self.assertEqual(m.pick(self.song, "karaoke", m.WATCH + "old00000000")[0], None)


if __name__ == "__main__":
    unittest.main()
