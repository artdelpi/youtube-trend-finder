from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_trend_finder.reference_channel import analyze_transcripts, read_vtt  # noqa: E402


class ReferenceTranscriptTest(unittest.TestCase):
    def test_transcript_failure_does_not_abort_corpus(self) -> None:
        publications = [
            {"video_id": "available", "title": "Available"},
            {"video_id": "missing", "title": "Missing"},
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "available.en.vtt"
            path.write_text(
                "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nThese are documented cases\n\n"
                "00:00:02.000 --> 00:00:04.000\ndocumented cases from a community\n",
                encoding="utf-8",
            )
            analysis = analyze_transcripts(publications, temp)

        self.assertEqual(analysis["transcripts_obtained"], 1)
        self.assertEqual(analysis["transcripts_unavailable"], 1)
        self.assertEqual(publications[0]["transcript"]["status"], "available")
        self.assertEqual(publications[1]["transcript"]["status"], "unavailable")

    def test_vtt_reader_removes_rolling_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.vtt"
            path.write_text(
                "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nOne two three\n\n"
                "00:00:01.000 --> 00:00:02.000\ntwo three four\n",
                encoding="utf-8",
            )
            self.assertEqual(read_vtt(path), "One two three four")


if __name__ == "__main__":
    unittest.main()
