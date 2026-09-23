from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any


WORD = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?")
MEANINGLESS_TITLE_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "for",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "was",
    "with",
}

TITLE_MECHANICS: dict[str, str] = {
    "danger_collection": r"\b(?:disturbing|horrifying|deadliest|darkest|crimes?|deaths?|horrors?)\b",
    "ranked_or_exhaustive": r"(?:^|\b)(?:\d+|every|all|best|worst|most|least|kill count|explained)(?:\b|$)",
    "familiar_work_lens": r"\b(?:episode|movie|game|chapter|story|show)\s+(?:about|on)\b",
    "answerable_mystery": r"^(?:what|why|how|who|where|when|can|could|did|does|has|is|was|will)\b|\?",
    "reveal_or_reversal": r"\b(?:actually|hidden|lost|secret|wrong|solved|happened|needed|still|truth)\b",
    "challenge_or_survival": r"\b(?:escape|fight|last to leave|survive|survived|trapped|stranded|beat|risk)\b",
    "quantified_stakes": r"(?:\$[\d,]+|\b\d[\d,]*(?:\s*(?:days?|hours?|people|kids?|cops?|lbs?))?\b|\bwin\b|\bkeep it\b)",
    "extreme_comparison": r"\b(?:vs\.?|versus|strongest|fastest|biggest|smallest|most extreme|\$\d[^\n]*\bvs\b)\b",
    "creator_identity": r"\b(?:who (?:made|created|is behind)|creator (?:of|identity|attribution)|developer behind|person behind|authorship)\b",
}

OPENING_SIGNALS: dict[str, str] = {
    "collection_promise": r"^(?:these are|this is (?:a |the )?(?:mega )?compilation)\b|\b(?:we have|every case|first case|next case)\b",
    "escalation_promise": r"\b(?:get|gets|become|becomes|progressively|only).{0,35}(?:worse|darker|deadlier|horrifying|terrifying)\b",
    "thesis_or_guiding_question": r"\b(?:main point|which raises the question|the question is|what causes|why does|how does|is .* really|we will get into)\b",
    "context_then_explanation": r"\b(?:for context|at this point|we all know|let's start|before moving on|we learn that)\b",
    "rules_or_stakes": r"\b(?:if .* (?:win|lose|get|escape)|wins?|gets nothing|start the timer|until the end|have to|risk|reward)\b",
    "action_first": r"^(?:we(?:'re| are)|behind me|i (?:survived|spent|built)|escape|survive|last to)\b",
    "dated_case_first": r"\b(?:on (?:january|february|march|april|may|june|july|august|september|october|november|december)|in (?:19|20)\d{2}|around \d{1,2})\b",
}

TREND_TEXT_FIELDS = (
    "codex_theme",
    "theme",
    "topic",
    "api_title",
    "api_description",
    "collector_keywords",
    "collector_keywords_matched",
    "reddit_theory_pulse",
)


def _share(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _percentile(values: list[int], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return float(ordered[low])
    return round(ordered[low] + (ordered[high] - ordered[low]) * (index - low), 2)


def classify_title(title: str) -> list[str]:
    """Return reusable packaging mechanics without copying subject wording."""

    return [
        name
        for name, pattern in TITLE_MECHANICS.items()
        if re.search(pattern, title, re.IGNORECASE)
    ]


def analyze_title_surface(publications: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(item) for item in publications if str(item.get("title", "")).strip()]
    titles = [str(item["title"]).strip() for item in rows]
    word_counts = [len(WORD.findall(title)) for title in titles]
    character_counts = [len(title) for title in titles]
    mechanic_counts = Counter(
        mechanic for title in titles for mechanic in classify_title(title)
    )
    viewed = [item for item in rows if isinstance(item.get("view_count"), int)]
    viewed.sort(key=lambda item: int(item["view_count"]), reverse=True)
    top_count = max(1, math.ceil(len(viewed) / 4)) if viewed else 0
    top_rows = viewed[:top_count]
    top_mechanics = Counter(
        mechanic
        for item in top_rows
        for mechanic in classify_title(str(item["title"]))
    )
    return {
        "titles_analyzed": len(titles),
        "word_count": {
            "median": statistics.median(word_counts) if word_counts else 0,
            "p10": _percentile(word_counts, 0.1),
            "p90": _percentile(word_counts, 0.9),
        },
        "character_count": {
            "median": statistics.median(character_counts) if character_counts else 0,
            "p10": _percentile(character_counts, 0.1),
            "p90": _percentile(character_counts, 0.9),
        },
        "question_mark_share": _share(sum("?" in title for title in titles), len(titles)),
        "caps_emphasis_share": _share(
            sum(
                any(len(word) > 1 and word.isupper() for word in WORD.findall(title))
                for title in titles
            ),
            len(titles),
        ),
        "mechanic_share": {
            name: _share(mechanic_counts[name], len(titles)) for name in TITLE_MECHANICS
        },
        "view_association": {
            "method": "Descriptive only; topic, age, thumbnail, audience, and distribution remain confounders.",
            "videos_with_views": len(viewed),
            "top_quartile_count": len(top_rows),
            "top_quartile_mechanic_share": {
                name: _share(top_mechanics[name], len(top_rows)) for name in TITLE_MECHANICS
            },
        },
    }


def analyze_caption_opening(
    title: str, transcript: str, *, excerpt_words: int = 120
) -> dict[str, Any]:
    """Relate a small caption opening to its title promise."""

    words = WORD.findall(transcript)
    opening_words = words[:excerpt_words]
    opening = " ".join(opening_words)
    title_tokens = {
        token.lower()
        for token in WORD.findall(title)
        if token.lower() not in MEANINGLESS_TITLE_WORDS and not token.isdigit()
    }
    opening_tokens = {token.lower() for token in opening_words}
    overlap = sorted(title_tokens & opening_tokens)
    return {
        "excerpt_word_count": len(opening_words),
        "opening_excerpt": opening,
        "title_keyword_recall": round(len(overlap) / len(title_tokens), 4)
        if title_tokens
        else 0.0,
        "title_keywords_repeated": overlap,
        "opening_signals": [
            name
            for name, pattern in OPENING_SIGNALS.items()
            if re.search(pattern, opening, re.IGNORECASE)
        ],
    }


def analyze_presentation_channel(
    channel: Mapping[str, Any],
    publications: Iterable[Mapping[str, Any]],
    caption_texts: Mapping[str, str],
    *,
    excerpt_words: int = 120,
) -> dict[str, Any]:
    rows = [dict(item) for item in publications]
    by_id = {str(item.get("video_id", "")): item for item in rows}
    caption_samples: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for video_id in channel.get("caption_video_ids", []):
        row = by_id.get(str(video_id))
        if row is None:
            failures.append(
                {"video_id": str(video_id), "reason": "Video was outside the collected title window."}
            )
            continue
        transcript = caption_texts.get(str(video_id), "")
        if not transcript:
            failures.append(
                {"video_id": str(video_id), "reason": "No accessible English caption was cached."}
            )
            continue
        caption_samples.append(
            {
                "video_id": str(video_id),
                "title": row["title"],
                "title_mechanics": classify_title(str(row["title"])),
                **analyze_caption_opening(
                    str(row["title"]), transcript, excerpt_words=excerpt_words
                ),
            }
        )

    title_analysis = analyze_title_surface(rows)
    opening_counts = Counter(
        signal for sample in caption_samples for signal in sample["opening_signals"]
    )
    mechanics = title_analysis["mechanic_share"]
    dominant = sorted(mechanics, key=lambda item: (-mechanics[item], item))[:4]
    return {
        "id": channel["id"],
        "url": channel["url"],
        "title_window": len(rows),
        "title_analysis": title_analysis,
        "dominant_title_mechanics": [
            {"mechanic": name, "share": mechanics[name]}
            for name in dominant
            if mechanics[name] > 0
        ],
        "caption_analysis": {
            "requested": len(channel.get("caption_video_ids", [])),
            "obtained": len(caption_samples),
            "opening_excerpt_words": excerpt_words,
            "video_or_audio_downloaded": False,
            "average_title_keyword_recall": round(
                sum(sample["title_keyword_recall"] for sample in caption_samples)
                / len(caption_samples),
                4,
            )
            if caption_samples
            else 0.0,
            "opening_signal_video_share": {
                name: _share(opening_counts[name], len(caption_samples))
                for name in OPENING_SIGNALS
            },
            "samples": caption_samples,
            "failures": failures,
        },
    }


def _trend_text(trend: Mapping[str, Any]) -> str:
    return " ".join(str(trend.get(field, "")) for field in TREND_TEXT_FIELDS).lower()


def _subject_text(trend: Mapping[str, Any]) -> str:
    return " ".join(
        str(trend.get(field, ""))
        for field in ("codex_theme", "theme", "topic", "api_title")
    ).lower()


def _signal_flags(text: str, subject_text: str) -> dict[str, bool]:
    return {
        "multiple_cases": bool(
            re.search(r"\b(?:cases|incidents|examples|deaths|victims|crimes|stories|characters|episodes|mods|worst|best|ranking|list|kill count)\b", text)
        ),
        "harm_or_consequence": bool(
            re.search(r"\b(?:crime|harm|abuse|fraud|death|killed|scandal|failure|consequence|victim|danger|cult|disaster|accident)\b", text)
        ),
        "familiar_artifact": bool(
            re.search(r"\b(?:episode|film|movie|show|series|game|mod|chapter|fandom|community|platform|franchise|character)\b", text)
        ),
        "social_theme": bool(
            re.search(r"\b(?:consumerism|greed|addiction|bullying|poverty|economics|protest|immigration|influencer|moderation|identity|trust|exploitation|workplace|social media)\b", text)
        ),
        "mystery_or_cause": bool(
            re.search(r"\b(?:why|how|what happened|mystery|theory|clue|secret|hidden|origin|explained|reveal|solved|changed)\b", text)
        ),
        "number_or_scale": bool(
            re.search(r"(?:\$\s*\d|\b\d[\d,]*\b|\b(?:count|total|record|scale|millions?|thousands?|days?|hours?)\b)", subject_text)
        ),
        "comparison": bool(
            re.search(r"\b(?:vs\.?|versus|best|worst|most|least|strongest|biggest|deadliest|ranking|compare)\b", subject_text)
        ),
        "creator_lookup": bool(
            re.search(TITLE_MECHANICS["creator_identity"], subject_text, re.IGNORECASE)
        ),
    }


def presentation_options_for_trend(
    trend: Mapping[str, Any], profile: Mapping[str, Any]
) -> dict[str, Any]:
    """Cross one trend with evidence-derived presentation archetypes."""

    text = _trend_text(trend)
    subject_text = _subject_text(trend)
    flags = _signal_flags(text, subject_text)
    fit_scores = {
        "escalating-case-ladder": 15
        + 35 * flags["multiple_cases"]
        + 35 * flags["harm_or_consequence"]
        + 15 * flags["familiar_artifact"],
        "familiar-work-thematic-lens": 20
        + 40 * flags["familiar_artifact"]
        + 35 * flags["social_theme"],
        "answerable-mystery": 30
        + 50 * flags["mystery_or_cause"]
        + 20 * flags["familiar_artifact"],
        "quantified-stakes": 10
        + 55 * flags["number_or_scale"]
        + 25 * flags["harm_or_consequence"]
        + 10 * flags["multiple_cases"],
        "extreme-comparison": 10
        + 55 * flags["comparison"]
        + 25 * flags["multiple_cases"]
        + 10 * flags["harm_or_consequence"],
    }
    warnings: list[str] = []
    identity_has_stakes = flags["harm_or_consequence"] or flags["social_theme"] or bool(
        re.search(r"\b(?:why|how|caused|changed|mechanism|conflict|scandal)\b", subject_text)
    )
    if flags["creator_lookup"] and not identity_has_stakes:
        warnings.append(
            "Identity-only creator lookup: reject unless the identity changes a documented consequence, mechanism, or central contradiction."
        )
        for key in ("answerable-mystery", "familiar-work-thematic-lens"):
            fit_scores[key] = max(0, fit_scores[key] - 50)
        if not (flags["number_or_scale"] or flags["comparison"]):
            fit_scores = {key: max(0, value - 35) for key, value in fit_scores.items()}

    archetypes = profile.get("presentation", {}).get("archetypes", [])
    options: list[dict[str, Any]] = []
    for archetype in archetypes:
        identifier = str(archetype.get("id", ""))
        fit = min(100, fit_scores.get(identifier, 0))
        ceiling = int(archetype.get("sensationalism_ceiling", 0))
        options.append(
            {
                "presentation_archetype": identifier,
                "reference_channel": archetype.get("reference_channel", ""),
                "fit_score": fit,
                "sensationalism_ceiling": ceiling,
                "sensationalism_potential_score": round(fit * ceiling / 100),
                "title_mechanic": archetype.get("title_mechanic", ""),
                "approach": archetype.get("approach", ""),
                "use_when": archetype.get("use_when", ""),
                "reject_when": archetype.get("reject_when", ""),
            }
        )
    options.sort(
        key=lambda item: (
            -int(item["sensationalism_potential_score"]),
            -int(item["fit_score"]),
            str(item["presentation_archetype"]),
        )
    )
    return {"signals": flags, "warnings": warnings, "options": options}
