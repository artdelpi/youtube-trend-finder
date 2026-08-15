# YouTube Trend Finder

Use this repository's YouTube trend workflow for the user's niche.

1. Read `skills/youtube-trend-finder/SKILL.md`.
2. Choose relevant English keywords for the niche.
3. Run `collector.collect(...)` or `py scripts/collect.py`.
4. Read the generated `outputs/YYYYMMDD-HHMMSS/*-api_payload.json` and `*-api_videos.csv`.
5. Create `*-codex_top20.csv` with curated trends.
6. Create `*-codex_video_ideas.csv` with 30 original video ideas.

Preserve source boundaries: `api_*` fields come from YouTube, `collector_*` fields come from code, and `codex_*` fields are agent inference.
