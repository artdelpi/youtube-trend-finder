"""Build the study pack for one recycle reference: why did this video break out?

    py scripts/viral_study.py --run-dir "<run_dir>" --video <video_id or URL>

Writes `_internal/viral/<video_id>/`:

    reference.json    fresh statistics, chapters, most-replayed curve, scan metrics
    comments.json     top-level comments by relevance (and newest), with permalinks
    transcript.txt    timestamped narration from the caption track, when one exists
    signals.json      comment piles, commented timestamps, replayed moments and
                      the narration lines commenters quoted back, each with what was said
    thumbnail.jpg     the packaging the audience clicked
    study.md          the agent's analysis; created once as a pending template

Only metadata, captions, comments and the thumbnail are fetched - the same
things `check_download.py` leaves open on a `deny`. The video file is never
downloaded here. Quota: 1 unit for the statistics plus 1 per comment page.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_trend_finder.collector import iso_utc, load_api_key, parse_duration_seconds  # noqa: E402
from youtube_trend_finder.viral import (  # noqa: E402
    STUDY_PENDING as PENDING,
    comment_signals,
    excerpt_at,
    fetch_comments,
    fetch_videos,
    heatmap_peaks,
    parse_vtt,
    transcript_text,
)

VIDEO_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|^)([A-Za-z0-9_-]{11})(?:[&?#/]|$)")
INFO_KEEP = ("id", "title", "channel", "channel_id", "channel_follower_count", "upload_date",
             "timestamp", "duration", "view_count", "like_count", "comment_count", "tags",
             "categories", "chapters", "heatmap", "description", "thumbnail", "language",
             "age_limit", "live_status")
# Within a kind (authored, then ASR), the plainest English track first.
TRACK_PREFERENCE = ("en", "en-US", "en-GB", "en-orig")
ASR_PREFERENCE = ("en-orig", "en", "en-US", "en-GB")
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def video_id_of(value: str) -> str:
    match = VIDEO_ID.search(value.strip())
    if not match:
        raise ValueError(f"not a YouTube video id or URL: {value}")
    return match.group(1)


def scan_row(run_dir: Path, video_id: str) -> dict[str, Any]:
    path = run_dir / "_internal/viral/viral_candidates.csv"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("api_video_id") == video_id:
                return {k: v for k, v in row.items() if k.startswith(("collector_", "viral_rank"))}
    return {}


def pick_tracks(info: dict[str, Any]) -> list[tuple[str, str]]:
    """(label, vtt url) of every English track, best first: authored, then ASR.

    Among ASR tracks `en-orig` comes first. On an English video the ASR `en`
    entry is YouTube's translation route (`&tlang=en`), and on 2026-09-23 it
    answered HTTP 429 on three videos in a row while `en-orig` returned the
    whole track on the next request.
    """

    out: list[tuple[str, str]] = []
    for kind, tracks, order in (("manual", info.get("subtitles") or {}, TRACK_PREFERENCE),
                                ("asr", info.get("automatic_captions") or {}, ASR_PREFERENCE)):
        langs = [lang for lang in order if lang in tracks]
        langs += sorted(lang for lang in tracks if lang.startswith("en-") and lang not in langs)
        for lang in langs:
            url = next((f["url"] for f in tracks[lang] if f.get("ext") == "vtt" and f.get("url")), "")
            if url:
                out.append((f"{kind}:{lang}", url))
    return out


def pick_track(info: dict[str, Any]) -> tuple[str, str]:
    tracks = pick_tracks(info)
    return tracks[0] if tracks else ("", "")


def fetch_metadata_and_captions(url: str) -> tuple[dict[str, Any], str, str, str]:
    """yt-dlp without the media, then exactly one caption request.

    Letting yt-dlp write every English track costs one timedtext request per
    track, and the second one is where YouTube starts answering 429 (2026-09-23).
    Returns (slim info, label, vtt text, status).
    """

    command = ["yt-dlp", "--skip-download", "--dump-single-json", "--no-warnings", "--no-progress", url]
    if not shutil.which("yt-dlp"):
        command[0:1] = [sys.executable, "-m", "yt_dlp"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=180)
    if result.returncode:
        stderr = (result.stderr or "").strip().splitlines()
        return {}, "", "", f"failed: {stderr[-1] if stderr else f'yt-dlp exit {result.returncode}'}"
    info = json.loads(result.stdout)
    slim = {k: info.get(k) for k in INFO_KEEP if k in info}
    tracks = pick_tracks(info)
    if not tracks:
        if not (info.get("subtitles") or info.get("automatic_captions")):
            return slim, "", "", "no-track (the video has no caption track)"
        return slim, "", "", "no English track"
    failures: list[str] = []
    # One request per track, at most three tracks; a 429 on one track is not
    # a verdict on the next (the `en` translation route fails where `en-orig` answers).
    for label, track_url in tracks[:3]:
        request = urllib.request.Request(track_url, headers={"User-Agent": BROWSER_UA})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return slim, label, response.read().decode("utf-8", "replace"), "ok"
        except urllib.error.HTTPError as exc:
            failures.append(f"{label} HTTP {exc.code}")
        except urllib.error.URLError as exc:
            failures.append(f"{label} {exc.reason}")
        time.sleep(3)
    # A 429 or bot wall is a route failure, not "no captions" (researcher ROUTES.md).
    return slim, tracks[0][0], "", "failed: " + "; ".join(failures)


def fetch_thumbnail(video_id: str, target: Path) -> str:
    for name in ("maxresdefault.jpg", "hqdefault.jpg"):
        url = f"https://i.ytimg.com/vi/{video_id}/{name}"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                target.write_bytes(response.read())
            return url
        except urllib.error.URLError:
            continue
    return ""


def study_template(reference: dict[str, Any]) -> str:
    scan = reference.get("scan", {})
    return f"""# Recycle study: {reference.get('title', '')}

{PENDING} - replace this line once every section below is written from the pack.

Reference: {reference.get('url', '')} · {reference.get('channel', '')} · published {reference.get('published_at', '')}
Measured {reference.get('measured_at', '')}: {reference.get('views', '')} views, {reference.get('comments', '')} comments,
{scan.get('collector_outlier_ratio') or '?'}x the channel median ({scan.get('collector_breakout') or 'not scanned'}).

Cite comment ids, `quoted_lines`, `timestamp_peaks` and `heatmap_peaks` from `signals.json`
for every claim about the audience. Lexical piles are sorting, not sentiment: read them.

## Format verdict

`recyclable` or `not recyclable`, and why. Recyclable: commentary, theory, compilation,
documentary, essay, review, reaction or ranking - a film another channel can answer with its
own research and conclusions. Not recyclable: the work itself (an animation episode, a short
film, a series entry), a trailer or official promotion, music, gameplay without commentary, a
performance, a raw news clip. Those belong to the trend lane as subjects, not references.

## Why it broke out

Packaging (title mechanic, thumbnail promise), subject heat (what else is happening on the
subject right now), timing, and the reflections and conclusions the audience responded to.

## Attention

The moments viewers replayed or pointed at, and what the narration said there.

## Sentiment and repercussion

How the comment section splits (praise, criticism, correction, request, personal stake,
question), what the split says, and where else the video echoed (Reddit, response videos,
headroom on the subject).

## Hits to keep

The conclusions, reflections and structural moves that worked - as ideas, never as wording.

## Misses to fix

Corrections, complaints, unanswered questions and requests. Each one is a place our film is
better, and each needs research to deliver.

## Originality boundary

What we must not reuse: their title wording, thumbnail composition, running order, jokes,
sentences, footage. What is ours: the evidence they lacked, the cases they missed, the
profile's register and our own conclusion.

## Our film

One paragraph: the proposal this study earns, or why it earns none.
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--video", required=True, help="Video id or YouTube URL.")
    parser.add_argument("--comment-pages", type=int, default=3,
                        help="Relevance-ordered pages of 100 comments (default 3).")
    parser.add_argument("--recent-pages", type=int, default=1,
                        help="Newest-first pages of 100, for how the reaction is moving (default 1).")
    parser.add_argument("--no-captions", action="store_true", help="Skip yt-dlp entirely.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = args.run_dir.resolve()
    try:
        video_id = video_id_of(args.video)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not (run_dir / "_internal/run.json").is_file():
        print(f"error: not a trend run: {run_dir}", file=sys.stderr)
        return 2
    out = run_dir / "_internal/viral" / video_id
    out.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"
    now = dt.datetime.now(dt.timezone.utc)
    calls: list[dict[str, Any]] = []
    statuses: dict[str, str] = {}

    key = load_api_key(ROOT / ".env")
    item = fetch_videos([video_id], key, calls).get(video_id)
    if not item:
        print(f"error: {video_id} is not listed by the API (private, removed or wrong id)", file=sys.stderr)
        return 2
    snippet, stats = item.get("snippet", {}), item.get("statistics", {})
    duration = parse_duration_seconds(item.get("contentDetails", {}).get("duration"))

    comments: list[dict[str, Any]] = []
    try:
        rows, statuses["comments"] = fetch_comments(video_id, key, calls, pages=args.comment_pages)
        comments.extend(rows)
        if args.recent_pages > 0 and statuses["comments"] == "ok":
            recent, _ = fetch_comments(video_id, key, calls, pages=args.recent_pages, order="time")
            known = {c["comment_id"] for c in comments}
            comments.extend(c for c in recent if c["comment_id"] not in known)
    except urllib.error.HTTPError as exc:
        statuses["comments"] = f"failed: HTTP {exc.code}"

    info: dict[str, Any] = {}
    segments: list[dict[str, Any]] = []
    if args.no_captions:
        statuses["transcript"] = "skipped"
    else:
        try:
            info, label, vtt, statuses["transcript"] = fetch_metadata_and_captions(url)
            if vtt:
                segments = parse_vtt(vtt)
                statuses["transcript_track"] = label
        except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as exc:
            statuses["transcript"] = f"failed: {type(exc).__name__}: {exc}"
    if segments:
        (out / "transcript.txt").write_text(transcript_text(segments) + "\n", encoding="utf-8")

    thumbnail = fetch_thumbnail(video_id, out / "thumbnail.jpg")
    statuses["thumbnail"] = "ok" if thumbnail else "failed"
    heat = heatmap_peaks(info.get("heatmap"))
    statuses["heatmap"] = "ok" if heat else "absent (YouTube shows no most-replayed curve yet)"

    signals = comment_signals(comments, segments, duration=duration)
    signals["heatmap_peaks"] = [{**peak, "said": excerpt_at(segments, peak["start"])} for peak in heat]
    signals["chapters"] = info.get("chapters") or []

    published = snippet.get("publishedAt", "")
    reference = {
        "video_id": video_id,
        "url": url,
        "title": snippet.get("title", ""),
        "channel": snippet.get("channelTitle", ""),
        "channel_id": snippet.get("channelId", ""),
        "channel_followers": info.get("channel_follower_count"),
        "published_at": published,
        "measured_at": iso_utc(now),
        "duration_seconds": duration,
        "views": int(stats.get("viewCount") or 0),
        "likes": int(stats.get("likeCount") or 0),
        "comments": int(stats.get("commentCount") or 0),
        "tags": snippet.get("tags", []),
        "description": snippet.get("description", ""),
        "thumbnail_url": thumbnail,
        "chapters": info.get("chapters") or [],
        "heatmap": info.get("heatmap") or [],
        "scan": scan_row(run_dir, video_id),
        "statuses": statuses,
        "api_calls": calls,
        "estimated_quota_units": sum(int(c.get("quota_units", 0)) for c in calls),
    }
    (out / "reference.json").write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "comments.json").write_text(json.dumps(comments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "signals.json").write_text(json.dumps(signals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    study = out / "study.md"
    if not study.exists():  # never overwrite a written study
        study.write_text(study_template(reference), encoding="utf-8")

    print(json.dumps({
        "study_dir": str(out),
        "title": reference["title"],
        "views": reference["views"],
        "comments_read": len(comments),
        "transcript_segments": len(segments),
        "statuses": statuses,
        "estimated_quota_units": reference["estimated_quota_units"],
        "next": f"read signals.json, transcript.txt and thumbnail.jpg, then write {study}",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
