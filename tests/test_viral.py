"""Viral-recycle lane: screening, outlier maths, study signals and the copy guard. Offline."""
from __future__ import annotations

import contextlib
import csv
import datetime as dt
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from youtube_trend_finder import viral  # noqa: E402

NOW = dt.datetime(2026, 9, 23, 12, tzinfo=dt.timezone.utc)


def ago(hours: float) -> str:
    return (NOW - dt.timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


class FormatScreenTests(unittest.TestCase):
    def screen(self, title, description="", duration=900, tags=""):
        return viral.classify_format({"api_title": title, "api_description": description,
                                      "api_duration_seconds": duration, "api_tags": tags})

    def test_commentary_family_is_eligible(self):
        for title in ["Marvel's Wolverine is Shockingly Bad (Review)",
                      "The Walten Files Theory That Changes Everything",
                      "Top 10 Most Disturbing Roblox Games",
                      "The Rise and Fall of a Horror Channel",
                      "I watched every Five Nights at Freddy's movie"]:
            with self.subTest(title=title):
                self.assertEqual(self.screen(title)["collector_format_screen"], "eligible")

    def test_original_work_and_promotion_are_rejected(self):
        for title, family in [("The Walten Files 5: Episode 5", "original-work"),
                              # 2026-09-23: a 395x "breakout" that was a free full-length film upload.
                              ("The Wrong Woman | Full Thriller Movie | Danica McKellar", "original-work"),
                              ("Wolverine | Official Trailer", "official-promo"),
                              ("Skibidi Song (Official Music Video)", "music"),
                              ("Blox Fruits Gameplay No Commentary", "gameplay")]:
            with self.subTest(title=title):
                result = self.screen(title)
                self.assertEqual(result["collector_format_screen"], "rejected")
                self.assertEqual(result["collector_format_class"], family)

    def test_commentary_about_a_trailer_stays_eligible(self):
        result = self.screen("Wolverine Trailer Breakdown and Every Hidden Detail")
        self.assertEqual(result["collector_format_screen"], "eligible")
        self.assertIn("about official-promo", result["collector_format_reason"])

    def test_original_title_with_commentary_only_in_description_needs_review(self):
        result = self.screen("Chris Hansen Confronts Him | FULL EXCLUSIVE INTERVIEW",
                             description="The drama everyone is reacting to")
        self.assertEqual(result["collector_format_screen"], "needs-review")

    def test_description_trailer_link_does_not_reject(self):
        result = self.screen("PlayStation Is Charging Users Different Prices",
                             description="Watch the trailer here: https://example.com")
        self.assertNotEqual(result["collector_format_screen"], "rejected")

    def test_shorts_and_unsignalled_rows_go_to_review(self):
        self.assertEqual(self.screen("Top 10 creepiest games", duration=45)["collector_format_screen"],
                         "needs-review")
        self.assertIn("short-form", self.screen("Top 10 creepiest games", duration=45)["collector_format_reason"])
        self.assertEqual(self.screen("Kitt Gaming plays with friends")["collector_format_screen"], "needs-review")


class OutlierTests(unittest.TestCase):
    def test_baseline_excludes_itself_young_uploads_and_other_form(self):
        uploads = [
            {"video_id": "self", "views": 9_000_000, "published_at": ago(200), "duration_seconds": 900},
            {"video_id": "young", "views": 1, "published_at": ago(10), "duration_seconds": 900},
            {"video_id": "short", "views": 5_000_000, "published_at": ago(300), "duration_seconds": 40},
            *[{"video_id": f"v{i}", "views": v, "published_at": ago(500 + i), "duration_seconds": 700}
              for i, v in enumerate([10_000, 20_000, 30_000])],
        ]
        baseline = viral.channel_baseline(uploads, exclude_video_id="self", now=NOW)
        self.assertEqual(baseline, {"collector_channel_sample": 3, "collector_channel_median_views": 20_000.0})
        shorts = viral.channel_baseline(uploads, exclude_video_id="self", long_form=False, now=NOW)
        self.assertEqual(shorts["collector_channel_median_views"], 5_000_000.0)

    def test_breakout_labels(self):
        self.assertEqual(viral.breakout_label(None), "unknown")
        self.assertEqual(viral.breakout_label(viral.BREAKOUT_RATIO), "breakout")
        self.assertEqual(viral.breakout_label(viral.STRONG_RATIO), "strong")
        self.assertEqual(viral.breakout_label(1.2), "channel-normal")

    def test_unmeasured_outlier_scores_zero_and_ratio_raises_score(self):
        base = dict(views=1_000_000, comments=4_000, age_hours=96)
        unmeasured = viral.viral_components(**base, outlier_ratio=None)
        self.assertEqual(unmeasured["outlier"], 0.0)
        low = viral.viral_score(viral.viral_components(**base, outlier_ratio=2))
        high = viral.viral_score(viral.viral_components(**base, outlier_ratio=40))
        self.assertLess(low, high)
        self.assertEqual(viral.viral_components(**base, outlier_ratio=40)["outlier"], 100.0)

    def test_outlier_metrics_uses_the_median(self):
        row = {"api_views": 500_000, "api_comments": 2_500, "collector_age_hours": 48}
        metrics = viral.outlier_metrics(row, {"collector_channel_sample": 20,
                                              "collector_channel_median_views": 25_000}, 100_000)
        self.assertEqual(metrics["collector_outlier_ratio"], 20.0)
        self.assertEqual(metrics["collector_breakout"], "breakout")
        self.assertEqual(metrics["collector_subscriber_ratio"], 5.0)
        self.assertEqual(json.loads(metrics["collector_viral_components"])["discussion"], 100.0)
        empty = viral.outlier_metrics(row, {"collector_channel_sample": 0,
                                            "collector_channel_median_views": 0.0}, None)
        self.assertEqual((empty["collector_outlier_ratio"], empty["collector_breakout"]), ("", "unknown"))


class FakeApi:
    def __init__(self, responses):
        self.responses = responses
        self.seen = []

    def __call__(self, endpoint, params, key):
        self.seen.append((endpoint, dict(params)))
        answer = self.responses[endpoint]
        answer = answer(params) if callable(answer) else answer
        if isinstance(answer, Exception):
            raise answer
        return answer


def http_error(code, body):
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(body.encode()))


class ApiTests(unittest.TestCase):
    def test_channel_uploads_carry_views_and_subscribers(self):
        api = FakeApi({
            "channels": {"items": [
                {"id": "c1", "statistics": {"subscriberCount": "1000"},
                 "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}},
                {"id": "c2", "statistics": {"hiddenSubscriberCount": True},
                 "contentDetails": {"relatedPlaylists": {"uploads": "UU2"}}}]},
            "playlistItems": lambda p: {"items": [{"contentDetails": {"videoId": p["playlistId"] + "-a"}}]},
            "videos": {"items": [
                {"id": "UU1-a", "statistics": {"viewCount": "700"}, "snippet": {"publishedAt": ago(400)},
                 "contentDetails": {"duration": "PT10M"}},
                {"id": "UU2-a", "statistics": {"viewCount": "90"}, "snippet": {"publishedAt": ago(400)},
                 "contentDetails": {"duration": "PT50S"}}]},
        })
        calls: list = []
        channels = viral.fetch_channel_uploads(["c1", "c2", "c1"], "k", calls, get=api)
        self.assertEqual(channels["c1"]["subscribers"], 1000)
        self.assertIsNone(channels["c2"]["subscribers"])
        self.assertEqual(channels["c1"]["recent"][0]["views"], 700)
        self.assertEqual(channels["c2"]["recent"][0]["duration_seconds"], 50)
        self.assertEqual(sum(c["quota_units"] for c in calls), 4)

    def test_comments_paginate_and_disabled_is_a_status(self):
        page = {"items": [{"snippet": {"totalReplyCount": 2, "topLevelComment": {
            "id": "Ugx1", "snippet": {"authorDisplayName": "@a", "textDisplay": "4:05 this part",
                                      "likeCount": 12, "publishedAt": ago(5)}}}}]}
        api = FakeApi({"commentThreads": lambda p: {**page, "nextPageToken": None if p.get("pageToken") else "t2"}})
        calls: list = []
        rows, status = viral.fetch_comments("vid", "k", calls, pages=3, get=api)
        self.assertEqual((status, len(rows), len(calls)), ("ok", 2, 2))
        self.assertEqual(rows[0]["permalink"], "https://www.youtube.com/watch?v=vid&lc=Ugx1")
        disabled = FakeApi({"commentThreads": http_error(403, '{"reason": "commentsDisabled"}')})
        rows, status = viral.fetch_comments("vid", "k", [], get=disabled)
        self.assertEqual((rows, status), ([], "comments-disabled"))
        with self.assertRaises(urllib.error.HTTPError):
            viral.fetch_comments("vid", "k", [], get=FakeApi({"commentThreads": http_error(403, "quotaExceeded")}))


VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.000 align:start position:0%

I<00:00:00.680><c> told</c><c> myself</c>

00:00:02.000 --> 00:00:04.000 align:start position:0%
I told myself
it didn't need to be a game&nbsp;

00:01:05.500 --> 00:01:08.000
it didn't need to be a game&nbsp;
its very nature as a thing to be interacted with
"""


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.segments = viral.parse_vtt(VTT)

    def test_vtt_drops_rolling_repeats_tags_and_entities(self):
        self.assertEqual([s["text"] for s in self.segments],
                         ["I told myself", "it didn't need to be a game",
                          "its very nature as a thing to be interacted with"])
        self.assertEqual(self.segments[-1]["start"], 65.5)
        self.assertIn("[1:05] its very nature", viral.transcript_text(self.segments))

    def test_timestamp_peaks_are_log_weighted_and_bounded_by_duration(self):
        comments = [{"comment_id": "a", "text": "1:05 and 1:05 again", "likes": 9},
                    {"comment_id": "b", "text": "1:10 lol", "likes": 0},
                    {"comment_id": "c", "text": "at 10:00:00 nope", "likes": 99},
                    {"comment_id": "d", "text": "2:40", "likes": 99999}]
        peaks = viral.timestamp_peaks(comments, duration=600)
        self.assertEqual(peaks[0]["start"], 150)
        first_minute = next(p for p in peaks if p["start"] == 60)
        self.assertEqual((first_minute["count"], first_minute["weight"]), (2, 3.0))
        self.assertNotIn(36000, [p["start"] for p in peaks])

    def test_heatmap_skips_the_opening_and_keeps_peaks_apart(self):
        curve = [{"start_time": t, "end_time": t + 5, "value": v} for t, v in
                 [(0, 1.0), (5, 0.2), (40, 0.3), (45, 0.9), (50, 0.8), (55, 0.85), (60, 0.2),
                  (90, 0.1), (95, 0.6), (100, 0.1), (400, 0.1)]]
        peaks = viral.heatmap_peaks(curve, min_gap=20)
        self.assertEqual([p["start"] for p in peaks], [45.0, 95.0])
        self.assertEqual(viral.heatmap_peaks(None), [])

    def test_quoted_lines_find_the_sentence_that_landed(self):
        comments = [{"comment_id": "q", "likes": 129, "text": "“it didn't need to be a game. Its very nature” perfect"},
                    {"comment_id": "n", "likes": 3, "text": "great video"}]
        hits = viral.quoted_lines(comments, self.segments)
        self.assertEqual([h["comment_id"] for h in hits], ["q"])
        self.assertEqual(hits[0]["at"], "0:02")

    def test_signals_sort_comments_into_piles(self):
        comments = [
            {"comment_id": "1", "likes": 50, "text": "Finally someone said it. New sub."},
            {"comment_id": "2", "likes": 5, "text": "Actually the studio said otherwise"},
            {"comment_id": "3", "likes": 20, "text": "You forgot the 2019 case, part 2?"},
            {"comment_id": "4", "likes": 0, "text": "I remember when this happened to me"},
        ]
        signals = viral.comment_signals(comments, self.segments, duration=120)
        piles = signals["piles"]
        self.assertEqual(piles["praise"]["count"], 1)
        self.assertEqual(piles["correction"]["count"], 1)
        self.assertEqual(piles["request"]["examples"][0]["comment_id"], "3")
        self.assertEqual(piles["question"]["count"], 1)
        self.assertEqual(piles["personal"]["count"], 1)
        self.assertEqual(piles["praise"]["share_of_likes"], 0.667)
        self.assertEqual(signals["top_comments"][0]["comment_id"], "1")


class OriginalityTests(unittest.TestCase):
    reference = "Marvel's Wolverine is Shockingly Bad (Review)"
    transcript = "[0:02] I told myself it didn't need to be a game its very nature as a thing to be interacted with"

    def test_reworded_reference_title_is_caught(self):
        self.assertGreater(viral.title_overlap("Wolverine Is Shockingly Bad", self.reference),
                           viral.TITLE_OVERLAP_MAX)
        row = {"title": "Insomniac Made a Movie and Called It Wolverine",
               "alternate_titles": json.dumps(["Marvel's Wolverine Is Shockingly Bad"])}
        errors = viral.originality_errors(row, self.reference)
        self.assertEqual(len(errors), 1)
        self.assertIn("shares", errors[0])

    def test_transcript_runs_are_caught_in_any_proposal_field(self):
        row = {"title": "Insomniac Made a Movie and Called It Wolverine", "alternate_titles": "[]",
               "thesis": "It didn't need to be a game: its very nature as a thing to be ignored"}
        errors = viral.originality_errors(row, self.reference, self.transcript)
        self.assertEqual(len(errors), 1)
        self.assertIn("thesis repeats", errors[0])
        clean = dict(row, thesis="The studio built a film and hid it behind a controller")
        self.assertEqual(viral.originality_errors(clean, self.reference, self.transcript), [])


def load_script(name):
    spec = importlib.util.spec_from_file_location(f"{name}_cli", ROOT / f"scripts/{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StudyCliTests(unittest.TestCase):
    def test_one_track_is_chosen_authored_first(self):
        study = load_script("viral_study")
        info = {"subtitles": {"en-GB": [{"ext": "json3", "url": "j"}, {"ext": "vtt", "url": "manual"}]},
                "automatic_captions": {"en": [{"ext": "vtt", "url": "asr"}], "de": [{"ext": "vtt", "url": "x"}]}}
        self.assertEqual(study.pick_track(info), ("manual:en-GB", "manual"))
        self.assertEqual(study.pick_track({"automatic_captions": info["automatic_captions"]}), ("asr:en", "asr"))
        self.assertEqual(study.pick_track({"automatic_captions": {"de": []}}), ("", ""))
        # The ASR `en` entry is the translation route that answered 429; `en-orig` goes first.
        asr = {"automatic_captions": {"en": [{"ext": "vtt", "url": "tlang"}],
                                      "en-orig": [{"ext": "vtt", "url": "orig"}]}}
        self.assertEqual(study.pick_tracks(asr), [("asr:en-orig", "orig"), ("asr:en", "tlang")])

    def test_video_ids_from_urls(self):
        study = load_script("viral_study")
        for value in ["ShelqOuE_PI", "https://www.youtube.com/watch?v=ShelqOuE_PI&t=4",
                      "https://youtu.be/ShelqOuE_PI", "https://www.youtube.com/shorts/ShelqOuE_PI"]:
            self.assertEqual(study.video_id_of(value), "ShelqOuE_PI")
        with self.assertRaises(ValueError):
            study.video_id_of("not a video")

    def test_copy_check_reads_every_string_of_a_brief(self):
        check = load_script("check_recycle_copy")
        with tempfile.TemporaryDirectory() as tmp:
            reference = Path(tmp) / "transcript.txt"
            reference.write_text("[12:51] it's just that it didn't need to be a game its very nature\n",
                                 encoding="utf-8")
            brief = Path(tmp) / "brief.json"
            brief.write_text(json.dumps({"chapters": [{"beats": [
                {"narration": "Our own sentence about the studio's contract."},
                {"narration": "It's just that it didn't need to be a game, honestly."}]}]}), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(check.main(["--reference", str(reference), "--text", str(brief)]), 1)
            self.assertIn("it didn't need to be a game", out.getvalue())
            brief.write_text(json.dumps({"narration": "Our own sentence about the contract."}), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(check.main(["--reference", str(reference), "--text", str(brief)]), 0)


class ScanCollectionTests(unittest.TestCase):
    def test_batches_merge_by_video_keeping_the_latest_views(self):
        scan = load_script("viral_scan")
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            for batch, views in (("30d", 100), ("7d", 900)):
                target = run / "_internal/youtube" / batch
                target.mkdir(parents=True)
                with (target / "x-api_videos.csv").open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=["api_video_id", "api_views"])
                    writer.writeheader()
                    writer.writerow({"api_video_id": "abc", "api_views": views})
            rows, batches = scan.read_collections(run)
        self.assertEqual(batches, ["30d", "7d"])
        self.assertEqual(rows["abc"]["api_views"], "900")
        self.assertEqual(rows["abc"]["collector_batches"], "30d|7d")


if __name__ == "__main__":
    unittest.main()
