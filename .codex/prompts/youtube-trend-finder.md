# YouTube Trend Finder

Use `$youtube-trend-finder` to find YouTube trending themes for `<NICHE>` in the
US. Support `--window flash|weekly|monthly|evergreen|compare`, `--days <N>`,
and `--intent discovery|production|evergreen|news-reactive`.

Defaults are `--window monthly` and `--intent production`. Choose relevant
English keywords, scan 2 pages per keyword unless the user asks otherwise, run
`collector.collect(...)`, read the raw API output, and create one curated
`*_trending_themes.csv` in the timestamped directory under `outputs/`. For
`--window compare`, run 7, 30, and 60 day collections with the same keyword set
before creating the final CSV.

Do not create video ideas, titles, hooks, scripts, thumbnail concepts, production notes, or content angles. Each row must be a theme/topic that is already trending in the evidence.

Include decision fields for window class, momentum, researchability, artifact
availability, rights risk, saturation risk, and recommended next step. For
compare runs, include 7d/30d/60d signal fields.

Finish with the inferred keywords, resolved window/intent, the path to
`*_trending_themes.csv`, the top 5 theme names only, and this next command:

```text
/research --themes-csv "<path-to-trending_themes.csv>" --rank 1
```
