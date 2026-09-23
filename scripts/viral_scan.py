"""Find recent breakout videos in a run's YouTube collections for the recycle lane.

Reads every `_internal/youtube/<batch>/*-api_videos.csv` of one trend run,
screens format and profile exclusions without spending quota, then measures
the survivors against their own channel's recent uploads:

    py scripts/viral_scan.py --run-dir "<run_dir>" --profile <profile_id>

Writes `_internal/viral/viral_candidates.csv` (every screened row, measured or
not, with the reason) and `_internal/viral/viral_scan.json` (parameters and
quota). About 1 + 1 + N + N*30/50 units for N measured channels, so the
default 40 costs roughly 70 units.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
import urllib.error
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_trend_finder import ProfileError, evaluate_profile_fit, load_profile  # noqa: E402
from youtube_trend_finder.collector import (  # noqa: E402
    iso_utc,
    load_api_key,
    parse_date,
    parse_duration_seconds,
)
from youtube_trend_finder.viral import (  # noqa: E402
    SHORT_MAX_SECONDS,
    channel_baseline,
    classify_format,
    fetch_channel_uploads,
    fetch_videos,
    outlier_metrics,
)

FIELDS = [
    "viral_rank", "collector_scan_status", "api_video_id", "api_url", "api_title", "api_channel",
    "api_channel_id", "api_published_at", "api_views", "api_likes", "api_comments",
    "api_duration_seconds", "api_channel_subscribers", "collector_age_hours",
    "collector_views_per_hour", "collector_recent_views_per_hour", "collector_engagement_rate",
    "collector_channel_median_views", "collector_channel_sample", "collector_outlier_ratio",
    "collector_subscriber_ratio", "collector_breakout", "collector_viral_score",
    "collector_viral_components", "collector_format_class", "collector_format_screen",
    "collector_format_reason", "collector_profile_rejected_by", "collector_keywords_matched",
    "collector_batches", "collector_refreshed_at", "api_description", "api_tags",
]


def read_collections(run_dir: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    rows: dict[str, dict[str, Any]] = {}
    batches: list[str] = []
    for path in sorted((run_dir / "_internal/youtube").glob("*/*-api_videos.csv")):
        batch = path.parent.name
        batches.append(batch)
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                video_id = row.get("api_video_id", "")
                if not video_id:
                    continue
                seen = rows.get(video_id)
                row_batches = [*(seen or {}).get("collector_batches", "").split("|"), batch]
                if seen is None or int(row.get("api_views") or 0) >= int(seen.get("api_views") or 0):
                    rows[video_id] = dict(row)
                rows[video_id]["collector_batches"] = "|".join(sorted({b for b in row_batches if b}))
    return rows, sorted(set(batches))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--max-age-days", type=float, default=45,
                        help="Recent means published within this many days (default 45).")
    parser.add_argument("--min-views", type=int, default=50_000)
    parser.add_argument("--min-duration", type=int, default=180,
                        help="Seconds; long-form commentary is the lane's target (default 180).")
    parser.add_argument("--include-shorts", action="store_true",
                        help="Also measure Shorts against the channel's other Shorts.")
    parser.add_argument("--candidates", type=int, default=40,
                        help="How many screened videos to measure against their channel (default 40).")
    parser.add_argument("--uploads-per-channel", type=int, default=30)
    args = parser.parse_args(argv)
    if args.candidates < 1:
        parser.error("--candidates must be positive")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = args.run_dir.resolve()
    if not (run_dir / "_internal/run.json").is_file():
        print(f"error: not a trend run: {run_dir}", file=sys.stderr)
        return 2
    try:
        profile = load_profile(args.profile)
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    collected, batches = read_collections(run_dir)
    if not collected:
        print("error: no YouTube collections under _internal/youtube/", file=sys.stderr)
        return 2

    now = dt.datetime.now(dt.timezone.utc)
    screened: list[dict[str, Any]] = []
    for row in collected.values():
        try:
            age_hours = (now - parse_date(row["api_published_at"])).total_seconds() / 3600
        except (KeyError, ValueError):
            continue
        views = int(float(row.get("api_views") or 0))
        duration = int(float(row.get("api_duration_seconds") or 0))
        if age_hours > args.max_age_days * 24 or views < args.min_views or duration <= 0:
            continue
        if duration < args.min_duration and not (args.include_shorts and duration <= SHORT_MAX_SECONDS):
            continue
        row.update(classify_format(row))
        fit = evaluate_profile_fit(row, profile.data)
        row["collector_profile_rejected_by"] = "|".join(fit["profile_rejected_by"])
        if row["collector_format_screen"] == "rejected":
            row["collector_scan_status"] = "not-measured: format rejected"
        elif fit["profile_rejected_by"]:
            row["collector_scan_status"] = "not-measured: profile exclusion"
        else:
            row["collector_scan_status"] = "pool"
        screened.append(row)

    pool = sorted((r for r in screened if r["collector_scan_status"] == "pool"),
                  key=lambda r: float(r.get("collector_views_per_hour") or 0), reverse=True)
    for row in pool[args.candidates:]:
        row["collector_scan_status"] = f"not-measured: below the top {args.candidates} by views/hour"
    pool = pool[:args.candidates]

    calls: list[dict[str, Any]] = []
    error = ""
    if pool:
        try:
            key = load_api_key(ROOT / ".env")
            fresh = fetch_videos([r["api_video_id"] for r in pool], key, calls)
            refreshed_at = iso_utc(now)
            for row in pool:
                item = fresh.get(row["api_video_id"])
                if not item:
                    row["collector_scan_status"] = "not-measured: video no longer listed"
                    continue
                stats, snippet = item.get("statistics", {}), item.get("snippet", {})
                old_views, old_age = int(float(row.get("api_views") or 0)), float(row.get("collector_age_hours") or 0)
                published = parse_date(snippet.get("publishedAt") or row["api_published_at"])
                age_hours = max((now - published).total_seconds() / 3600, 1)
                views = int(stats.get("viewCount") or 0)
                row.update(
                    api_channel_id=snippet.get("channelId", row.get("api_channel_id", "")),
                    api_views=views,
                    api_likes=int(stats.get("likeCount") or 0),
                    api_comments=int(stats.get("commentCount") or 0),
                    api_duration_seconds=parse_duration_seconds(item.get("contentDetails", {}).get("duration")),
                    collector_age_hours=round(age_hours, 2),
                    collector_views_per_hour=round(views / age_hours, 2),
                    collector_refreshed_at=refreshed_at,
                )
                # Velocity since the collection snapshot says whether it is still climbing.
                elapsed = age_hours - old_age
                if elapsed >= 1 and views >= old_views:
                    row["collector_recent_views_per_hour"] = round((views - old_views) / elapsed, 2)
            channels = fetch_channel_uploads(
                [r["api_channel_id"] for r in pool if r.get("api_channel_id")], key, calls,
                per_channel=args.uploads_per_channel,
            )
            for row in pool:
                if row["collector_scan_status"] != "pool":
                    continue
                channel = channels.get(row.get("api_channel_id", ""))
                if not channel:
                    row["collector_scan_status"] = "not-measured: channel unavailable"
                    continue
                long_form = int(row["api_duration_seconds"]) > SHORT_MAX_SECONDS
                baseline = channel_baseline(channel["recent"], exclude_video_id=row["api_video_id"],
                                            long_form=long_form, now=now)
                row.update(outlier_metrics(row, baseline, channel["subscribers"]))
                row["collector_scan_status"] = (
                    "measured" if baseline["collector_channel_sample"] >= 3
                    else f"measured: thin baseline ({baseline['collector_channel_sample']} uploads)"
                )
        except (RuntimeError, urllib.error.URLError, OSError) as exc:
            # A quota wall must read as a quota wall, never as "no breakouts".
            error = f"{type(exc).__name__}: {exc}"

    measured = [r for r in screened if str(r["collector_scan_status"]).startswith("measured")]
    measured.sort(key=lambda r: float(r.get("collector_viral_score") or 0), reverse=True)
    for rank, row in enumerate(measured, start=1):
        row["viral_rank"] = rank
    rest = [r for r in screened if r not in measured]
    out_dir = run_dir / "_internal/viral"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "viral_candidates.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(measured + rest)
    quota = sum(int(call.get("quota_units", 0)) for call in calls)
    summary = {
        "run_dir": str(run_dir),
        "profile_id": profile.profile_id,
        "measured_at": iso_utc(now),
        "batches": batches,
        "parameters": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "collected_videos": len(collected),
        "screened": len(screened),
        "format_rejected": sum(1 for r in screened if r["collector_scan_status"] == "not-measured: format rejected"),
        "profile_excluded": sum(1 for r in screened if r["collector_scan_status"] == "not-measured: profile exclusion"),
        "measured": len(measured),
        "breakouts": sum(1 for r in measured if r.get("collector_breakout") == "breakout"),
        "strong": sum(1 for r in measured if r.get("collector_breakout") == "strong"),
        "estimated_quota_units": quota,
        "error": error,
        "api_calls": calls,
        "csv": str(csv_path),
    }
    (out_dir / "viral_scan.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "api_calls"}, ensure_ascii=False, indent=2))
    top = [f"{r['viral_rank']:>2}. {r['collector_breakout']:<14} {r.get('collector_outlier_ratio') or '?':>7}x "
           f"{r['collector_format_screen']:<12} {r['api_title'][:70]}" for r in measured[:15]]
    if top:
        print("\n".join(top))
    return 1 if error else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
