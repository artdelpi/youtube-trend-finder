from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_trend_finder import (  # noqa: E402
    analyze_caption_opening,
    analyze_presentation_channel,
    classify_title,
    load_profile,
    presentation_options_for_trend,
)


class PresentationReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = load_profile("possumdotmov").data

    def test_title_mechanics_are_abstract_not_channel_specific(self) -> None:
        self.assertIn(
            "danger_collection",
            classify_title("Most Disturbing Cases in a Fictional Community"),
        )
        self.assertIn(
            "familiar_work_lens",
            classify_title("The Cartoon Episode About Consumerism"),
        )
        self.assertIn(
            "quantified_stakes", classify_title("Escape 100 Guards, Win $5,000")
        )
        self.assertIn(
            "answerable_mystery", classify_title("Why Did The Machine Stop?")
        )

    def test_caption_opening_is_bounded_and_related_to_title(self) -> None:
        result = analyze_caption_opening(
            "Most Disturbing Cases in a Fictional Community",
            "These are the most disturbing cases in a fictional community and the cases get darker. "
            + "padding " * 200,
            excerpt_words=40,
        )
        self.assertEqual(result["excerpt_word_count"], 40)
        self.assertIn("collection_promise", result["opening_signals"])
        self.assertIn("escalation_promise", result["opening_signals"])
        self.assertGreater(result["title_keyword_recall"], 0.7)

    def test_channel_analysis_relates_titles_to_small_caption_samples(self) -> None:
        channel = {
            "id": "reference",
            "url": "https://www.youtube.com/@reference/videos",
            "caption_video_ids": ["one", "missing"],
        }
        publications = [
            {
                "video_id": "one",
                "title": "Why Did The Machine Stop?",
                "view_count": 100,
            }
        ]
        result = analyze_presentation_channel(
            channel,
            publications,
            {"one": "Why did the machine stop For context the final switch failed"},
            excerpt_words=40,
        )
        self.assertEqual(result["caption_analysis"]["obtained"], 1)
        self.assertEqual(len(result["caption_analysis"]["failures"]), 1)
        self.assertFalse(result["caption_analysis"]["video_or_audio_downloaded"])

    def test_case_collection_beats_creator_biography_for_documented_cases(self) -> None:
        result = presentation_options_for_trend(
            {
                "theme": "Five documented abuse cases in a game mod community",
                "api_description": "victims, platform failure, and consequences",
            },
            self.profile,
        )
        self.assertEqual(
            result["options"][0]["presentation_archetype"],
            "escalating-case-ladder",
        )

    def test_identity_only_creator_lookup_is_explicitly_warned_and_penalized(self) -> None:
        result = presentation_options_for_trend(
            {"theme": "Who is behind the popular mod X"}, self.profile
        )
        self.assertTrue(result["warnings"])
        self.assertLess(result["options"][0]["fit_score"], 50)

    def test_creator_lookup_can_be_reframed_as_supported_comparison(self) -> None:
        result = presentation_options_for_trend(
            {
                "theme": "Creator attribution in monster compilations",
                "api_title": "Biggest Monsters Compared in 16 Minutes",
            },
            self.profile,
        )
        self.assertTrue(result["warnings"])
        self.assertIn(
            result["options"][0]["presentation_archetype"],
            {"quantified-stakes", "extreme-comparison"},
        )

    def test_kill_count_prefers_bounded_quantified_or_comparison_lanes(self) -> None:
        result = presentation_options_for_trend(
            {
                "theme": "Total kill count across 20 documented horror game characters",
                "api_description": "compare the deadliest character using confirmed deaths",
            },
            self.profile,
        )
        top = {item["presentation_archetype"] for item in result["options"][:2]}
        self.assertTrue(top & {"quantified-stakes", "extreme-comparison"})


if __name__ == "__main__":
    unittest.main()
