from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


PROFILE_FILENAME = "editorial-profile.json"
PROFILE_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProfileError(ValueError):
    """Raised when an editorial profile cannot be safely loaded or validated."""


@dataclass(frozen=True)
class LoadedProfile:
    profile_id: str
    path: Path
    data: dict[str, Any]


def find_profiles_root(start: str | Path | None = None) -> Path:
    """Find the nearest Slop Factory ``profiles`` directory.

    The trend finder is a git submodule, so its CLI may run from either the
    submodule or the parent repository. Search both the working directory and
    the installed module's ancestors without accepting a user-supplied path.
    """

    starts = [Path(start).resolve() if start is not None else Path.cwd().resolve()]
    starts.append(Path(__file__).resolve())
    seen: set[Path] = set()
    for origin in starts:
        base = origin if origin.is_dir() else origin.parent
        for parent in (base, *base.parents):
            candidate = (parent / "profiles").resolve()
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate.is_dir():
                return candidate
    raise ProfileError(
        "Could not find the Slop Factory profiles directory. Run from the "
        "Slop Factory checkout or install a profiles directory beside it."
    )


def list_profiles(profiles_root: str | Path | None = None) -> list[str]:
    root = (
        Path(profiles_root).resolve()
        if profiles_root is not None
        else find_profiles_root()
    )
    if not root.is_dir():
        raise ProfileError(f"Profiles directory does not exist: {root}")
    return sorted(
        item.name
        for item in root.iterdir()
        if item.is_dir()
        and not item.name.startswith("_")
        and (item / PROFILE_FILENAME).is_file()
    )


def _type_name(expected: type | tuple[type, ...]) -> str:
    if isinstance(expected, tuple):
        return " or ".join(item.__name__ for item in expected)
    return expected.__name__


def _require_path(
    payload: Mapping[str, Any],
    dotted_path: str,
    expected: type | tuple[type, ...],
) -> Any:
    value: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            raise ProfileError(f"Editorial profile is missing '{dotted_path}'.")
        value = value[part]
    numeric_expected = expected is int or (
        isinstance(expected, tuple) and any(item in (int, float) for item in expected)
    )
    if not isinstance(value, expected) or isinstance(value, bool) and numeric_expected:
        raise ProfileError(
            f"Editorial profile field '{dotted_path}' must be {_type_name(expected)}."
        )
    return value


def _require_nonempty_strings(payload: Mapping[str, Any], dotted_path: str) -> list[str]:
    values = _require_path(payload, dotted_path, list)
    if not values or any(not isinstance(item, str) or not item.strip() for item in values):
        raise ProfileError(
            f"Editorial profile field '{dotted_path}' must be a non-empty list of strings."
        )
    return values


def validate_editorial_profile(
    payload: Mapping[str, Any], expected_id: str | None = None
) -> dict[str, Any]:
    """Validate the complete profile contract used by ranking and generation."""

    if not isinstance(payload, Mapping):
        raise ProfileError("Editorial profile root must be an object.")

    schema_version = _require_path(payload, "schema_version", int)
    if schema_version < 1:
        raise ProfileError("Editorial profile 'schema_version' must be at least 1.")

    profile_id = _require_path(payload, "id", str)
    if not PROFILE_NAME.fullmatch(profile_id):
        raise ProfileError(
            "Editorial profile 'id' must use lowercase letters, digits, and single hyphens."
        )
    if expected_id is not None and profile_id != expected_id:
        raise ProfileError(
            f"Editorial profile id '{profile_id}' does not match directory '{expected_id}'."
        )

    required_strings = (
        "identity.name",
        "identity.proposition",
        "identity.audience",
        "framing.approach",
        "voice.informality",
        "narrative.format",
        "narrative.target_duration",
        "narrative.story_use",
        "narrative.example_use",
        "narrative.evidence_use",
        "narrative.humor_use",
        "narrative.commentary_use",
        "narrative.conclusion",
        "narrative.cta",
        "titles.style",
        "titles.curiosity",
        "titles.tension",
        "titles.specificity",
        "titles.positioning",
        "titles.capitalization",
        "titles.punctuation",
        "adaptation.saturation_policy",
        "adaptation.evidence_policy",
        "reference.channel",
        "reference.url",
        "reference.collected_at",
        "reference.catalog_file",
        "reference.analysis_file",
    )
    for path in required_strings:
        value = _require_path(payload, path, str)
        if not value.strip():
            raise ProfileError(f"Editorial profile field '{path}' cannot be empty.")

    required_lists = (
        "identity.core_topics",
        "identity.excluded_topics",
        "selection.criteria",
        "selection.topic_signals",
        "selection.audience_signals",
        "selection.angle_signals",
        "selection.reject_signals",
        "framing.angles",
        "framing.thesis_types",
        "framing.question_types",
        "voice.tone",
        "voice.vocabulary",
        "voice.avoid",
        "narrative.hook_rules",
        "narrative.development",
        "titles.patterns",
        "titles.avoid",
        "adaptation.rules",
        "adaptation.differentiation_rules",
        "output.required_fields",
    )
    for path in required_lists:
        _require_nonempty_strings(payload, path)

    _require_path(payload, "reference.failures", list)
    for path in ("reference.total_publications", "reference.transcripts_obtained"):
        value = _require_path(payload, path, int)
        if value < 0:
            raise ProfileError(f"Editorial profile field '{path}' cannot be negative.")

    minimum_fit = _require_path(payload, "selection.minimum_fit_score", (int, float))
    if not 0 <= minimum_fit <= 100:
        raise ProfileError("'selection.minimum_fit_score' must be between 0 and 100.")

    for path, expected_keys in (
        ("selection.fit_weights", {"audience", "themes", "angle", "novelty"}),
        ("selection.ranking_weights", {"trend", "profile"}),
    ):
        weights = _require_path(payload, path, dict)
        if set(weights) != expected_keys:
            raise ProfileError(
                f"Editorial profile field '{path}' must contain exactly: "
                f"{', '.join(sorted(expected_keys))}."
            )
        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
            for value in weights.values()
        ) or sum(weights.values()) <= 0:
            raise ProfileError(f"Editorial profile field '{path}' has invalid weights.")

    return dict(payload)


def load_profile(
    profile_id: str,
    profiles_root: str | Path | None = None,
) -> LoadedProfile:
    root = (
        Path(profiles_root).resolve()
        if profiles_root is not None
        else find_profiles_root()
    )
    valid = list_profiles(root)
    valid_text = ", ".join(valid) if valid else "(none)"
    if not PROFILE_NAME.fullmatch(profile_id or ""):
        raise ProfileError(
            f"Invalid profile name '{profile_id}'. Expected lowercase letters, digits, "
            f"and single hyphens. Valid profiles: {valid_text}"
        )

    profile_dir = (root / profile_id).resolve()
    if root not in profile_dir.parents:
        raise ProfileError(f"Invalid profile name '{profile_id}'. Valid profiles: {valid_text}")
    path = (profile_dir / PROFILE_FILENAME).resolve()
    if profile_dir not in path.parents or not path.is_file():
        raise ProfileError(f"Unknown profile '{profile_id}'. Valid profiles: {valid_text}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f"Could not read editorial profile '{profile_id}': {exc}") from exc
    return LoadedProfile(
        profile_id=profile_id,
        path=path,
        data=validate_editorial_profile(payload, expected_id=profile_id),
    )


def load_reference_titles(profile: LoadedProfile) -> list[str]:
    relative = profile.data["reference"]["catalog_file"]
    path = (profile.path.parent / relative).resolve()
    if profile.path.parent not in path.parents:
        raise ProfileError("Reference catalog path must stay inside the profile directory.")
    if not path.is_file():
        raise ProfileError(f"Reference catalog does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f"Could not read reference catalog: {exc}") from exc
    publications = payload.get("publications")
    if not isinstance(publications, list):
        raise ProfileError("Reference catalog must contain a 'publications' list.")
    titles = [item.get("title", "") for item in publications if isinstance(item, Mapping)]
    return [title for title in titles if isinstance(title, str) and title.strip()]
