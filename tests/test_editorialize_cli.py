"""Offline generation handoff: proposal budget and real channel memory."""
from __future__ import annotations

import contextlib
import dataclasses
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("editorialize_cli", ROOT / "scripts/editorialize.py")
assert spec and spec.loader
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class EditorializeCliTests(unittest.TestCase):
    def run_handoff(self, count=18, top=None, ledger_exists=True):
        actual = cli.load_profile("possumdotmov")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "scripts").mkdir()
            (workspace / "tracking").mkdir()
            shutil.copyfile(actual.path.parents[2] / "scripts/coverage.py", workspace / "scripts/coverage.py")
            rows = [{"theme": f"Hidden crime cases in game fandom community {i}",
                     "collector_trend_score": 100 - i} for i in range(count)]
            if ledger_exists:
                (workspace / "tracking/covered_subjects.txt").write_text(
                    f"2026-09-01 | covered | old-run | possumdotmov | {rows[0]['theme']} | |\n"
                    f"2026-09-02 | blocked | blocked-run | possumdotmov | {rows[1]['theme']} | |\n",
                    encoding="utf-8",
                )
            source = workspace / "candidates.json"
            source.write_text(json.dumps(rows), encoding="utf-8")
            profile = dataclasses.replace(actual, path=workspace / "profiles/possumdotmov/editorial-profile.json")
            args = ["--profile", "possumdotmov", "--input", str(source)]
            if top is not None:
                args += ["--top", str(top)]
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(cli, "load_profile", return_value=profile), \
                 mock.patch.object(cli, "load_reference_titles", return_value=[]), \
                 mock.patch.object(cli, "load_presentation_reference_analysis", return_value={"channels": []}), \
                 contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.main(args)
            if code:
                return code, err.getvalue()
            summary = json.loads(out.getvalue())
            drafts = json.loads(Path(summary["drafts"]).read_text(encoding="utf-8"))
            ranked = json.loads(Path(summary["ranked"]).read_text(encoding="utf-8"))
            prompt = Path(summary["generation_prompt"]).read_text(encoding="utf-8")
            return summary, drafts, ranked, prompt

    def test_default_fifteen_preserves_covered_and_excludes_explicit_block(self):
        summary, drafts, ranked, prompt = self.run_handoff()
        self.assertEqual(len(drafts), 15)
        self.assertEqual(summary["requested_proposals"], 15)
        self.assertEqual(summary["shortfall"], 0)
        covered = next(row for row in drafts if row["tracking_status"] == "covered")
        self.assertEqual(covered["tracking_run_id"], "old-run")
        self.assertEqual(covered["tracking_date"], "2026-09-01")
        self.assertEqual(drafts[0], covered)
        self.assertFalse(any(row["tracking_status"] == "blocked" for row in drafts))
        self.assertTrue(next(row for row in ranked if row["tracking_status"] == "blocked")["discarded"])
        self.assertIn("up to 15 distinct", prompt)
        self.assertTrue(summary["coverage_notices"])

    def test_shortfall_reported_without_padding(self):
        summary, drafts, _, _ = self.run_handoff(count=4)
        self.assertEqual(len(drafts), 3)
        self.assertEqual(summary["shortfall"], 12)

    def test_explicit_top_changes_the_handoff(self):
        summary, drafts, _, prompt = self.run_handoff(top=7)
        self.assertEqual(len(drafts), 7)
        self.assertEqual(summary["requested_proposals"], 7)
        self.assertIn("up to 7 distinct", prompt)

    def test_missing_ledger_cannot_silently_skip_coverage(self):
        code, error = self.run_handoff(ledger_exists=False)
        self.assertEqual(code, 2)
        self.assertIn("covered_subjects.txt", error)

    def test_nonpositive_top_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.parse_args(["--profile", "possumdotmov", "--input", "unused", "--top", "0"])


if __name__ == "__main__":
    unittest.main()
