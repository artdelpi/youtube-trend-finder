from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class CollectCliTest(unittest.TestCase):
    def run_collect(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/collect.py", *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )

    def test_profile_is_required(self) -> None:
        result = self.run_collect("topic", "--days", "7", "--keyword", "test")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--profile", result.stderr)

    def test_unknown_profile_fails_before_collection_and_lists_valid(self) -> None:
        result = self.run_collect(
            "topic",
            "--profile",
            "unknown",
            "--days",
            "7",
            "--keyword",
            "test",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown profile 'unknown'", result.stderr)
        self.assertIn("possumdotmov", result.stderr)

    def test_path_profile_fails_before_collection(self) -> None:
        result = self.run_collect(
            "topic",
            "--profile",
            "../possumdotmov",
            "--days",
            "7",
            "--keyword",
            "test",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid profile name", result.stderr)

    def test_valid_profile_is_written_to_collection_context(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "trend_finder_collect_cli", ROOT / "scripts" / "collect.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as temp:
            csv_path = Path(temp) / "topic-api_videos.csv"
            csv_path.write_text("api_video_id\n", encoding="utf-8")
            result = {
                "csv": str(csv_path),
                "json": str(Path(temp) / "topic-api_payload.json"),
                "report": {
                    "raw_video_ids_found": 1,
                    "unique_videos_found": 1,
                    "estimated_quota_units": 101,
                },
            }
            stdout = io.StringIO()
            with mock.patch.object(module, "collect", return_value=result), contextlib.redirect_stdout(
                stdout
            ):
                code = module.main(
                    [
                        "topic",
                        "--profile",
                        "possumdotmov",
                        "--days",
                        "7",
                        "--keyword",
                        "test",
                        "--out-dir",
                        temp,
                    ]
                )

            self.assertEqual(code, 0)
            summary = json.loads(stdout.getvalue())
            self.assertEqual(summary["profile_id"], "possumdotmov")
            context = json.loads(Path(summary["profile_context"]).read_text(encoding="utf-8"))
            self.assertEqual(context["profile_id"], "possumdotmov")
            self.assertEqual(context["editorial_profile"]["id"], "possumdotmov")


if __name__ == "__main__":
    unittest.main()
