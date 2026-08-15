# YouTube Trend Finder

Collect YouTube Data API evidence for a niche and convert it into curated trend and video-idea CSVs.

## Skills

This repo ships one agent skill:

- `$youtube-trend-finder` - choose niche keywords, collect YouTube Data API evidence, read the raw output, create a top-20 trends CSV, and create 30 original video ideas.

Codex should read `skills/youtube-trend-finder/SKILL.md` when the user asks for YouTube trend discovery, niche research, or video ideas based on current YouTube data. `.agents/skills/youtube-trend-finder/SKILL.md` mirrors the same workflow for local workspace discovery.

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

Existing skill prompts may keep using:

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
