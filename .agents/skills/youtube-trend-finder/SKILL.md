---
name: youtube-trend-finder
description: Find current YouTube trend evidence for a niche, then rank and turn it into original video proposals for one explicitly selected editorial profile. Requires --profile on every run.
---

# YouTube Trend Finder

Collect broad YouTube evidence first. Apply one validated editorial profile to
selection, ranking, and proposal generation afterward. Never run without an
explicit `--profile`; there is no default profile or generic fallback.

## Profile gate

Validate before any network call:

```powershell
py scripts/profiles.py validate <profile_id>
```

List available profiles:

```powershell
py scripts/profiles.py list
```

Reject missing, unknown, malformed, absolute, or path-like names. Profiles load
only from the enclosing Slop Factory `profiles/<id>/editorial-profile.json`.

## Workflow

1. Resolve:

- topic or niche;
- required profile id;
- time window;
- ranking intent;
- region and language, normally `US` and `en`;
- 6-10 broad English keywords covering core, adjacent, format, and emerging
  entity terms.

Windows: `flash` 3 days, `weekly` 7, `monthly` 30, `evergreen` 90, and
`compare` 7/30/60 with one keyword set. Intents: `discovery`, `production`,
`evergreen`, and `news-reactive`.

2. Collect from the repository root:

```powershell
py scripts/collect.py "<topic>" --profile <profile_id> --days <days> --keyword "<keyword-1>" --keyword "<keyword-2>" --pages-per-keyword 2
```

For `compare`, repeat at 7, 30, and 60 days with the same profile and keywords.
The default depth is two 50-result pages per keyword. Read every generated
`*-api_videos.csv`, `*-api_payload.json`, and `*-profile_context.json`.

`collector.collect(...)` remains a raw collection primitive. It is not a full
trend_finder run and does not replace the profile gate.

3. Build broad candidate themes from evidence. Preserve source boundaries:

- `api_*`: YouTube API returns;
- `collector_*`: local calculations;
- `codex_*`: agent inference;
- `profile_*`: editorial profile decisions.

Each candidate must retain dated evidence URLs and values for recency, velocity,
engagement, cross-platform confirmation when available, saturation, and expected
useful life. Normalize those six judgments as `codex_recency_score`,
`codex_growth_score`, `codex_engagement_score`, `codex_cross_platform_score`,
`codex_saturation_score`, and `codex_lifespan_score` on a 0-100 scale, each with
an evidence note.

4. Apply the profile:

```powershell
py scripts/editorialize.py --profile <profile_id> --input "<candidate-csv-or-json>"
```

Read `*-profile-ranked.json`, `*-profile-drafts.json`, and
`*-generation-prompt.md`. Deterministic scoring separates trend strength from
profile fit. The profile must visibly affect:

- selection and rejection;
- profile-fit score and rationale;
- editorial angle;
- primary and alternate titles;
- hook and thesis;
- video structure;
- differentiation from the complete reference catalog;
- saturation risk and opportunity window.

Discard incompatible popularity with a reason. Do not hide discarded candidates.
Crowding is a risk label, not an automatic rejection.

5. Write one final `*-trending_themes.csv`. Keep a `theme` column for downstream
compatibility and include:

- `profile_id`
- `title`
- `alternate_titles`
- `source_trend`
- `evidence_urls_and_dates`
- `trend_score`
- `trend_score_components`
- `trend_signal_gaps`
- `profile_fit_score`
- `profile_fit_reason`
- `angle`
- `hook`
- `thesis`
- `structure`
- `research_or_validation_needed`
- `difference_from_existing_content`
- `saturation_risk`
- `opportunity_window`

Keep relevant raw evidence fields too. Never copy or closely paraphrase a
reference title or transcript. Extract recurring grammar and structure while
keeping proposals original.

## Reference research

Profiles may declare a public reference channel, complete catalog, and analysis.
Refresh it without downloading video or audio:

```powershell
py scripts/collect_reference_channel.py --profile <profile_id> --refresh-captions
```

The command traverses the full YouTube uploads playlist, checks public Shorts and
Lives tabs, fetches batched public metadata, caches available English captions in
the enclosing repository's ignored `.slash_tmp/`, records every missing
transcript, and writes compact catalog/analysis JSON at profile-declared paths.
One failed or unavailable transcript must not abort the corpus.

## Final response

Report the selected profile, keywords, window/intent, final CSV, top five adapted
titles and source themes, collection counts and quota, incompatible discards,
and any reference/transcript limitations. Finish with:

```text
/research --themes-csv "<path-to-trending_themes.csv>" --rank 1
```
