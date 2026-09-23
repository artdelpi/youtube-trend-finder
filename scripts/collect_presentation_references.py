from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_trend_finder import (  # noqa: E402
    ProfileError,
    analyze_presentation_channel,
    load_profile,
)
from youtube_trend_finder.reference_channel import read_vtt, write_json  # noqa: E402


def _profile_output(profile_dir: Path, relative: str) -> Path:
    target = (profile_dir / relative).resolve()
    reference_root = (profile_dir / "references").resolve()
    if not (
        profile_dir == target
        or profile_dir in target.parents
        or reference_root == target
        or reference_root in target.parents
    ):
        raise ProfileError("Presentation reference output must stay inside the profile directory.")
    return target


def _flat_catalog(channel_url: str, limit: int) -> list[dict[str, Any]]:
    result = subprocess.run(
        [
            "yt-dlp",
            "--flat-playlist",
            "--playlist-end",
            str(limit),
            "--no-warnings",
            "--dump-json",
            channel_url,
        ],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        video_id = item.get("id")
        title = item.get("title")
        if not isinstance(video_id, str) or not isinstance(title, str):
            continue
        view_count = item.get("view_count")
        rows.append(
            {
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": title,
                "view_count": int(view_count) if isinstance(view_count, (int, float)) else None,
            }
        )
    if not rows:
        limitation = result.stderr.strip()[-500:]
        raise RuntimeError(
            f"yt-dlp returned no public Videos-tab items for {channel_url}: {limitation}"
        )
    return rows


def _caption_path(cache_dir: Path, video_id: str) -> Path | None:
    choices = (
        cache_dir / f"{video_id}.en-orig.vtt",
        cache_dir / f"{video_id}.en.vtt",
    )
    return next((path for path in choices if path.is_file()), None)


def _download_caption(video_id: str, cache_dir: Path) -> tuple[Path | None, str]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    existing = _caption_path(cache_dir, video_id)
    if existing is not None:
        return existing, "cached"

    errors: list[str] = []
    for language in ("en-orig", "en"):
        result = subprocess.run(
            [
                "yt-dlp",
                "--ignore-errors",
                "--skip-download",
                "--write-subs",
                "--write-auto-subs",
                "--sub-langs",
                language,
                "--sub-format",
                "vtt",
                "--no-write-playlist-metafiles",
                "--output",
                str(cache_dir / "%(id)s.%(ext)s"),
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        path = _caption_path(cache_dir, video_id)
        if path is not None:
            return path, "downloaded"
        if result.stderr.strip():
            errors.append(result.stderr.strip()[-250:])
    return None, " | ".join(errors) or "No accessible English captions returned."


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure title mechanics and small caption-opening samples from public "
            "presentation reference channels without downloading video or audio."
        )
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument(
        "--refresh-captions",
        action="store_true",
        help="Fetch declared caption samples when absent from the ignored cache.",
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
        config = profile.data["presentation_references"]
        profile_dir = profile.path.parent.resolve()
        analysis_path = _profile_output(profile_dir, config["analysis_file"])
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    factory_root = profile_dir.parent.parent
    cache_root = (
        Path(args.cache_dir).resolve()
        if args.cache_dir
        else factory_root
        / ".slash_tmp"
        / "trend_finder"
        / profile.profile_id
        / "presentation-references"
    )
    channels: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for channel in config["channels"]:
        channel_id = channel["id"]
        try:
            publications = _flat_catalog(channel["url"], int(config["title_limit"]))
        except RuntimeError as exc:
            failures.append({"channel": channel_id, "reason": str(exc)})
            continue

        caption_texts: dict[str, str] = {}
        caption_status: list[dict[str, str]] = []
        channel_cache = cache_root / channel_id
        for video_id in channel["caption_video_ids"]:
            path = _caption_path(channel_cache, video_id)
            status = "cached" if path else "not requested"
            if path is None and args.refresh_captions:
                path, status = _download_caption(video_id, channel_cache)
            if path is not None:
                caption_texts[video_id] = read_vtt(path)
            caption_status.append(
                {"video_id": video_id, "status": status, "cache_file": path.name if path else ""}
            )

        analysis = analyze_presentation_channel(
            channel,
            publications,
            caption_texts,
            excerpt_words=int(config["caption_excerpt_words"]),
        )
        analysis["caption_collection"] = caption_status
        channels.append(analysis)

    payload = {
        "schema_version": 2,
        "collected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "method": (
            "yt-dlp flat-playlist metadata for a bounded recent title window plus "
            "declared English caption-opening samples; no video, audio, or thumbnail downloaded."
        ),
        "rights": (
            "Reference patterns only. Never copy or closely paraphrase title or caption wording."
        ),
        "title_limit_per_channel": config["title_limit"],
        "caption_excerpt_words": config["caption_excerpt_words"],
        "channels": channels,
        "presentation_archetypes": profile.data["presentation"]["archetypes"],
        "collection_failures": failures,
        "limitations": [
            "Title/view associations are descriptive, not causal.",
            "Small caption samples validate title-to-opening promise only; they do not characterize full videos.",
            "Automatic captions can contain recognition errors and missing punctuation.",
            "Public metrics and availability can change after collection.",
        ],
    }
    write_json(analysis_path, payload)
    print(
        json.dumps(
            {
                "profile_id": profile.profile_id,
                "analysis": str(analysis_path),
                "channels_requested": len(config["channels"]),
                "channels_analyzed": len(channels),
                "titles_analyzed": sum(item["title_window"] for item in channels),
                "captions_obtained": sum(
                    item["caption_analysis"]["obtained"] for item in channels
                ),
                "video_or_audio_downloaded": False,
                "failures": failures,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if channels else 2


if __name__ == "__main__":
    raise SystemExit(main())
