from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping
from typing import Any

from youtube_trend_finder.presentation import presentation_options_for_trend


TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)


def _trend_text(trend: Mapping[str, Any]) -> str:
    fields = (
        "codex_theme",
        "theme",
        "topic",
        "api_title",
        "api_description",
        "collector_keywords",
        "collector_keywords_matched",
        "reddit_theory_pulse",
    )
    return " ".join(str(trend.get(field, "")) for field in fields).lower()


def _matches(text: str, signals: Iterable[str]) -> list[str]:
    return sorted({signal for signal in signals if signal.lower() in text})


def _tokens(value: str) -> set[str]:
    ignored = {"a", "an", "and", "in", "of", "on", "the", "to", "with"}
    return {item.lower() for item in TOKEN.findall(value) if item.lower() not in ignored}


def _novelty_score(title: str, published_titles: Iterable[str]) -> float:
    candidate = _tokens(title)
    if not candidate:
        return 0.0
    maximum = 0.0
    for published in published_titles:
        existing = _tokens(published)
        union = candidate | existing
        if union:
            maximum = max(maximum, len(candidate & existing) / len(union))
    return round(100 * (1 - maximum), 2)


def evaluate_profile_fit(
    trend: Mapping[str, Any],
    profile: Mapping[str, Any],
    published_titles: Iterable[str] = (),
) -> dict[str, Any]:
    """Score editorial fit independently from volatile trend strength."""

    text = _trend_text(trend)
    selection = profile["selection"]
    theme_hits = _matches(text, selection["topic_signals"])
    audience_hits = _matches(text, selection["audience_signals"])
    angle_hits = _matches(text, selection["angle_signals"])
    rejected_by = _matches(
        text,
        [*profile["identity"]["excluded_topics"], *selection["reject_signals"]],
    )

    components = {
        "themes": min(100.0, len(theme_hits) * 34.0),
        "audience": min(100.0, len(audience_hits) * 40.0),
        "angle": min(100.0, len(angle_hits) * 50.0),
        "novelty": _novelty_score(
            str(trend.get("codex_theme") or trend.get("theme") or trend.get("topic") or ""),
            published_titles,
        ),
    }
    weights = selection["fit_weights"]
    weight_total = sum(float(value) for value in weights.values())
    score = sum(components[key] * float(weights[key]) for key in components) / weight_total
    if rejected_by:
        score = 0.0

    hit_parts = []
    if theme_hits:
        hit_parts.append(f"topic signals: {', '.join(theme_hits)}")
    if audience_hits:
        hit_parts.append(f"audience signals: {', '.join(audience_hits)}")
    if angle_hits:
        hit_parts.append(f"angle signals: {', '.join(angle_hits)}")
    if rejected_by:
        hit_parts.append(f"incompatible signals: {', '.join(rejected_by)}")
    if not hit_parts:
        hit_parts.append("no explicit editorial signal matched")

    return {
        "profile_fit_score": round(score, 2),
        "profile_fit_components": {key: round(value, 2) for key, value in components.items()},
        "profile_fit_reason": "; ".join(hit_parts),
        "profile_topic_signals": theme_hits,
        "profile_audience_signals": audience_hits,
        "profile_angle_signals": angle_hits,
        "profile_rejected_by": rejected_by,
        "profile_compatible": not rejected_by
        and score >= float(selection["minimum_fit_score"]),
    }


def _number(trend: Mapping[str, Any], *names: str) -> float:
    for name in names:
        try:
            value = float(trend.get(name, 0))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            return value
    return 0.0


def _optional_number(trend: Mapping[str, Any], *names: str) -> float | None:
    for name in names:
        if name not in trend or trend.get(name) in (None, ""):
            continue
        try:
            value = float(trend[name])
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            return max(0.0, min(100.0, value))
    return None


def _scale(values: list[float]) -> list[float]:
    low = min(values, default=0.0)
    high = max(values, default=0.0)
    if high == low:
        return [100.0 if high > 0 else 0.0 for _ in values]
    return [100 * (value - low) / (high - low) for value in values]


def _saturation_score(trend: Mapping[str, Any]) -> float | None:
    explicit = _optional_number(trend, "codex_saturation_score", "saturation_score")
    if explicit is not None:
        return explicit
    verdict = str(trend.get("youtube_verdict", "")).lower()
    return {
        "hot-open": 100.0,
        "uncovered": 85.0,
        "hot-crowded": 55.0,
        "quiet": 45.0,
        "dormant": 30.0,
        "spent": 0.0,
    }.get(verdict)


def rank_trends_for_profile(
    trends: Iterable[Mapping[str, Any]],
    profile: Mapping[str, Any],
    published_titles: Iterable[str] = (),
) -> list[dict[str, Any]]:
    rows = [dict(item) for item in trends]
    raw_scores = [
        _number(row, "collector_trend_score", "trend_score", "codex_trend_score")
        for row in rows
    ]
    collector_scaled = _scale(raw_scores)
    growth_scaled = _scale(
        [_number(row, "collector_views_per_hour", "views_per_hour") for row in rows]
    )
    engagement_scaled = _scale(
        [_number(row, "collector_engagement_rate", "engagement_rate") for row in rows]
    )
    ranking_weights = profile["selection"]["ranking_weights"]
    ranking_total = sum(float(value) for value in ranking_weights.values())

    ranked: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        age_hours = _number(row, "collector_age_hours", "age_hours")
        components: dict[str, float] = {}
        gaps: list[str] = []

        recency = _optional_number(row, "codex_recency_score", "recency_score")
        if recency is None:
            if age_hours > 0:
                recency = 100 / (1 + age_hours / (24 * 7))
            else:
                recency = collector_scaled[index]
                gaps.append("recency")
        components["recency"] = recency

        growth = _optional_number(row, "codex_growth_score", "growth_score")
        if growth is None:
            growth = growth_scaled[index] or collector_scaled[index]
            if not _number(row, "collector_views_per_hour", "views_per_hour"):
                gaps.append("growth")
        components["growth"] = growth

        engagement = _optional_number(
            row, "codex_engagement_score", "engagement_score"
        )
        if engagement is None:
            engagement = engagement_scaled[index]
            if not _number(row, "collector_engagement_rate", "engagement_rate"):
                gaps.append("engagement")
        components["engagement"] = engagement

        cross_platform = _optional_number(
            row, "codex_cross_platform_score", "cross_platform_score"
        )
        if cross_platform is None:
            reddit_threads = _number(row, "reddit_thread_count")
            cross_platform = min(100.0, 35.0 + reddit_threads * 10) if reddit_threads else 0.0
            if not reddit_threads:
                gaps.append("cross_platform")
        components["cross_platform"] = cross_platform

        saturation = _saturation_score(row)
        if saturation is None:
            saturation = 50.0
            gaps.append("saturation")
        components["saturation"] = saturation

        lifespan = _optional_number(row, "codex_lifespan_score", "lifespan_score")
        if lifespan is None:
            lifespan = 50.0
            gaps.append("lifespan")
        components["lifespan"] = lifespan

        trend_score = sum(components.values()) / len(components)
        fit = evaluate_profile_fit(row, profile, published_titles)
        presentation = presentation_options_for_trend(row, profile)
        combined = (
            trend_score * float(ranking_weights["trend"])
            + fit["profile_fit_score"] * float(ranking_weights["profile"])
        ) / ranking_total
        ranked.append(
            {
                **row,
                **fit,
                "trend_score": round(trend_score, 2),
                "trend_score_components": {
                    key: round(value, 2) for key, value in components.items()
                },
                "trend_signal_gaps": gaps,
                "combined_score": round(combined, 2),
                "profile_id": profile["id"],
                "presentation_signals": presentation["signals"],
                "presentation_warnings": presentation["warnings"],
                "presentation_options": presentation["options"],
                "discarded": not fit["profile_compatible"],
                "discard_reason": (
                    fit["profile_fit_reason"]
                    if not fit["profile_compatible"]
                    else ""
                ),
            }
        )
    ranked.sort(
        key=lambda item: (item["discarded"], -item["combined_score"], -item["trend_score"])
    )
    for index, item in enumerate((item for item in ranked if not item["discarded"]), start=1):
        item["profile_rank"] = index
    return ranked


class _TemplateValues(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _format(template: str, subject: str) -> str:
    values = _TemplateValues(
        subject=subject,
        community=subject,
        platform=subject,
        case=subject,
    )
    return template.format_map(values)


def draft_suggestion(
    trend: Mapping[str, Any], profile: Mapping[str, Any]
) -> dict[str, Any]:
    """Create a profile-shaped draft for tests and as an agent starting point."""

    subject = str(
        trend.get("codex_theme") or trend.get("theme") or trend.get("topic") or "the subject"
    ).strip()
    patterns = profile["titles"]["patterns"]
    hooks = profile["narrative"]["hook_rules"]
    theses = profile["framing"]["thesis_types"]
    angles = profile["framing"]["angles"]
    presentation = trend.get("presentation_options")
    if not isinstance(presentation, list):
        presentation = presentation_options_for_trend(trend, profile)["options"]
    selected_presentation = presentation[0] if presentation else {}
    archetype = next(
        (
            item
            for item in profile.get("presentation", {}).get("archetypes", [])
            if item.get("id") == selected_presentation.get("presentation_archetype")
        ),
        {},
    )
    draft_pattern = str(archetype.get("draft_pattern") or patterns[0])
    presentation_fit = int(selected_presentation.get("fit_score", 0))
    presentation_ceiling = int(selected_presentation.get("sensationalism_ceiling", 0))
    return {
        "profile_id": profile["id"],
        "title": _format(draft_pattern, subject),
        "alternate_titles": [_format(item, subject) for item in patterns[1:4]],
        "source_trend": subject,
        "angle": _format(angles[0], subject),
        "hook": _format(hooks[0], subject),
        "thesis": _format(theses[0], subject),
        "structure": list(profile["narrative"]["development"]),
        "fit_reason": trend.get("profile_fit_reason", "profile rules applied"),
        "presentation_archetype": selected_presentation.get(
            "presentation_archetype", "unresolved"
        ),
        "sensationalism_potential_score": selected_presentation.get(
            "sensationalism_potential_score", 0
        ),
        "sensationalism_rationale": (
            f"Presentation fit {presentation_fit}/100 with truthful intensity capped at "
            f"{presentation_ceiling}/100 until its evidence requirements are met."
        ),
        "title_mechanic": selected_presentation.get("title_mechanic", ""),
        "approach": selected_presentation.get("approach", ""),
        "reference_pattern_evidence": selected_presentation.get(
            "reference_channel", ""
        ),
    }


def build_generation_prompt(
    profile: Mapping[str, Any],
    ranked_trends: Iterable[Mapping[str, Any]],
    published_titles: Iterable[str] = (),
    presentation_reference_analysis: Mapping[str, Any] | None = None,
    *, top: int = 15,
) -> str:
    """Build the mandatory handoff from deterministic ranking to agent generation."""

    context = {
        "profile": profile,
        "ranked_trends": list(ranked_trends),
        "published_reference_titles": list(published_titles),
        "presentation_reference_analysis": dict(presentation_reference_analysis or {}),
    }
    fields = ", ".join(profile["output"]["required_fields"])
    return (
        f"Generate editorial video proposals for profile '{profile['id']}'.\n"
        f"Return up to {top} distinct evidence-backed proposals, ranked 1 through N; "
        "never pad missing evidence or count alternate titles as separate ideas. "
        "If fewer qualify, report the shortfall. Preserve tracking_* fields: covered "
        "means notify with subject, date and run, never exclude or demote for coverage. "
        "Related means possible overlap, not proof of the same topic. Honor explicit blocked entries.\n"
        "Treat trend evidence as volatile execution data and profile rules as stable "
        "editorial identity. Discard incompatible rows even when popular. Apply the profile "
        "to selection, fit score, angle, title, hook, thesis, structure, differentiation, "
        "saturation risk, urgency, and recommendation rationale. Do not copy or closely "
        "paraphrase any reference title or transcript. Every factual trend claim needs a "
        "source URL and observation date.\n"
        "For every compatible trend, compare all presentation_options and select the one "
        "whose promise the evidence can deliver. A kill count, ranked list, worst/best "
        "compilation, exhaustive 'every' survey, quantified stake, or extreme comparison "
        "is allowed only when bounded units, counts, or comparisons are already supported. "
        "Use a familiar work as a thematic lens only when it exposes a charged human or "
        "system theme. Use an answerable mystery only for a concrete contradiction with a "
        "researchable payoff. Reject identity-only 'who made/created/is behind X' premises "
        "unless identity changes a documented consequence, mechanism, or central contradiction.\n"
        "sensationalism_potential_score measures safe packaging headroom from 0-100, not "
        "trend strength, truth probability, or permission to exaggerate facts. Never exceed "
        "the selected archetype's sensationalism_ceiling. State title mechanic, content "
        "approach, rationale, and reference-pattern evidence explicitly. Reference channels "
        "teach abstract presentation grammar only; their subjects and wording are forbidden.\n"
        f"Every proposal must contain: {fields}.\n\n"
        "INPUT_JSON\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
    )
