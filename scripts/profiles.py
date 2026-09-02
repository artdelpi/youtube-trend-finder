from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_trend_finder import ProfileError, list_profiles, load_profile  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List or validate editorial profiles.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List profiles available to trend_finder.")
    validate = subparsers.add_parser("validate", help="Validate one profile.")
    validate.add_argument("profile")
    args = parser.parse_args(argv)

    try:
        if args.command == "list":
            for profile_id in list_profiles():
                print(profile_id)
            return 0
        profile = load_profile(args.profile)
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "profile_id": profile.profile_id,
                "schema_version": profile.data["schema_version"],
                "path": str(profile.path),
                "status": "valid",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
