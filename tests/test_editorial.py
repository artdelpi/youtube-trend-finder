from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_trend_finder import (  # noqa: E402
    build_generation_prompt,
    draft_suggestion,
    load_profile,
    rank_trends_for_profile,
)


class EditorialRankingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = load_profile("possumdotmov").data
        self.trends = [
            {
                "codex_theme": "Hidden crime cases in a game fandom community",
                "collector_trend_score": 10,
            },
            {
                "codex_theme": "Quarterly stock-market earnings forecast",
                "collector_trend_score": 10,
            },
        ]

    def test_same_trends_rank_differently_for_different_profiles(self) -> None:
        finance = copy.deepcopy(self.profile)
        finance["id"] = "market-watch"
        finance["selection"]["topic_signals"] = ["stock", "earnings", "market"]
        finance["selection"]["audience_signals"] = ["investor", "forecast"]
        finance["selection"]["angle_signals"] = ["quarterly", "valuation"]
        finance["identity"]["excluded_topics"] = ["crime", "fandom", "horror"]

        horror_ranked = rank_trends_for_profile(self.trends, self.profile)
        finance_ranked = rank_trends_for_profile(self.trends, finance)
        self.assertEqual(horror_ranked[0]["codex_theme"], self.trends[0]["codex_theme"])
        self.assertEqual(finance_ranked[0]["codex_theme"], self.trends[1]["codex_theme"])

    def test_profile_reaches_generation_handoff(self) -> None:
        ranked = rank_trends_for_profile(self.trends[:1], self.profile)
        prompt = build_generation_prompt(self.profile, ranked, ["An existing title"])
        self.assertIn("profile 'possumdotmov'", prompt)
        self.assertIn('"id": "possumdotmov"', prompt)
        for field in ("title", "hook", "thesis", "structure", "profile_fit_score"):
            self.assertIn(field, prompt)

    def test_trend_score_keeps_six_volatile_components_separate(self) -> None:
        trend = {
            **self.trends[0],
            "codex_recency_score": 90,
            "codex_growth_score": 80,
            "codex_engagement_score": 70,
            "codex_cross_platform_score": 60,
            "codex_saturation_score": 50,
            "codex_lifespan_score": 40,
        }
        ranked = rank_trends_for_profile([trend], self.profile)[0]
        self.assertEqual(
            set(ranked["trend_score_components"]),
            {"recency", "growth", "engagement", "cross_platform", "saturation", "lifespan"},
        )
        self.assertEqual(ranked["trend_score"], 65)
        self.assertEqual(ranked["trend_signal_gaps"], [])

    def test_possumdotmov_shapes_title_angle_hook_and_structure(self) -> None:
        ranked = rank_trends_for_profile(self.trends[:1], self.profile)[0]
        suggestion = draft_suggestion(ranked, self.profile)
        self.assertEqual(suggestion["profile_id"], "possumdotmov")
        self.assertIn("Darkest Cases", suggestion["title"])
        self.assertIn("case-file", suggestion["angle"])
        self.assertIn("documented cases", suggestion["hook"])
        self.assertGreaterEqual(len(suggestion["structure"]), 7)
        self.assertIn("verified incident", suggestion["structure"][0])


if __name__ == "__main__":
    unittest.main()
