# YouTube Trend Finder

Use this repository's YouTube trend workflow for the user's niche.

1. Read `skills/youtube-trend-finder/SKILL.md`.
2. Parse optional `--window` and `--intent` flags. Defaults are
   `--window monthly` and `--intent production`.
3. Choose relevant English keywords for the niche.
4. Run `collector.collect(...)` or `py scripts/collect.py`. For
   `--window compare`, run 7, 30, and 60 day collections with the same keywords.
5. Read the generated `outputs/YYYYMMDD-HHMMSS/*-api_payload.json` and `*-api_videos.csv`.
6. Create `*-trending_themes.csv` with curated trending themes.
7. Include decision fields for window class, momentum, researchability,
   artifact availability, rights risk, saturation risk, and recommended next
   step. For compare runs, include 7d/30d/60d signal fields.
8. Do not create video ideas, video titles, hooks, thumbnail concepts, scripts,
   production notes, or content angles. Each row must be a theme/topic that is
   already trending in the evidence.
9. Finish with the inferred keywords, resolved window/intent, the CSV path, the top 5 theme names only,
   and this next command:

```text
/research --themes-csv "<path-to-trending_themes.csv>" --rank 1
```

Preserve source boundaries: `api_*` fields come from YouTube, `collector_*` fields come from code, and `codex_*` fields are agent inference.
