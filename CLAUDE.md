# YouTube Trend Finder

Collect YouTube Data API evidence for a niche and convert it into curated trending-theme CSVs.

## Skills

This repo ships one agent workflow:

- `$youtube-trend-finder` - choose niche keywords, collect YouTube Data API evidence, read the raw output, and create a ranked CSV of trending themes. Supports `flash`, `weekly`, `monthly`, `evergreen`, and `compare` windows plus `discovery`, `production`, `evergreen`, and `news-reactive` ranking intent. Do not create video ideas or titles.

Claude should use `.claude/commands/youtube-trend-finder.md` for a slash-command style entry point and `skills/youtube-trend-finder/SKILL.md` as the canonical workflow. `.agents/skills/youtube-trend-finder/SKILL.md` mirrors the same workflow for local workspace discovery.

## Build & Test

```powershell
py -m compileall collector.py src scripts tests
py -m unittest discover -s tests
```

## Run

Use the CLI for manual collection:

```powershell
py scripts/collect.py "<topic>" --days 30 --keyword "<keyword>" --pages-per-keyword 2
```

Agent window presets:

```text
flash=3 days, weekly=7 days, monthly=30 days, evergreen=90 days, compare=7/30/60 days
```

Agent ranking intents:

```text
discovery, production, evergreen, news-reactive
```

Existing prompts may keep using:

```powershell
py -c "import collector as c; r=c.collect('<topic>', [<keywords>], <days>); print(r['csv']); print(r['json'])"
```

## Project Structure

```text
skills/                      Codex plugin skill source
.agents/skills/              Local workspace skill mirror
.claude/commands/            Claude slash-command prompt
.claude-plugin/              Claude plugin metadata
.codex/prompts/              Codex reusable prompt
.codex-plugin/               Codex plugin metadata
scripts/                     Command-line entry points
src/youtube_trend_finder/    Python package
tests/                       Unit tests for pure helpers
outputs/                     Generated data, ignored by git
```

## Conventions

- Keep `AGENTS.md`, `CLAUDE.md`, `README.md`, `skills/`, and `.agents/skills/` in sync when changing the agent contract.
- Preserve source boundaries in CSV fields: `api_*` from YouTube, `collector_*` from code, and `codex_*` from agent inference.
- Do not commit `.env`, generated `outputs/`, `__pycache__/`, or `.pyc` files.
- Keep the root `collector.py` shim unless all agent prompts have migrated to the package or CLI.
