---
name: youtube-trend-finder
description: Find current YouTube trends and video ideas for a niche, especially US/English trends, using the local collector.collect function. Use when the user asks to discover what is trending on YouTube, choose keywords for a niche, collect recent YouTube API data, infer top topics, create a curated top-20 trends CSV, or generate 30 video suggestions based on identified trends.
---

# YouTube Trend Finder

Use `collector.collect(...)` or `py scripts/collect.py` only for collection. Do the trend inference yourself after reading the generated API output.

## Workflow

1. Infer or ask for:
- `topic`
- time window in days
- region and language, defaulting to `US` and `en`

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

5. Create a separate curated trends CSV in the same timestamped output directory as the raw API files, named:

```text
<topic>-codex_top20.csv
```

6. The curated trends CSV must contain exactly 20 rows when enough evidence exists. Include:
- `rank`
- `codex_trend`
- `codex_trend_summary`
- `codex_recommended_format`
- `codex_hook`
- `codex_us_relevance`
- `codex_risk`
- `api_evidence_titles`
- `api_evidence_channels`
- `api_total_views_evidence`
- `collector_best_trend_score`
- `collector_best_views_per_hour`
- `collector_keywords`
- `api_call_count_estimated`
- `api_quota_units_estimated`
- `api_cost_usd_estimated`
- `codex_confidence`
- `codex_source_boundary`

7. Create a separate video suggestions CSV in the same timestamped output directory as the raw API files, named:

```text
<topic>-codex_video_ideas.csv
```

8. The video suggestions CSV must contain exactly 30 rows based on the curated top-20 trends. Include:
- `rank`
- `codex_video_title`
- `codex_source_trends`
- `codex_angle`
- `codex_format`
- `codex_hook`
- `codex_opening_beat`
- `codex_thumbnail_concept`
- `codex_target_viewer`
- `codex_production_notes`
- `codex_risk`
- `codex_confidence`
- `codex_source_boundary`

9. Keep source boundaries explicit:
- `api_*` fields summarize YouTube API returns.
- `collector_*` fields come from `collector.py`.
- `codex_*` fields are agent inference.

10. Estimate API cost from the collection report and reuse the same values where cost fields are needed:
- `api_call_count_estimated = len(report["api_calls"])`
- `api_quota_units_estimated = report["estimated_quota_units"]`
- `api_cost_usd_estimated = report["estimated_youtube_api_cost_usd"]`
- Mention `report["raw_video_ids_found"]`, `report["unique_videos_found"]`, `report["pages_per_keyword"]`, and `report["max_results_per_page"]` in the final response.

Prefer US audience relevance over raw global view count when ranking the final top 20. Make video suggestions original, production-ready, and clearly derived from trend patterns rather than copied titles.
