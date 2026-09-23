"""Fail when a recycle film repeats its reference video's narration.

    py agents/search/trend_finder/scripts/check_recycle_copy.py --reference "<transcript.txt>" --text "<brief.json or script>"

A shared run of 8 words (`viral.TRANSCRIPT_NGRAM`) is a copied sentence, not a
shared idea. JSON inputs are read as every string value they hold, so a brief's
narration, cards and titles are all checked. Exit 1 lists each copied run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_trend_finder.viral import TRANSCRIPT_NGRAM, shared_runs  # noqa: E402


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.values() for s in strings(item)]
    if isinstance(value, list):
        return [s for item in value for s in strings(item)]
    return []


def read_text(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        return strings(json.loads(text))
    return text.splitlines()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reference", type=Path, required=True, help="The reference transcript.txt.")
    parser.add_argument("--text", type=Path, action="append", required=True,
                        help="Brief, script or proposal text to check. Repeatable.")
    args = parser.parse_args(argv)
    reference = args.reference.read_text(encoding="utf-8")
    copied: list[dict[str, str]] = []
    for path in args.text:
        for passage in read_text(path):
            for run in shared_runs(passage, reference):
                copied.append({"file": str(path), "run": run, "passage": passage[:200]})
    print(json.dumps({"ngram": TRANSCRIPT_NGRAM, "copied": copied}, ensure_ascii=False, indent=2))
    return 1 if copied else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
