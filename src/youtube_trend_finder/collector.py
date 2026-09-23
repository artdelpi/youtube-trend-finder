from __future__ import annotations

import csv
import datetime as dt
import json
import math
import os
import re
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


BASE_URL = "https://www.googleapis.com/youtube/v3"
ENV_KEYS = ("YOUTUBE_API_KEY", "API_KEY_YOUTUBE_V3", "YOUTUBE_API_KEY_V3")
# YouTube Data API v3 quota units per call. search.list is 100x more expensive
# than videos.list, which dominates the cost of a collection run.
QUOTA_COST = {"search.list": 100, "videos.list": 1}


def load_api_key(path: str | Path = ".env") -> str:
    env_path = Path(path)
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if "=" not in stripped or stripped.startswith("#"):
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

    for key in ENV_KEYS:
        value = os.environ.get(key)
        if value:
            return value

    raise RuntimeError(f"Missing API key in .env: {', '.join(ENV_KEYS)}")


def youtube_get(endpoint: str, params: Mapping[str, Any], key: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({**params, "key": key})
    url = f"{BASE_URL}/{endpoint}?{query}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def iso_utc(value: dt.datetime) -> str:
    return (
        value.astimezone(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_date(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_duration_seconds(value: str | None) -> int:
    match = re.fullmatch(
        r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?",
        value or "",
    )
    if not match:
        return 0
    days, hours, minutes, seconds = [int(part or 0) for part in match.groups()]
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "trend"


def chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def trend_score(views: int, likes: int, comments: int, age_hours: float) -> float:
    engagement = (likes + comments) / views if views else 0
    velocity = views / max(age_hours, 1)
    return velocity * math.log10(max(views, 10)) * (1 + min(engagement, 0.25) * 4)


def build_video_row(
    video_id: str,
    payload: Mapping[str, Any],
    now: dt.datetime,
) -> dict[str, Any]:
    item = payload["item"]
    snippet = item.get("snippet", {})
    statistics = item.get("statistics", {})
    content_details = item.get("contentDetails", {})
    published = parse_date(snippet["publishedAt"])
    age_hours = max((now - published).total_seconds() / 3600, 1)
    views = int(statistics.get("viewCount", 0))
    likes = int(statistics.get("likeCount", 0))
    comments = int(statistics.get("commentCount", 0))
    engagement = (likes + comments) / views if views else 0
    velocity = views / age_hours

    return {
        "api_video_id": video_id,
        "api_url": f"https://www.youtube.com/watch?v={video_id}",
        "api_title": snippet.get("title", ""),
        "api_channel": snippet.get("channelTitle", ""),
        "api_channel_id": snippet.get("channelId", ""),
        "api_published_at": iso_utc(published),
        "api_description": snippet.get("description", ""),
        "api_tags": "|".join(snippet.get("tags", [])),
        "api_views": views,
        "api_likes": likes,
        "api_comments": comments,
        "api_duration_seconds": parse_duration_seconds(content_details.get("duration")),
        "collector_keywords_matched": "|".join(sorted(set(payload["keywords"]))),
        "collector_age_hours": round(age_hours, 2),
        "collector_views_per_hour": round(velocity, 2),
        "collector_engagement_rate": round(engagement, 5),
        "collector_trend_score": round(
            trend_score(views=views, likes=likes, comments=comments, age_hours=age_hours),
            2,
        ),
    }


def write_outputs(
    topic: str,
    rows: list[dict[str, Any]],
    report: Mapping[str, Any],
    out_dir: str | Path,
    timestamped_output: bool = True,
) -> tuple[Path, Path]:
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path(out_dir) / timestamp if timestamped_output else Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    base = output_dir / slugify(topic)
    csv_path = base.with_name(base.name + "-api_videos.csv")
    json_path = base.with_name(base.name + "-api_payload.json")
    if not timestamped_output and (csv_path.exists() or json_path.exists()):
        raise FileExistsError(f"Collection already exists in {output_dir}; use a new batch directory")
    fields = list(rows[0].keys()) if rows else ["api_video_id"]

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return csv_path, json_path


def collect(
    topic: str,
    keywords: list[str],
    days: int,
    region: str = "US",
    language: str = "en",
    max_results_per_keyword: int | None = None,
    max_results_per_page: int = 50,
    pages_per_keyword: int = 2,
    out_dir: str | Path = "outputs",
    timestamped_output: bool = True,
) -> dict[str, Any]:
    if not timestamped_output:
        for suffix in ("-api_videos.csv", "-api_payload.json", "-profile_context.json"):
            if (Path(out_dir) / (slugify(topic) + suffix)).exists():
                raise FileExistsError(f"Collection already exists in {out_dir}; use a new batch directory")
    key = load_api_key()
    now = dt.datetime.now(dt.timezone.utc)
    published_after = iso_utc(now - dt.timedelta(days=days))
    calls: list[dict[str, Any]] = []
    found: dict[str, dict[str, Any]] = {}
    max_results_per_page = min(max_results_per_keyword or max_results_per_page, 50)
    pages_per_keyword = max(1, pages_per_keyword)
    raw_video_ids = 0

    for keyword in keywords:
        ids: list[str] = []
        page_token = None
        for page in range(1, pages_per_keyword + 1):
            params = {
                "part": "snippet",
                "type": "video",
                "q": keyword,
                "order": "viewCount",
                "publishedAfter": published_after,
                "regionCode": region,
                "relevanceLanguage": language,
                "safeSearch": "moderate",
                "maxResults": max_results_per_page,
            }
            if page_token:
                params["pageToken"] = page_token

            search = youtube_get("search", params, key)
            calls.append(
                {
                    "method": "search.list",
                    "keyword": keyword,
                    "page": page,
                    "quota_units": QUOTA_COST["search.list"],
                }
            )
            ids.extend(
                item["id"]["videoId"]
                for item in search.get("items", [])
                if item.get("id", {}).get("videoId")
            )
            page_token = search.get("nextPageToken")
            if not page_token:
                break

        raw_video_ids += len(ids)
        for chunk_index, video_ids in enumerate(chunks(unique(ids), 50), start=1):
            videos = youtube_get(
                "videos",
                {
                    "part": "snippet,statistics,contentDetails",
                    "id": ",".join(video_ids),
                },
                key,
            )
            calls.append(
                {
                    "method": "videos.list",
                    "keyword": keyword,
                    "chunk": chunk_index,
                    "quota_units": QUOTA_COST["videos.list"],
                }
            )
            for item in videos.get("items", []):
                found.setdefault(item["id"], {"keywords": [], "item": item})[
                    "keywords"
                ].append(keyword)

    rows = [build_video_row(video_id, payload, now) for video_id, payload in found.items()]
    rows.sort(key=lambda row: row["collector_trend_score"], reverse=True)

    report = {
        "topic": topic,
        "keywords": keywords,
        "days": days,
        "published_after": published_after,
        "region": region,
        "language": language,
        "max_results_per_page": max_results_per_page,
        "pages_per_keyword": pages_per_keyword,
        "max_search_results_per_keyword": max_results_per_page * pages_per_keyword,
        "raw_video_ids_found": raw_video_ids,
        "unique_videos_found": len(rows),
        "api_calls": calls,
        "estimated_youtube_api_cost_usd": 0,
        "estimated_quota_units": sum(call["quota_units"] for call in calls),
        "rows": rows,
    }
    csv_path, json_path = write_outputs(topic, rows, report, out_dir, timestamped_output)
    return {"csv": str(csv_path), "json": str(json_path), "report": report}
