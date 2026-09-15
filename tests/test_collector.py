from __future__ import annotations

import datetime as dt
import unittest
import tempfile
from pathlib import Path
from unittest import mock

import collector


class CollectorHelpersTest(unittest.TestCase):
    def test_direct_batch_output_and_legacy_timestamp_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for timestamped in [True, False]:
                batch = root / str(timestamped)
                csv_path, json_path = collector.write_outputs(
                    'Topic', [], {}, batch, timestamped_output=timestamped)
                self.assertEqual(csv_path.parent.parent if timestamped else csv_path.parent, batch)
                self.assertEqual(json_path.parent, csv_path.parent)
            original = csv_path.read_bytes()
            with self.assertRaises(FileExistsError):
                collector.write_outputs('Topic', [], {}, batch, timestamped_output=False)
            self.assertEqual(csv_path.read_bytes(), original)

    def test_existing_batch_fails_before_api_access(self) -> None:
        from youtube_trend_finder import collector as implementation
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / 'topic-profile_context.json').write_text('{}', encoding='utf-8')
            with mock.patch.object(implementation, 'load_api_key') as key:
                with self.assertRaises(FileExistsError):
                    implementation.collect('Topic', ['topic'], 7, out_dir=temp,
                                           timestamped_output=False)
                key.assert_not_called()

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

    def test_quota_cost_matches_youtube_pricing(self) -> None:
        self.assertEqual(collector.QUOTA_COST["search.list"], 100)
        self.assertEqual(collector.QUOTA_COST["videos.list"], 1)


if __name__ == "__main__":
    unittest.main()
