from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_trend_finder import ProfileError, load_profile  # noqa: E402
from youtube_trend_finder.collector import load_api_key  # noqa: E402
from youtube_trend_finder.reference_channel import (  # noqa: E402
    build_analysis,
    collect_catalog,
    write_json,
)


def _profile_output(profile_dir: Path, relative: str) -> Path:
    target = (profile_dir / relative).resolve()
    reference_root = (profile_dir / "references").resolve()
    if not (
        profile_dir == target
        or profile_dir in target.parents
        or reference_root == target
        or reference_root in target.parents
    ):
        raise ProfileError("Reference output paths must stay inside the profile directory.")
    return target


def _tab_ids(channel_url: str, tab: str) -> tuple[set[str], dict[str, object]]:
    result = subprocess.run(
        [
            "yt-dlp",
            "--flat-playlist",
            "--ignore-errors",
            "--print",
            "%(id)s",
            f"{channel_url.rstrip('/')}/{tab}",
        ],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    ids = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    no_tab = "does not have a" in result.stderr and "tab" in result.stderr
    return ids, {
        "available": bool(ids),
        "items": len(ids),
        "status": "absent" if no_tab else "ok" if result.returncode == 0 else "failed",
        "limitation": "" if result.returncode == 0 or no_tab else result.stderr.strip()[-500:],
    }


def _refresh_captions(channel_url: str, cache_dir: Path) -> int:
    cache_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "yt-dlp",
        "--ignore-errors",
        "--no-simulate",
        "--skip-download",
        "--write-info-json",
        "--no-write-playlist-metafiles",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        "en.*,en,-live_chat",
        "--sub-format",
        "vtt",
        "--sleep-requests",
        "0.25",
        "--output",
        str(cache_dir / "%(id)s.%(ext)s"),
        f"{channel_url.rstrip('/')}/videos",
    ]
    return subprocess.run(command).returncode


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect a complete public reference-channel catalog and analyze captions."
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument(
        "--refresh-captions",
        action="store_true",
        help="Refresh yt-dlp metadata and English captions without downloading video/audio.",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Ignored local cache. Defaults to .slash_tmp under the Slop Factory root.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        profile = load_profile(args.profile)
        reference = profile.data["reference"]
        profile_dir = profile.path.parent.resolve()
        catalog_path = _profile_output(profile_dir, reference["catalog_file"])
        analysis_path = _profile_output(profile_dir, reference["analysis_file"])
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    factory_root = profile_dir.parent.parent
    cache_dir = (
        Path(args.cache_dir).resolve()
        if args.cache_dir
        else factory_root / ".slash_tmp" / "trend_finder" / profile.profile_id / "reference-channel"
    )
    channel_url = reference["url"].rstrip("/")
    handle = channel_url.rsplit("/", 1)[-1]

    if args.refresh_captions:
        _refresh_captions(channel_url, cache_dir)

    try:
        key = load_api_key(ROOT / ".env")
        catalog = collect_catalog(handle, key)
    except (OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    short_ids, shorts_status = _tab_ids(channel_url, "shorts")
    stream_ids, streams_status = _tab_ids(channel_url, "streams")
    for publication in catalog["publications"]:
        if publication["video_id"] in short_ids:
            publication["publication_type"] = "short"
        elif publication["video_id"] in stream_ids:
            publication["publication_type"] = "live"

    catalog["collection"].update(
        {
            "collected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source": "YouTube Data API v3 uploads playlist plus yt-dlp public tabs/captions",
            "tabs": {"shorts": shorts_status, "streams": streams_status},
            "cache": str(cache_dir),
            "video_or_audio_downloaded": False,
        }
    )
    analysis = build_analysis(catalog, cache_dir)
    declared_failures = {
        item.get("video_id"): item.get("reason")
        for item in reference.get("failures", [])
        if isinstance(item, dict) and item.get("video_id") and item.get("reason")
    }
    for publication in catalog["publications"]:
        transcript = publication.get("transcript", {})
        reason = declared_failures.get(publication["video_id"])
        if transcript.get("status") == "unavailable" and reason:
            transcript["reason"] = reason
    for failure in analysis["transcripts"]["failures"]:
        reason = declared_failures.get(failure["video_id"])
        if reason:
            failure["reason"] = reason
    catalog["collection"]["transcripts_obtained"] = analysis["transcripts"][
        "transcripts_obtained"
    ]
    catalog["collection"]["transcripts_unavailable"] = analysis["transcripts"][
        "transcripts_unavailable"
    ]
    catalog["collection"]["catalog_complete"] = not catalog["collection"][
        "metadata_failures"
    ]
    catalog["collection"]["transcript_coverage_complete"] = not analysis[
        "transcripts"
    ]["failures"]
    write_json(catalog_path, catalog)
    write_json(analysis_path, analysis)

    print(
        json.dumps(
            {
                "profile_id": profile.profile_id,
                "catalog": str(catalog_path),
                "analysis": str(analysis_path),
                "publications": len(catalog["publications"]),
                "playlist_pages": catalog["collection"]["playlist_pages_traversed"],
                "transcripts_obtained": analysis["transcripts"]["transcripts_obtained"],
                "transcripts_unavailable": analysis["transcripts"]["transcripts_unavailable"],
                "failures": analysis["transcripts"]["failures"],
                "shorts_tab": shorts_status,
                "streams_tab": streams_status,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
