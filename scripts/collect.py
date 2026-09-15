from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_trend_finder import ProfileError, collect, load_profile  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect YouTube trend evidence.")
    parser.add_argument("topic", help="Topic or niche, such as 'horror channel'.")
    parser.add_argument(
        "--profile",
        required=True,
        help="Editorial profile id. No default or generic fallback is allowed.",
    )
    parser.add_argument("--days", type=int, required=True, help="Lookback window in days.")
    parser.add_argument(
        "--keyword",
        action="append",
        dest="keywords",
        required=True,
        help="Search keyword. Repeat for multiple keywords.",
    )
    parser.add_argument("--region", default="US", help="YouTube region code.")
    parser.add_argument("--language", default="en", help="Relevance language.")
    parser.add_argument("--pages-per-keyword", type=int, default=2)
    parser.add_argument("--out-dir", default="outputs")
    parser.add_argument("--no-timestamp", action="store_true",
                        help="Write directly into --out-dir; use a distinct directory per run batch.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        profile = load_profile(args.profile)
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = collect(
        topic=args.topic,
        keywords=args.keywords,
        days=args.days,
        region=args.region,
        language=args.language,
        pages_per_keyword=args.pages_per_keyword,
        out_dir=args.out_dir,
        timestamped_output=not args.no_timestamp,
    )
    report = result["report"]
    context_path = Path(result["csv"]).with_name(
        Path(result["csv"]).name.replace("-api_videos.csv", "-profile_context.json")
    )
    context_path.write_text(
        json.dumps(
            {
                "profile_id": profile.profile_id,
                "profile_file": str(profile.path),
                "schema_version": profile.data["schema_version"],
                "editorial_profile": profile.data,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "csv": result["csv"],
                "json": result["json"],
                "raw_video_ids_found": report["raw_video_ids_found"],
                "unique_videos_found": report["unique_videos_found"],
                "estimated_quota_units": report["estimated_quota_units"],
                "profile_id": profile.profile_id,
                "profile_context": str(context_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
