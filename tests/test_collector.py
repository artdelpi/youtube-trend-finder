from __future__ import annotations

import datetime as dt
import unittest

import collector


class CollectorHelpersTest(unittest.TestCase):
    def test_slugify_falls_back_to_trend(self) -> None:
        self.assertEqual(collector.slugify("!!!"), "trend")

    def test_slugify_normalizes_topic(self) -> None:
        self.assertEqual(
            collector.slugify("Horror Channel: US Trends"),
            "horror-channel-us-trends",
        )

    def test_parse_duration_seconds(self) -> None:
        self.assertEqual(collector.parse_duration_seconds("PT1H2M3S"), 3723)
        self.assertEqual(collector.parse_duration_seconds("P1DT2S"), 86402)
        self.assertEqual(collector.parse_duration_seconds("not-a-duration"), 0)

    def test_iso_utc_uses_z_suffix(self) -> None:
        value = dt.datetime(2026, 8, 14, 12, 34, 56, tzinfo=dt.timezone.utc)
        self.assertEqual(collector.iso_utc(value), "2026-08-14T12:34:56Z")


if __name__ == "__main__":
    unittest.main()
