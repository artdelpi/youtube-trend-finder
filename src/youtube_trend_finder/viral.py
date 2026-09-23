"""Viral-recycle lane: recent breakout videos in a niche, and why they broke out.

The trend lane asks what a niche is publishing. This lane asks a narrower
question: which *single* recent video in the niche outran everything its own
channel normally does, is it a commentary-family video another channel could
answer with its own film, and what in it did the audience actually respond to.

Every number here is local code over YouTube API data (the `collector_*`
boundary). The recyclability verdict and the reading of the comments stay
agent judgment (`codex_*`); the helpers only screen and sort.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import math
import re
import statistics
import urllib.error
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from youtube_trend_finder.collector import QUOTA_COST, parse_date, youtube_get


# --- thresholds ------------------------------------------------------------
# Views against the channel's own median: 20x saturates the outlier component,
# 5x is a breakout and 2x a strong video. Below 2x a big channel is doing big
# channel numbers, which says nothing about the subject.
OUTLIER_FULL = 20.0
BREAKOUT_RATIO = 5.0
STRONG_RATIO = 2.0
# Views per hour at which the velocity component saturates.
VELOCITY_FULL = 20_000.0
# Comments per view at which the discussion component saturates. A commentary
# video that sets its comment section arguing is worth more to this lane than
# one that is only watched.
DISCUSSION_FULL = 0.005
# Half-life-like decay for recency, in days: a recycle is worth most while the
# reference is still being recommended.
RECENCY_DAYS = 14.0
VIRAL_WEIGHTS = {"outlier": 0.40, "velocity": 0.30, "recency": 0.15, "discussion": 0.15}
# Uploads younger than this have not settled, so they stay out of a baseline.
BASELINE_MIN_AGE_HOURS = 72.0
SHORT_MAX_SECONDS = 60
LONG_FORM_MIN_SECONDS = 180

# A title may share this much of its content vocabulary with the reference
# title, no more; and no proposal text may share a run of this many words with
# the reference transcript.
TITLE_OVERLAP_MAX = 0.5
TRANSCRIPT_NGRAM = 8


# --- format screen ---------------------------------------------------------
# Commentary-family formats a second channel can answer with its own film.
# Strong patterns decide on their own; weak ones only raise a row to review.
RECYCLABLE = {
    "theory": (
        ("strong", r"\btheor(?:y|ies)\b|\bexplained\b|\blore\b|\bhidden meaning|\bdecoded\b|"
                   r"\biceberg\b|\bending explained\b|\bwhat really happened\b"),
        ("weak", r"\bmystery\b|\bsecret\b|\bthe truth\b"),
    ),
    "compilation": (
        ("strong", r"\bcompilation\b|\btop \d+\b|\btier list\b|\branking\b|\branked\b|"
                   r"\bmost (?:disturbing|terrifying|insane|unhinged|cursed)\b|"
                   r"\b(?:scariest|creepiest|craziest|darkest|weirdest)\b"),
        ("weak", r"\bevery\b|\bworst\b|\bbest\b|\bmoments\b"),
    ),
    "commentary": (
        ("strong", r"(?<!no )\bcommentary\b|\breview\b|\bcritique\b|\brant\b|\bthe problem with\b|"
                   r"\bis ruining\b|\bdownfall\b|\brise and fall\b|\bcontroversy\b|"
                   r"\bdrama\b|\bexposed\b|\bexposing\b|\bi (?:watched|played|read|spent|tried)\b|"
                   r"\breact(?:s|ing|ion)\b|\bbreakdown\b"),
        ("weak", r"\bwhy\b|\bsituation\b|\bresponse\b|\bis (?:bad|dead|over)\b"),
    ),
    "documentary": (
        ("strong", r"\bdocumentary\b|\bthe (?:full |untold |true )?story of\b|\bhistory of\b|"
                   r"\bwhat happened to\b|\binvestigat\w*\b|\bdeep dive\b|\brabbit hole\b|"
                   r"\btimeline\b|\buntold\b|\bunsolved\b"),
        ("weak", r"\bcase\b|\bstory\b|\bhow\b"),
    ),
    "essay": (
        ("strong", r"\bvideo essay\b|\bessay\b|\banalysis\b|\banaly[sz]ing\b|\bpsychology of\b"),
        ("weak", r"\bwhat .+ gets wrong\b|\bunderstanding\b"),
    ),
}
# Original works, official promotion and performances: there is nothing to
# answer, only a work to comment on (which is the trend lane's job).
ORIGINAL_WORK = {
    "official-promo": r"\btrailer\b|\bteaser\b|\bofficial (?:video|audio|clip)\b|\bfirst look\b",
    "music": r"\bmusic video\b|\blyric video\b|\blyrics\b|\bost\b|\bsoundtrack\b|\bcover song\b|"
             r"\bremix\b|\bfull album\b",
    "original-work": r"\bshort film\b|\banimated short\b|\banimation\b|\bepisode \d+\b|\bep\.? ?\d+\b|"
                     r"\bpilot\b|\bfull (?:\w+ )?(?:movie|film)\b|\bseason \d+\b",
    "gameplay": r"\bgameplay\b|\bwalkthrough\b|\blet'?s play\b|\bno commentary\b|\bfull game\b|"
                r"\blongplay\b|\bspeedrun\b",
    "performance": r"\basmr\b|\bmukbang\b|\bvlog\b|\bprank\b",
    "primary-material": r"\b(?:full |exclusive )?interview\b|\bdeposition\b|\bsentencing\b|\bhearing\b",
    "news-report": r"\bbreaking news\b|\blive:|\bnews conference\b|\bpress conference\b|\bbodycam\b|"
                   r"\bfootage\b",
}


def _screen_text(row: Mapping[str, Any]) -> str:
    title = str(row.get("api_title") or row.get("title") or "")
    tags = str(row.get("api_tags") or "").replace("|", " ")
    description = str(row.get("api_description") or row.get("description") or "")[:300]
    return f"{title} \n {tags} \n {description}".lower()


def classify_format(row: Mapping[str, Any]) -> dict[str, str]:
    """Screen one video for the recycle lane. A screen, not a verdict.

    `eligible` needs a strong commentary-family signal in the title, tags or
    the opening of the description. `rejected` needs an original-work signal
    and no commentary signal at all - "trailer breakdown" is commentary about a
    trailer and stays eligible. Everything else is `needs-review`, which the
    agent settles from the transcript.
    """

    title = str(row.get("api_title") or row.get("title") or "").lower()
    text = _screen_text(row)
    try:
        duration = int(float(row.get("api_duration_seconds") or row.get("duration_seconds") or 0))
    except (TypeError, ValueError):
        duration = 0

    strong: dict[str, list[str]] = {}
    weak: dict[str, list[str]] = {}
    strong_in_title = False
    for family, patterns in RECYCLABLE.items():
        for strength, pattern in patterns:
            # Weak words are too common to trust outside the title.
            hits = re.findall(pattern, text if strength == "strong" else title)
            if hits:
                target = strong if strength == "strong" else weak
                target.setdefault(family, []).extend(hits)
                strong_in_title |= strength == "strong" and bool(re.search(pattern, title))
    # Original-work words only count in the title: descriptions of commentary
    # videos link trailers and tags list "gameplay" as a matter of routine.
    original = {name: re.findall(pattern, title) for name, pattern in ORIGINAL_WORK.items()}
    original = {name: hits for name, hits in original.items() if hits}

    notes: list[str] = []
    if 0 < duration <= SHORT_MAX_SECONDS or "#shorts" in text:
        notes.append(f"short-form ({duration}s)")
    elif 0 < duration < LONG_FORM_MIN_SECONDS:
        notes.append(f"under {LONG_FORM_MIN_SECONDS}s ({duration}s)")
    if original:
        notes.append("about " + ", ".join(sorted(original)))

    def _family(found: dict[str, list[str]]) -> str:
        return max(found, key=lambda name: len(found[name]))

    if strong:
        family = _family(strong)
        short = bool(notes) and notes[0].startswith(("short-form", "under"))
        # A title that names an original work, with commentary words only in
        # the description, is usually the work itself described as drama.
        screen = "needs-review" if short or (original and not strong_in_title) else "eligible"
        reason = f"{family} signals: {', '.join(sorted(set(strong[family])))}"
    elif original:
        family = max(original, key=lambda name: len(original[name]))
        screen = "rejected" if not weak else "needs-review"
        reason = f"{family} signals: {', '.join(sorted(set(original[family])))}"
        if weak:
            reason += f"; weak commentary signals: {', '.join(sorted({w for v in weak.values() for w in v}))}"
    elif weak:
        family = _family(weak)
        screen = "needs-review"
        reason = f"weak {family} signals only: {', '.join(sorted(set(weak[family])))}"
    else:
        family = "unknown"
        screen = "needs-review"
        reason = "no format signal in title, tags or description opening"
    if notes:
        reason += "; " + "; ".join(notes)
    return {
        "collector_format_class": family,
        "collector_format_screen": screen,
        "collector_format_reason": reason,
    }


# --- outlier metrics -------------------------------------------------------

def channel_baseline(
    uploads: Iterable[Mapping[str, Any]],
    *,
    exclude_video_id: str = "",
    long_form: bool = True,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Median views of a channel's settled recent uploads, like for like.

    The candidate itself is excluded, so a breakout cannot raise its own bar.
    Shorts and long-form pull different numbers, so a long-form candidate is
    measured against long-form uploads only (and a Short against Shorts).
    """

    now = now or dt.datetime.now(dt.timezone.utc)
    views: list[int] = []
    for upload in uploads:
        if upload.get("video_id") == exclude_video_id:
            continue
        duration = int(upload.get("duration_seconds") or 0)
        if duration and (duration > SHORT_MAX_SECONDS) != long_form:
            continue
        published = upload.get("published_at")
        if published:
            age = (now - parse_date(str(published))).total_seconds() / 3600
            if age < BASELINE_MIN_AGE_HOURS:
                continue
        views.append(int(upload.get("views") or 0))
    return {
        "collector_channel_sample": len(views),
        "collector_channel_median_views": round(statistics.median(views), 1) if views else 0.0,
    }


def breakout_label(outlier_ratio: float | None) -> str:
    if outlier_ratio is None:
        return "unknown"
    if outlier_ratio >= BREAKOUT_RATIO:
        return "breakout"
    if outlier_ratio >= STRONG_RATIO:
        return "strong"
    return "channel-normal"


def viral_components(
    *,
    views: int,
    comments: int,
    age_hours: float,
    outlier_ratio: float | None,
) -> dict[str, float]:
    """Four 0-100 components. An unmeasured outlier ratio scores 0, not 50:
    a video that cannot be compared with its channel has not shown a breakout."""

    velocity = views / max(age_hours, 1.0)
    outlier = 0.0
    if outlier_ratio is not None and outlier_ratio > 1:
        outlier = min(1.0, math.log10(outlier_ratio) / math.log10(OUTLIER_FULL))
    return {
        "outlier": round(100 * outlier, 2),
        "velocity": round(100 * min(1.0, math.log10(max(velocity, 1.0)) / math.log10(VELOCITY_FULL)), 2),
        "recency": round(100 / (1 + (age_hours / 24) / RECENCY_DAYS), 2),
        "discussion": round(100 * min(1.0, (comments / views if views else 0.0) / DISCUSSION_FULL), 2),
    }


def viral_score(components: Mapping[str, float]) -> float:
    total = sum(VIRAL_WEIGHTS.values())
    return round(sum(components[key] * weight for key, weight in VIRAL_WEIGHTS.items()) / total, 2)


def outlier_metrics(
    row: Mapping[str, Any],
    baseline: Mapping[str, Any],
    subscribers: int | None,
) -> dict[str, Any]:
    views = int(float(row.get("api_views") or 0))
    comments = int(float(row.get("api_comments") or 0))
    age_hours = float(row.get("collector_age_hours") or 1)
    median = float(baseline.get("collector_channel_median_views") or 0)
    ratio = round(views / median, 2) if median > 0 else None
    components = viral_components(
        views=views, comments=comments, age_hours=age_hours, outlier_ratio=ratio
    )
    return {
        **baseline,
        "api_channel_subscribers": subscribers if subscribers is not None else "",
        "collector_outlier_ratio": ratio if ratio is not None else "",
        "collector_subscriber_ratio": round(views / subscribers, 3) if subscribers else "",
        "collector_breakout": breakout_label(ratio),
        "collector_viral_components": json.dumps(components),
        "collector_viral_score": viral_score(components),
    }


# --- API calls (1 quota unit each) -------------------------------------------
Getter = Callable[[str, Mapping[str, Any], str], dict[str, Any]]


def _call(get: Getter, endpoint: str, params: Mapping[str, Any], key: str,
          calls: list[dict[str, Any]], detail: str) -> dict[str, Any]:
    method = f"{endpoint}.list"
    try:
        payload = get(endpoint, params, key)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        calls.append({"method": method, "detail": detail, "ok": False,
                      "error": f"HTTP {exc.code}: {body}", "quota_units": QUOTA_COST.get(method, 1)})
        raise
    calls.append({"method": method, "detail": detail, "ok": True,
                  "quota_units": QUOTA_COST.get(method, 1)})
    return payload


def fetch_videos(video_ids: Sequence[str], key: str, calls: list[dict[str, Any]],
                 get: Getter = youtube_get) -> dict[str, dict[str, Any]]:
    """Fresh snippet, statistics and duration, 50 ids per unit."""

    out: dict[str, dict[str, Any]] = {}
    ids = list(dict.fromkeys(video_ids))
    for start in range(0, len(ids), 50):
        chunk = ids[start:start + 50]
        payload = _call(get, "videos", {"part": "snippet,statistics,contentDetails",
                                        "id": ",".join(chunk)}, key, calls, f"{len(chunk)} ids")
        for item in payload.get("items", []):
            out[item["id"]] = item
    return out


def fetch_channel_uploads(channel_ids: Sequence[str], key: str, calls: list[dict[str, Any]],
                          *, per_channel: int = 30, get: Getter = youtube_get,
                          ) -> dict[str, dict[str, Any]]:
    """Subscribers plus the most recent uploads of each channel, with their views."""

    from youtube_trend_finder.collector import parse_duration_seconds

    channels: dict[str, dict[str, Any]] = {}
    ids = list(dict.fromkeys(cid for cid in channel_ids if cid))
    for start in range(0, len(ids), 50):
        chunk = ids[start:start + 50]
        payload = _call(get, "channels", {"part": "statistics,contentDetails",
                                          "id": ",".join(chunk)}, key, calls, f"{len(chunk)} channels")
        for item in payload.get("items", []):
            stats = item.get("statistics", {})
            hidden = stats.get("hiddenSubscriberCount")
            channels[item["id"]] = {
                "subscribers": None if hidden else int(stats.get("subscriberCount") or 0),
                "uploads": item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", ""),
                "recent": [],
            }
    upload_ids: dict[str, str] = {}
    for channel_id, channel in channels.items():
        if not channel["uploads"]:
            continue
        try:
            payload = _call(get, "playlistItems", {"part": "contentDetails", "playlistId": channel["uploads"],
                                                   "maxResults": min(per_channel, 50)},
                            key, calls, channel_id)
        except urllib.error.HTTPError:
            continue  # recorded in calls; the channel is reported as unmeasured
        for item in payload.get("items", []):
            video_id = item.get("contentDetails", {}).get("videoId")
            if video_id:
                upload_ids[video_id] = channel_id
    details = fetch_videos(list(upload_ids), key, calls, get=get)
    for video_id, channel_id in upload_ids.items():
        item = details.get(video_id)
        if not item:
            continue
        channels[channel_id]["recent"].append({
            "video_id": video_id,
            "views": int(item.get("statistics", {}).get("viewCount") or 0),
            "published_at": item.get("snippet", {}).get("publishedAt", ""),
            "duration_seconds": parse_duration_seconds(item.get("contentDetails", {}).get("duration")),
        })
    return channels


def fetch_comments(video_id: str, key: str, calls: list[dict[str, Any]], *,
                   pages: int = 3, order: str = "relevance",
                   get: Getter = youtube_get) -> tuple[list[dict[str, Any]], str]:
    """Top-level comments as structured rows. Returns (rows, status).

    A disabled comment section is a status, never an empty "nobody cared".
    """

    rows: list[dict[str, Any]] = []
    token = None
    for page in range(1, max(1, pages) + 1):
        params: dict[str, Any] = {"part": "snippet", "videoId": video_id, "maxResults": 100,
                                  "order": order, "textFormat": "plainText"}
        if token:
            params["pageToken"] = token
        try:
            payload = _call(get, "commentThreads", params, key, calls, f"{video_id} {order} p{page}")
        except urllib.error.HTTPError as exc:
            detail = calls[-1].get("error", "") if calls else ""
            if exc.code == 403 and "commentsDisabled" in detail:
                return rows, "comments-disabled"
            raise
        for thread in payload.get("items", []):
            top = thread.get("snippet", {}).get("topLevelComment", {})
            snippet = top.get("snippet", {})
            comment_id = top.get("id", "")
            rows.append({
                "comment_id": comment_id,
                "author": snippet.get("authorDisplayName", ""),
                "text": snippet.get("textDisplay") or snippet.get("textOriginal", ""),
                "likes": int(snippet.get("likeCount") or 0),
                "replies": int(thread.get("snippet", {}).get("totalReplyCount") or 0),
                "published_at": snippet.get("publishedAt", ""),
                "order": order,
                "permalink": f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
            })
        token = payload.get("nextPageToken")
        if not token:
            break
    return rows, "ok"


# --- transcript --------------------------------------------------------------
_CUE_TIME = re.compile(r"(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})\s+-->")
_TAG = re.compile(r"<[^>]+>")


def parse_vtt(text: str) -> list[dict[str, Any]]:
    """Caption cues as [{start, text}], with YouTube's rolling repeats removed.

    Auto-captions repeat the previous line at the top of every cue; emitting a
    line only when it differs from the last emitted line leaves each spoken
    line once.
    """

    segments: list[dict[str, Any]] = []
    last = ""
    start: float | None = None
    for raw in text.splitlines():
        line = raw.strip()
        match = _CUE_TIME.match(line)
        if match:
            hours, minutes, seconds, millis = match.groups()
            start = int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000
            continue
        if start is None or not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        # Authored tracks carry HTML entities (`&nbsp;` at every line end).
        clean = re.sub(r"\s+", " ", html.unescape(_TAG.sub("", line)).replace("\xa0", " ")).strip()
        if not clean or clean == last:
            continue
        segments.append({"start": round(start, 2), "text": clean})
        last = clean
    return segments


def transcript_text(segments: Sequence[Mapping[str, Any]]) -> str:
    return "\n".join(f"[{_clock(seg['start'])}] {seg['text']}" for seg in segments)


def excerpt_at(segments: Sequence[Mapping[str, Any]], start: float, span: float = 25.0) -> str:
    """What was being said at a moment: from 5 s before to `span` after."""

    words = [seg["text"] for seg in segments if start - 5 <= float(seg["start"]) <= start + span]
    return " ".join(words)[:600]


def _clock(seconds: float) -> str:
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


# --- attention -----------------------------------------------------------------
_TIMESTAMP = re.compile(r"(?<![\d:])(?:(\d{1,2}):)?(\d{1,2}):([0-5]\d)(?![\d:])")


def comment_timestamps(text: str, duration: float = 0) -> list[int]:
    out = []
    for hours, minutes, seconds in _TIMESTAMP.findall(text):
        value = int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)
        if not duration or value <= duration:
            out.append(value)
    return out


def timestamp_peaks(comments: Iterable[Mapping[str, Any]], *, duration: float = 0,
                    bin_seconds: int = 30, top: int = 5) -> list[dict[str, Any]]:
    """Moments commenters point at, like-weighted on a log scale so one pinned
    comment cannot outvote forty ordinary ones."""

    bins: dict[int, dict[str, Any]] = {}
    for comment in comments:
        for value in set(comment_timestamps(str(comment.get("text", "")), duration)):
            start = value // bin_seconds * bin_seconds
            entry = bins.setdefault(start, {"start": start, "weight": 0.0, "comments": []})
            entry["weight"] += 1 + math.log10(1 + int(comment.get("likes") or 0))
            entry["comments"].append(comment.get("comment_id", ""))
    ranked = sorted(bins.values(), key=lambda item: item["weight"], reverse=True)[:top]
    for item in ranked:
        item["weight"] = round(item["weight"], 2)
        item["count"] = len(item["comments"])
    return ranked


def heatmap_peaks(heatmap: Sequence[Mapping[str, Any]] | None, *, top: int = 5,
                  min_gap: float = 20.0) -> list[dict[str, Any]]:
    """Local maxima of YouTube's most-replayed curve, skipping the opening,
    which is high on every video because every viewer starts there."""

    points = [dict(p) for p in (heatmap or []) if "start_time" in p and "value" in p]
    if len(points) < 3:
        return []
    end = float(points[-1].get("end_time") or points[-1]["start_time"])
    skip = max(10.0, 0.03 * end)
    maxima = [
        points[i] for i in range(1, len(points) - 1)
        if float(points[i]["start_time"]) >= skip
        and points[i]["value"] >= points[i - 1]["value"] and points[i]["value"] >= points[i + 1]["value"]
    ]
    chosen: list[dict[str, Any]] = []
    for point in sorted(maxima, key=lambda p: p["value"], reverse=True):
        if all(abs(float(point["start_time"]) - float(c["start_time"])) >= min_gap for c in chosen):
            chosen.append(point)
        if len(chosen) == top:
            break
    return [{"start": round(float(p["start_time"]), 1), "end": round(float(p.get("end_time") or 0), 1),
             "value": round(float(p["value"]), 3)} for p in chosen]


# --- comment signals -----------------------------------------------------------
# Lexical markers, not sentiment scores. They sort comments into piles for the
# agent to read; the reading is the analysis.
MARKERS = {
    "praise": r"\bbest video\b|\bunderrated\b|\bfinally someone\b|\bthank you for\b|\bmasterpiece\b|"
              r"\bchills\b|\bnew sub\b|\bsubscribed\b|\bso well (?:done|made|put)\b|\bclicked so fast\b|"
              r"\bdeserves more\b|\bneeded this\b|\bperfectly (?:said|put)\b|\bthis is why\b",
    "criticism": r"\bclickbait\b|\bmisinformation\b|\bnot true\b|\bincorrect\b|\bwrong\b|\blazy\b|"
                 r"\bstole\b|\bstolen\b|\bripped off\b|\bcopied\b|\bai voice\b|\bai generated\b|"
                 r"\bchatgpt\b|\btoo long\b|\bdragged\b|\bbiased\b|\bmisleading\b",
    "correction": r"\bactually\b|\bcorrection\b|\bsmall (?:mistake|error)\b|\bfun fact\b|"
                  r"\bfor context\b|\bto clarify\b",
    "request": r"\bpart 2\b|\bpart two\b|\bdo a video\b|\bmake a video\b|\byou should (?:cover|talk|do)\b|"
               r"\byou forgot\b|\byou missed\b|\bwhat about\b|\bno one (?:talks|is talking)\b|"
               r"\bnobody (?:talks|mentions)\b|\bdidn'?t mention\b|\bshould have mentioned\b|\bcover\b.+\bnext\b",
    "personal": r"\bi remember\b|\bas someone who\b|\bi was there\b|\bhappened to me\b|\bmy (?:friend|brother|sister|kid|son|daughter)\b|"
                r"\bi used to\b|\bi grew up\b",
}


def _ngrams(tokens: Sequence[str], size: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[i:i + size]) for i in range(len(tokens) - size + 1)}


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text.lower())


def quoted_lines(comments: Iterable[Mapping[str, Any]], segments: Sequence[Mapping[str, Any]],
                 *, size: int = 6, top: int = 15) -> list[dict[str, Any]]:
    """Transcript lines the audience repeated back in comments.

    A comment that shares a run of `size` words with the narration is quoting
    it - that is the sentence that landed.
    """

    # Slide over the whole transcript: a quoted sentence often spans two cues.
    index: dict[tuple[str, ...], float] = {}
    flat: list[tuple[str, float]] = [(w, float(seg["start"])) for seg in segments for w in words(str(seg["text"]))]
    for i in range(len(flat) - size + 1):
        index.setdefault(tuple(w for w, _ in flat[i:i + size]), flat[i][1])
    hits: list[dict[str, Any]] = []
    for comment in comments:
        tokens = words(str(comment.get("text", "")))
        found = [(gram, index[gram]) for gram in _ngrams(tokens, size) if gram in index]
        if found:
            gram, start = min(found, key=lambda item: item[1])
            hits.append({"comment_id": comment.get("comment_id", ""), "likes": int(comment.get("likes") or 0),
                         "at": _clock(start), "start": start, "phrase": " ".join(gram),
                         "text": str(comment.get("text", ""))[:300]})
    hits.sort(key=lambda item: item["likes"], reverse=True)
    return hits[:top]


def comment_signals(comments: Sequence[Mapping[str, Any]], segments: Sequence[Mapping[str, Any]] = (),
                    *, duration: float = 0, examples: int = 8) -> dict[str, Any]:
    """Piles for the agent to read, each with counts, like totals and the most
    liked examples. Questions are their own pile: an unanswered question in a
    viral comment section is the gap a second film can fill."""

    piles: dict[str, list[Mapping[str, Any]]] = {name: [] for name in [*MARKERS, "question"]}
    for comment in comments:
        text = str(comment.get("text", "")).lower()
        for name, pattern in MARKERS.items():
            if re.search(pattern, text):
                piles[name].append(comment)
        if "?" in text:
            piles["question"].append(comment)
    total_likes = sum(int(c.get("likes") or 0) for c in comments) or 1
    summary = {}
    for name, rows in piles.items():
        ranked = sorted(rows, key=lambda c: int(c.get("likes") or 0), reverse=True)
        likes = sum(int(c.get("likes") or 0) for c in rows)
        summary[name] = {
            "count": len(rows),
            "share_of_comments": round(len(rows) / len(comments), 3) if comments else 0.0,
            "share_of_likes": round(likes / total_likes, 3),
            "examples": [{"comment_id": c.get("comment_id", ""), "likes": int(c.get("likes") or 0),
                          "text": str(c.get("text", ""))[:300]} for c in ranked[:examples]],
        }
    return {
        "comments_read": len(comments),
        "piles": summary,
        "top_comments": [{"comment_id": c.get("comment_id", ""), "likes": int(c.get("likes") or 0),
                          "replies": int(c.get("replies") or 0), "text": str(c.get("text", ""))[:400]}
                         for c in sorted(comments, key=lambda c: int(c.get("likes") or 0), reverse=True)[:25]],
        "timestamp_peaks": [
            {**peak, "at": _clock(peak["start"]), "said": excerpt_at(segments, peak["start"])}
            for peak in timestamp_peaks(comments, duration=duration)
        ],
        "quoted_lines": quoted_lines(comments, segments) if segments else [],
    }


# --- proposal contract -----------------------------------------------------------
TREND_LANE = "trend"
RECYCLE_LANE = "viral-recycle"
# Extra fields a viral-recycle proposal must carry, on top of the profile's.
RECYCLE_FIELDS = (
    "reference_video_url",
    "reference_video_title",
    "reference_channel",
    "reference_published_at",
    "reference_views",
    "reference_outlier_ratio",
    "reference_format",
    "reference_study",
    "recycle_hits",
    "recycle_misses",
    "audience_sentiment",
    "recycle_originality",
)
STUDY_PENDING = "STUDY PENDING"


# --- originality guard -----------------------------------------------------------
_STOP = {"a", "an", "and", "in", "of", "on", "the", "to", "with", "is", "it", "this", "that",
         "for", "at", "by", "from", "i", "you", "we", "they", "was", "are", "be"}


def title_overlap(title: str, reference: str) -> float:
    """Jaccard overlap of content words; 1.0 is the same title reworded."""

    a = {w for w in words(title) if w not in _STOP}
    b = {w for w in words(reference) if w not in _STOP}
    return round(len(a & b) / len(a | b), 3) if a and b else 0.0


def shared_runs(text: str, reference_transcript: str, size: int = TRANSCRIPT_NGRAM) -> list[str]:
    """Runs of `size` words the proposal shares with the reference transcript."""

    ref = _ngrams(words(re.sub(r"\[\d+:\d{2}(?::\d{2})?\]", " ", reference_transcript)), size)
    return sorted({" ".join(gram) for gram in _ngrams(words(text), size) if gram in ref})


def originality_errors(row: Mapping[str, Any], reference_title: str,
                       reference_transcript: str = "") -> list[str]:
    errors = []
    for value in [str(row.get("title", "")), *_split_titles(row.get("alternate_titles"))]:
        overlap = title_overlap(value, reference_title)
        if overlap > TITLE_OVERLAP_MAX:
            errors.append(f"title {value!r} shares {overlap:.0%} of its words with the reference title")
    if reference_transcript:
        for field in ("title", "hook", "thesis", "angle", "structure"):
            runs = shared_runs(str(row.get(field, "")), reference_transcript)
            if runs:
                errors.append(f"{field} repeats the reference transcript: {runs[0]!r}")
    return errors


def _split_titles(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value or "").strip()
    if text.startswith("["):
        try:
            return [str(item) for item in json.loads(text)]
        except json.JSONDecodeError:
            pass
    return [part.strip() for part in text.split("|") if part.strip()]
