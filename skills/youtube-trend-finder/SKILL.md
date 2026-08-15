---
name: youtube-trend-finder
description: Find current YouTube trending themes for a niche, especially US/English trends, using the local collector.collect function. Use when the user asks to discover what themes, topics, memes, franchises, products, people, formats, or conversations are trending on YouTube. Do not generate video ideas, titles, hooks, scripts, thumbnail concepts, or production suggestions.
---

# YouTube Trend Finder

Use `collector.collect(...)` or `py scripts/collect.py` only for collection. Do the trend inference yourself after reading the generated API output.

## Workflow

1. Infer or ask for:
- `topic`
- time window in days, or a window preset
- ranking intent
- region and language, defaulting to `US` and `en`

Window presets:

- `flash`: 3 days
- `weekly`: 7 days
- `monthly`: 30 days
- `evergreen`: 90 days
- `compare`: run 7, 30, and 60 day collections with the same keywords and
  compare momentum

Intent presets:

- `discovery`: prioritize emerging themes
- `production`: prioritize researchable, shippable themes
- `evergreen`: prioritize durable themes
- `news-reactive`: prioritize recent named entities/current releases

2. Choose 6-10 English keywords that cover the niche from multiple angles:
- core category terms
- adjacent audience terms
- format terms
- emerging meme/franchise/person/entity terms when relevant

3. Run collection from the repository root. The default collection depth is 2 pages per keyword and 50 search results per page, so 10 keywords can inspect up to 1000 raw search results before deduplication.

CLI form:

```powershell
py scripts/collect.py "<topic>" --days <days> --keyword "<keyword-1>" --keyword "<keyword-2>" --pages-per-keyword 2
```

For `compare`, run the same command three times with `--days 7`, `--days 30`,
and `--days 60` using the same keyword set. Read all generated outputs before
ranking the final themes.

Python form:

```powershell
py -c "import collector as c; r=c.collect('<topic>', [<keywords>], <days>); print(r['csv']); print(r['json']); print(r['report']['estimated_quota_units'])"
```

For a smaller or larger scan in Python, set `pages_per_keyword` explicitly:

```powershell
py -c "import collector as c; r=c.collect('<topic>', [<keywords>], <days>, pages_per_keyword=5); print(r['csv']); print(r['json']); print(r['report']['estimated_quota_units'])"
```

4. Read the generated raw files in the timestamped output directory, such as:

```text
outputs/YYYYMMDD-HHMMSS/<topic>-api_videos.csv
outputs/YYYYMMDD-HHMMSS/<topic>-api_payload.json
```

5. Create one curated trending themes CSV in the same timestamped output directory as the raw API files, named:

```text
<topic>-trending_themes.csv
```

6. The curated themes CSV must contain exactly 20 rows when enough evidence exists. Each row is a theme/topic that is already trending in the evidence, not a proposed video. Include:
- `rank`
- `codex_theme`
- `codex_theme_summary`
- `codex_theme_type`
- `codex_why_trending`
- `codex_us_relevance`
- `codex_risk`
- `api_evidence_titles`
- `api_evidence_channels`
- `api_total_views_evidence`
- `collector_best_trend_score`
- `collector_best_views_per_hour`
- `collector_keywords`
- `codex_example_search_queries`
- `api_call_count_estimated`
- `api_quota_units_estimated`
- `api_cost_usd_estimated`
- `codex_confidence`
- `codex_source_boundary`
- `codex_window_class`
- `codex_momentum_note`
- `codex_recommended_next_step`
- `codex_researchability_score`
- `codex_artifact_availability`
- `codex_rights_risk`
- `codex_saturation_risk`

For `compare`, also include:

- `codex_7d_signal`
- `codex_30d_signal`
- `codex_60d_signal`

Allowed `codex_recommended_next_step` values:

- `research_now`
- `watchlist`
- `skip_rights_risk`
- `skip_too_generic`
- `skip_real_harm`

7. Do not create any separate video suggestions CSV. In particular, do not create:

- video titles
- video ideas
- hooks
- scripts
- thumbnail concepts
- production notes
- content angles

Examples of valid `codex_theme` values:
- `Backrooms creepypasta`
- `Obsession film reviews`
- `analog horror VHS aesthetics`
- `true overnight camping horror stories`

8. Keep source boundaries explicit:
- `api_*` fields summarize YouTube API returns.
- `collector_*` fields come from `collector.py`.
- `codex_*` fields are agent inference.

9. Estimate API cost from the collection report and reuse the same values where cost fields are needed:
- `api_call_count_estimated = len(report["api_calls"])`
- `api_quota_units_estimated = report["estimated_quota_units"]`
- `api_cost_usd_estimated = report["estimated_youtube_api_cost_usd"]`
- Mention `report["raw_video_ids_found"]`, `report["unique_videos_found"]`, `report["pages_per_keyword"]`, and `report["max_results_per_page"]` in the final response.

Prefer US audience relevance over raw global view count when ranking the final
top 20. Respect the requested intent: discovery favors emerging momentum,
production favors shippable/researchable themes, evergreen favors durable
subjects, and news-reactive favors current releases/named entities. The final
answer should report the inferred keywords, resolved window/intent, the path to
`*_trending_themes.csv`, the top 5 theme names only, and this next command:

```text
/research --themes-csv "<path-to-trending_themes.csv>" --rank 1
```

Do not include generated video titles or suggestions.
