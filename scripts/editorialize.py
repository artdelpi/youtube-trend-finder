from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_trend_finder import (  # noqa: E402
    ProfileError,
    build_generation_prompt,
    draft_suggestion,
    load_profile,
    load_presentation_reference_analysis,
    load_reference_titles,
    rank_trends_for_profile,
)


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return [dict(item) for item in payload["rows"] if isinstance(item, dict)]
    raise ValueError("Input JSON must be a list or an object with a 'rows' list.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply an editorial profile to collected trend candidates."
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument("--input", required=True, help="Candidate CSV or JSON.")
    parser.add_argument("--top", type=int, default=15, help="Maximum proposals (default: 15); never pad weak evidence.")
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory. Defaults beside the input file.",
    )
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top must be positive")
    return args


def annotate_coverage(rows: list[dict[str, Any]], profile: Any) -> None:
    """Recheck the enclosing channel ledger on every generation handoff."""
    workspace = profile.path.parents[2]
    script = workspace / "scripts" / "coverage.py"
    ledger = workspace / "tracking" / "covered_subjects.txt"
    if not script.is_file() or not ledger.is_file():
        raise ValueError("Coverage checker and tracking/covered_subjects.txt are required before proposals.")
    spec = importlib.util.spec_from_file_location("slop_coverage", script)
    assert spec and spec.loader
    coverage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(coverage)
    entries = coverage.read_ledger(ledger)
    for row in rows:
        subject = row.get("codex_theme") or row.get("theme") or row.get("topic")
        if not subject:
            raise ValueError("Every candidate needs a subject in theme, codex_theme or topic for coverage checking.")
        result = coverage.check_subject(str(subject), entries, profile.profile_id)
        best = result["matches"][0]["entry"] if result["matches"] else {}
        row.update(
            tracking_status=result["verdict"], tracking_match=best.get("subject", ""),
            tracking_date=best.get("date", ""), tracking_run_id=best.get("run_id", ""),
            tracking_advice=result["advice"],
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = Path(args.input).resolve()
    if not source.is_file():
        print(f"error: input does not exist: {source}", file=sys.stderr)
        return 2
    try:
        profile = load_profile(args.profile)
        reference_titles = load_reference_titles(profile)
        presentation_analysis = load_presentation_reference_analysis(profile)
        rows = _read_rows(source)
        annotate_coverage(rows, profile)
    except (ProfileError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    ranked = rank_trends_for_profile(rows, profile.data, reference_titles)
    for item in ranked:
        if item["tracking_status"] == "blocked":
            item.update(discarded=True, discard_reason="Explicit channel tracking block")
            item.pop("profile_rank", None)
    compatible = [item for item in ranked if not item["discarded"]]
    for rank, item in enumerate(compatible, start=1):
        item["profile_rank"] = rank
    selected = compatible[:args.top]
    drafts = [
        {
            **draft_suggestion(item, profile.data),
            "trend_score": item["trend_score"],
            "profile_fit_score": item["profile_fit_score"],
            "combined_score": item["combined_score"],
            "profile_fit_reason": item["profile_fit_reason"],
            **{key: value for key, value in item.items() if key.startswith("tracking_")},
        }
        for item in selected
    ]
    out_dir = Path(args.out_dir).resolve() if args.out_dir else source.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = source.stem
    ranked_path = out_dir / f"{stem}-profile-ranked.json"
    drafts_path = out_dir / f"{stem}-profile-drafts.json"
    prompt_path = out_dir / f"{stem}-generation-prompt.md"
    ranked_path.write_text(
        json.dumps(ranked, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    drafts_path.write_text(
        json.dumps(drafts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    prompt_path.write_text(
        build_generation_prompt(
            profile.data,
            selected,
            reference_titles,
            presentation_analysis,
            top=args.top,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "profile_id": profile.profile_id,
                "input_rows": len(rows),
                "compatible_rows": len(compatible),
                "discarded_rows": len(ranked) - len(compatible),
                "requested_proposals": args.top,
                "proposal_rows": len(selected),
                "shortfall": max(0, args.top - len(selected)),
                "coverage_notices": [
                    {"subject": item.get("codex_theme") or item.get("theme") or item.get("topic"),
                     **{key: value for key, value in item.items() if key.startswith("tracking_")}}
                    for item in ranked if item["tracking_status"] != "clear"
                ],
                "ranked": str(ranked_path),
                "drafts": str(drafts_path),
                "generation_prompt": str(prompt_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
