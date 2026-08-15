# YouTube Trend Finder

Collect YouTube Data API evidence for a niche, then let an AI agent turn that evidence into curated trend and video-idea CSVs.

This repo is organized to work with both Codex and Claude-style agent workflows:

- Codex reads `AGENTS.md` and can package the local skill through `.codex-plugin/plugin.json`.
- Claude Code reads `CLAUDE.md` and gets a matching command in `.claude/commands/youtube-trend-finder.md`.
- The plugin skill lives in `skills/youtube-trend-finder/SKILL.md`; `.agents/skills/youtube-trend-finder/SKILL.md` mirrors it for local workspace discovery.

## Quick Start

Create `.env` from `.env.example` and set one of the supported API key names:

```powershell
Copy-Item .env.example .env
```

Run a collection:

```powershell
py scripts/collect.py "horror channel" --days 30 `
  --keyword "horror stories" `
  --keyword "scary true stories" `
  --keyword "analog horror" `
  --pages-per-keyword 2
```

The collector writes timestamped files under `outputs/`:

```text
outputs/YYYYMMDD-HHMMSS/<topic>-api_videos.csv
outputs/YYYYMMDD-HHMMSS/<topic>-api_payload.json
```

## Agent Prompt

Use this prompt with Codex or Claude:

```text
Use $youtube-trend-finder to find YouTube trends for a horror channel in the US over the last 30 days. Choose relevant English keywords, scan 2 pages per keyword, run collector.collect(...), read the raw API output, create a curated top-20 trends CSV in the timestamped directory under outputs/, and create a second CSV with 30 original video suggestions based on those trends.
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
outputs/                     Generated API and curation files
```

## Development

Run the lightweight checks:

```powershell
py -m compileall collector.py src scripts tests
py -m unittest discover -s tests
```

The root `collector.py` is a compatibility shim so existing prompts that run `import collector as c` still work.
