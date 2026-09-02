from __future__ import annotations

import html
import json
import math
import re
import statistics
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from youtube_trend_finder.collector import chunks, parse_duration_seconds, youtube_get


TAG = re.compile(r"<[^>]+>")
TIMESTAMP = re.compile(r"^\d{2}:\d{2}(?::\d{2})?\.\d{3}\s+-->")
WORD = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?")


def collect_catalog(handle: str, key: str) -> dict[str, Any]:
    """Traverse the full public uploads playlist and fetch batched metadata."""

    clean_handle = handle.lstrip("@").strip()
    channel_response = youtube_get(
        "channels",
        {"part": "snippet,contentDetails,statistics", "forHandle": clean_handle},
        key,
    )
    channels = channel_response.get("items", [])
    if not channels:
        raise RuntimeError(f"YouTube channel not found: @{clean_handle}")
    channel = channels[0]
    uploads = channel["contentDetails"]["relatedPlaylists"]["uploads"]

    playlist_items: list[Mapping[str, Any]] = []
    page_token: str | None = None
    pages = 0
    while True:
        params: dict[str, Any] = {
            "part": "snippet,contentDetails,status",
            "playlistId": uploads,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token
        response = youtube_get("playlistItems", params, key)
        pages += 1
        playlist_items.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    video_ids = [item["contentDetails"]["videoId"] for item in playlist_items]
    details: dict[str, Mapping[str, Any]] = {}
    for group in chunks(video_ids, 50):
        response = youtube_get(
            "videos",
            {
                "part": "snippet,statistics,contentDetails,status,liveStreamingDetails",
                "id": ",".join(group),
            },
            key,
        )
        details.update({item["id"]: item for item in response.get("items", [])})

    publications: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for position, item in enumerate(playlist_items, start=1):
        video_id = item["contentDetails"]["videoId"]
        detail = details.get(video_id)
        playlist_snippet = item.get("snippet", {})
        if detail is None:
            failures.append({"video_id": video_id, "reason": "videos.list returned no item"})
            publications.append(
                {
                    "position": position,
                    "video_id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "title": playlist_snippet.get("title", ""),
                    "publication_type": "unknown",
                    "published_at": item.get("contentDetails", {}).get("videoPublishedAt"),
                    "duration_seconds": None,
                    "view_count": None,
                    "like_count": None,
                    "comment_count": None,
                }
            )
            continue

        snippet = detail.get("snippet", {})
        statistics_payload = detail.get("statistics", {})
        live = detail.get("liveStreamingDetails")
        publications.append(
            {
                "position": position,
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": snippet.get("title", playlist_snippet.get("title", "")),
                "publication_type": "live" if live else "video",
                "published_at": snippet.get("publishedAt"),
                "duration_seconds": parse_duration_seconds(
                    detail.get("contentDetails", {}).get("duration")
                ),
                "view_count": int(statistics_payload["viewCount"])
                if statistics_payload.get("viewCount") is not None
                else None,
                "like_count": int(statistics_payload["likeCount"])
                if statistics_payload.get("likeCount") is not None
                else None,
                "comment_count": int(statistics_payload["commentCount"])
                if statistics_payload.get("commentCount") is not None
                else None,
            }
        )

    return {
        "schema_version": 1,
        "channel": {
            "id": channel["id"],
            "handle": f"@{clean_handle}",
            "title": channel.get("snippet", {}).get("title", ""),
            "url": f"https://www.youtube.com/@{clean_handle}",
            "uploads_playlist": uploads,
            "reported_video_count": int(channel.get("statistics", {}).get("videoCount", 0)),
        },
        "collection": {
            "playlist_pages_traversed": pages,
            "publications_found": len(publications),
            "metadata_failures": failures,
        },
        "publications": publications,
    }


def _merge_words(existing: list[str], incoming: list[str]) -> None:
    maximum = min(40, len(existing), len(incoming))
    overlap = 0
    for size in range(maximum, 0, -1):
        if [item.lower() for item in existing[-size:]] == [
            item.lower() for item in incoming[:size]
        ]:
            overlap = size
            break
    existing.extend(incoming[overlap:])


def read_vtt(path: str | Path) -> str:
    """Return full caption text while removing YouTube rolling-caption overlap."""

    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    cues: list[list[str]] = []
    current: list[str] = []
    for raw in lines:
        line = raw.strip()
        if TIMESTAMP.match(line):
            if current:
                cues.append(current)
                current = []
            continue
        if not line or line == "WEBVTT" or line.startswith(("Kind:", "Language:", "NOTE")):
            continue
        clean = html.unescape(TAG.sub("", line)).strip()
        if clean:
            current = WORD.findall(clean)
    if current:
        cues.append(current)

    words: list[str] = []
    for cue in cues:
        _merge_words(words, cue)
    return " ".join(words)


def _share(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def analyze_titles(publications: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(publications)
    titles = [str(item.get("title", "")).strip() for item in rows]
    titles = [title for title in titles if title]
    word_counts = [len(WORD.findall(title)) for title in titles]
    char_counts = [len(title) for title in titles]
    total = len(titles)
    recurring = {
        "most_disturbing_crimes": sum(
            title.lower().startswith(("most disturbing crimes", "the most disturbing crimes"))
            for title in titles
        ),
        "community": sum("community" in title.lower() for title in titles),
        "iceberg": sum("iceberg" in title.lower() for title in titles),
        "disturbing": sum("disturbing" in title.lower() for title in titles),
        "worst": sum("worst" in title.lower() for title in titles),
        "numeric_opener": sum(bool(re.match(r"^\d+\b", title)) for title in titles),
        "parenthetical_scope": sum(bool(re.search(r"\([^)]*(?:long|documentary)[^)]*\)", title, re.I)) for title in titles),
        "happened": sum("happened" in title.lower() for title in titles),
        "place_or_platform": sum(
            bool(re.search(r"\b(?:at|on)\s+[A-Z]", title)) for title in titles
        ),
    }
    common_words = Counter(
        word.lower()
        for title in titles
        for word in WORD.findall(title)
        if word.lower() not in {"a", "an", "and", "at", "in", "of", "on", "the", "that", "to"}
    )
    views = sorted(
        int(item["view_count"])
        for item in rows
        if isinstance(item.get("view_count"), int)
    )
    threshold = views[max(0, math.ceil(len(views) * 0.75) - 1)] if views else 0
    top_titles = [
        str(item.get("title", ""))
        for item in rows
        if isinstance(item.get("view_count"), int) and item["view_count"] >= threshold
    ]
    top_forms = {
        "most_disturbing_crimes": sum(
            title.lower().startswith(("most disturbing crimes", "the most disturbing crimes"))
            for title in top_titles
        ),
        "community": sum("community" in title.lower() for title in top_titles),
        "iceberg": sum("iceberg" in title.lower() for title in top_titles),
        "disturbing": sum("disturbing" in title.lower() for title in top_titles),
        "numeric_opener": sum(bool(re.match(r"^\d+\b", title)) for title in top_titles),
    }
    return {
        "titles_analyzed": total,
        "word_count": {
            "median": statistics.median(word_counts) if word_counts else 0,
            "minimum": min(word_counts, default=0),
            "maximum": max(word_counts, default=0),
        },
        "character_count": {
            "median": statistics.median(char_counts) if char_counts else 0,
            "minimum": min(char_counts, default=0),
            "maximum": max(char_counts, default=0),
        },
        "question_mark_share": _share(sum("?" in title for title in titles), total),
        "exclamation_mark_share": _share(sum("!" in title for title in titles), total),
        "colon_share": _share(sum(":" in title for title in titles), total),
        "first_person_share": _share(
            sum(bool(re.search(r"\b(?:i|my|we|our)\b", title, re.I)) for title in titles), total
        ),
        "second_person_share": _share(
            sum(bool(re.search(r"\b(?:you|your)\b", title, re.I)) for title in titles), total
        ),
        "recurring_forms": {
            key: {"count": value, "share": _share(value, total)}
            for key, value in recurring.items()
        },
        "view_association": {
            "method": "Descriptive only; views also depend on topic, age, distribution, and packaging.",
            "top_quartile_threshold": threshold,
            "top_quartile_count": len(top_titles),
            "top_quartile_form_share": {
                key: _share(value, len(top_titles)) for key, value in top_forms.items()
            },
        },
        "common_content_words": common_words.most_common(30),
    }


def _contains(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, re.IGNORECASE))


def analyze_transcripts(
    publications: list[dict[str, Any]], cache_dir: str | Path
) -> dict[str, Any]:
    cache = Path(cache_dir)
    per_video: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    phrase_patterns = {
        "first_person": r"\b(?:i|i'm|i've|i'll|me|my|we|we're|we've|our)\b",
        "second_person": r"\b(?:you|you're|you've|you'll|your)\b",
        "evidence_language": r"\b(?:according to|police|court|report(?:ed)?|article|records?|evidence|investigat(?:e|ed|ion))\b",
        "sequence_language": r"\b(?:first|next|later|eventually|finally|moving on|with that|before we)\b",
        "case_reset": r"\b(?:next case|next story|moving on|things (?:only |just )?get (?:worse|darker)|cases (?:only |just )?get (?:worse|darker))\b",
        "commentary_language": r"\b(?:obviously|honestly|of course|ironically|ridiculous|unfortunately|somehow|thankfully)\b",
        "analogy_or_scenario": r"\b(?:imagine|picture this|think of it|like a|as if)\b",
        "sponsor": r"\b(?:sponsor(?:ed)?|thanks to .* for sponsoring)\b",
        "cta": r"\b(?:subscribe|like the video|leave a comment|comment below|thanks for watching|see you next)\b",
    }
    transcript_word_counts: list[int] = []
    pattern_video_counts = Counter()
    hook_counts = Counter()

    for publication in publications:
        video_id = publication["video_id"]
        choices = [
            cache / f"{video_id}.en-orig.vtt",
            cache / f"{video_id}.en.vtt",
        ]
        transcript_path = next((path for path in choices if path.is_file()), None)
        if transcript_path is None:
            publication["transcript"] = {
                "status": "unavailable",
                "reason": "No accessible English captions were returned by yt-dlp.",
            }
            missing.append(
                {
                    "video_id": video_id,
                    "title": publication.get("title", ""),
                    "reason": publication["transcript"]["reason"],
                }
            )
            continue

        text = read_vtt(transcript_path)
        words = WORD.findall(text)
        lower = text.lower()
        opening = " ".join(words[:180]).lower()
        closing = " ".join(words[-250:]).lower()
        transcript_word_counts.append(len(words))
        metrics = {
            key: len(re.findall(pattern, lower, re.IGNORECASE))
            for key, pattern in phrase_patterns.items()
        }
        for key, value in metrics.items():
            if value:
                pattern_video_counts[key] += 1

        hook_types = {
            "declarative_collection_promise": _contains(
                opening, r"^(?:these are|this is (?:a |the )?(?:mega )?compilation)\b"
            ),
            "escalation_promise": _contains(
                opening, r"\b(?:as the video|as this video|cases|things).{0,45}(?:worse|darker|horrifying|terrifying)\b"
            ),
            "question_or_direct_address": _contains(
                opening, r"\b(?:have you|did you|do you|what|why|how|imagine|picture this)\b"
            ),
            "case_or_subject_first": _contains(
                opening, r"\b(?:in \d{4}|on [a-z]+ \d+|this is|the .* community|the .* case)\b"
            ),
            "scope_preview": _contains(
                opening, r"\b(?:today|in this video|we(?:'re| are) going|we(?:'ll| will)|we have \d+)\b"
            ),
            "greeting": _contains(opening, r"^(?:hey|hello|what's up|welcome)\b"),
            "first_case_or_date_within_opening": _contains(
                opening,
                r"\b(?:on (?:january|february|march|april|may|june|july|august|september|october|november|december)|in (?:19|20)\d{2}|it(?:'s| is) (?:19|20)\d{2})\b",
            ),
        }
        for key, value in hook_types.items():
            if value:
                hook_counts[key] += 1

        has_closing_cta = _contains(closing, phrase_patterns["cta"])
        publication["transcript"] = {
            "status": "available",
            "cache_file": transcript_path.name,
            "word_count": len(words),
        }
        per_video.append(
            {
                "video_id": video_id,
                "word_count": len(words),
                "hook_types": [key for key, value in hook_types.items() if value],
                "closing_cta": has_closing_cta,
                "signal_counts": metrics,
            }
        )

    transcript_count = len(per_video)
    total_words = sum(transcript_word_counts)
    signal_totals = {
        key: sum(item["signal_counts"][key] for item in per_video)
        for key in phrase_patterns
    }
    return {
        "transcripts_obtained": transcript_count,
        "transcripts_unavailable": len(missing),
        "failures": missing,
        "word_count": {
            "total": total_words,
            "median_per_video": statistics.median(transcript_word_counts)
            if transcript_word_counts
            else 0,
            "minimum": min(transcript_word_counts, default=0),
            "maximum": max(transcript_word_counts, default=0),
        },
        "hook_type_video_share": {
            key: _share(value, transcript_count) for key, value in hook_counts.items()
        },
        "recurring_signal_video_share": {
            key: _share(pattern_video_counts[key], transcript_count) for key in phrase_patterns
        },
        "recurring_signal_rate_per_1000_words": {
            key: round(value * 1000 / total_words, 3) if total_words else 0.0
            for key, value in signal_totals.items()
        },
        "closing_cta_share": _share(
            sum(bool(item["closing_cta"]) for item in per_video), transcript_count
        ),
        "per_video_metrics": per_video,
    }


def build_analysis(catalog: dict[str, Any], cache_dir: str | Path) -> dict[str, Any]:
    publications = catalog["publications"]
    return {
        "schema_version": 1,
        "channel": catalog["channel"],
        "coverage": catalog["collection"],
        "titles": analyze_titles(publications),
        "transcripts": analyze_transcripts(publications, cache_dir),
    }


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
