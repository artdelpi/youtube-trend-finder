from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_trend_finder import collect  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect YouTube trend evidence.")
    parser.add_argument("topic", help="Topic or niche, such as 'horror channel'.")
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = collect(
        topic=args.topic,
        keywords=args.keywords,
        days=args.days,
        region=args.region,
        language=args.language,
        pages_per_keyword=args.pages_per_keyword,
        out_dir=args.out_dir,
    )
    report = result["report"]
    print(
        json.dumps(
            {
                "csv": result["csv"],
                "json": result["json"],
                "raw_video_ids_found": report["raw_video_ids_found"],
                "unique_videos_found": report["unique_videos_found"],
                "estimated_quota_units": report["estimated_quota_units"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

