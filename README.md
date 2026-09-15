# YouTube Trend Finder

Collect broad YouTube Data API evidence for a niche, then use one required
editorial profile to rank fit and create original video proposals.

This repo is organized to work with both Codex and Claude-style agent workflows:

- Codex reads `AGENTS.md` and can package the local skill through `.codex-plugin/plugin.json`.
- Claude Code reads `CLAUDE.md` and gets a matching command in `.claude/commands/youtube-trend-finder.md`.
- The plugin skill lives in `skills/youtube-trend-finder/SKILL.md`; `.agents/skills/youtube-trend-finder/SKILL.md` mirrors it for local workspace discovery.

## Quick Start

Create `.env` from `.env.example` and set one of the supported API key names:

```powershell
Copy-Item .env.example .env
```

List and validate profiles from the enclosing Slop Factory checkout:

```powershell
py scripts/profiles.py list
py scripts/profiles.py validate possumdotmov
```

Run a collection. `--profile` is mandatory; there is no default or generic
fallback:

```powershell
py scripts/collect.py "horror channel" --profile possumdotmov-lobby --days 30 `
  --keyword "horror stories" `
  --keyword "scary true stories" `
  --keyword "analog horror" `
  --pages-per-keyword 2
```

Agent workflows can choose windows by intent:

```text
flash      3 days
weekly     7 days
monthly    30 days
evergreen  90 days
compare    run 7/30/60 days and compare momentum
```

Ranking intent:

```text
discovery      emerging themes
production     researchable/shippable themes
evergreen      durable subjects
news-reactive  current releases and named entities
```

Standalone raw collection writes timestamped files under `outputs/`:

```text
outputs/YYYYMMDD-HHMMSS/<topic>-api_videos.csv
outputs/YYYYMMDD-HHMMSS/<topic>-api_payload.json
outputs/YYYYMMDD-HHMMSS/<topic>-profile_context.json
```

After building a candidate CSV from the evidence, apply profile scoring and
create the generation handoff:

```powershell
py scripts/editorialize.py --profile possumdotmov-lobby --input "<trend-candidates.csv>"
```

## Agent Prompt

Use this prompt with Codex or Claude:

```text
Use $youtube-trend-finder with --profile possumdotmov-lobby to collect current YouTube evidence for internet horror and online communities in the US with --window compare and --intent production. Infer broad English keywords, read all raw evidence, score trend strength separately from profile fit, discard incompatible popularity with reasons, and create original profile-adapted proposals in `trend_ideas.csv` inside one dated, descriptive run folder.
```

## Editorial profile contract

Each valid profile has `profiles/<id>/editorial-profile.json` in the enclosing
Slop Factory repository. It defines channel proposition, audience, core and
excluded topics, selection rules and weights, framing, thesis/question types,
voice, narrative structure, hooks, title grammar, constraints, adaptation,
differentiation, reference provenance, and required output fields. Names are
strict lowercase slugs; path-like values and profile symlinks escaping the
profiles directory are rejected.

Raw trend evidence stays volatile. Profile identity stays stable. A run writes a
profile-context snapshot beside the raw evidence so ranking and generation can
prove which profile was used.

## Updating reference research

```powershell
py scripts/collect_reference_channel.py --profile possumdotmov-lobby --refresh-captions
```

This traverses every page of the public uploads playlist, checks public Shorts
and Lives tabs, records public metadata, and fetches captions through `yt-dlp`
with `--skip-download`. Video and audio are never downloaded. Raw captions stay
in the enclosing repository's ignored `.slash_tmp/`; compact catalog, coverage,
failures, and corpus measurements are written to paths declared by the profile.
Missing transcripts are recorded and do not stop the remaining analysis.

## Project Structure

```text
skills/                      Codex plugin skill source
.agents/skills/              Local workspace skill mirror
.claude/commands/            Claude slash-command prompt
.claude-plugin/              Claude plugin metadata
.codex/prompts/              Codex reusable prompt
.codex-plugin/               Codex plugin metadata
scripts/                     Command-line entry points
src/youtube_trend_finder/    Collection, safe profile loading, ranking, and reference analysis
tests/                       Unit tests for pure helpers
outputs/                     Generated API and curation files
```

Factual verification after proposal selection remains the researcher's job.

## Development

Run the lightweight checks:

```powershell
py -m compileall collector.py src scripts tests
py -m unittest discover -s tests
```

The root `collector.py` is a compatibility shim so existing prompts that run `import collector as c` still work.

## Proposal count and channel memory

`editorialize.py --top 15` is the default generation handoff: up to 15 distinct,
evidence-backed proposals, with an explicit shortfall if fewer qualify. It
rechecks the enclosing `tracking/covered_subjects.txt` for the selected profile.
Already covered exact subjects stay ranked and produce notices with topic, date
and run. Similar wording is only `related`; explicit `blocked` entries remain
excluded. Preserve `tracking_*` in the final CSV and recheck after subject edits.

## Output location

A complete Slop Factory run owns exactly one directory:
`results/trends/YYYYMMDD-HHMMSS-<profile>-<topic-slug>/`.
The date, time and English topic description identify each run, including reruns.
Open **trend_ideas.csv** directly inside that directory for the ranked proposals.
`trend_ideas.md` is the readable companion; `evidence_report.md` records evidence
and limitations. All raw collections and working files stay in `_internal/`.
Write output names, navigation, reports and proposals in English.

From the enclosing Slop Factory root, use `py scripts/trend_run.py init` with
`<topic> --profile <id> --window <window> --intent <intent> --top <top>` once.
Keep its absolute `run_dir` through every comparison window, expansion and resume.
Collect with `--out-dir "<run_dir>/_internal/youtube/<batch>" --no-timestamp`,
using distinct batches such as `7d`, `30d`, `60d` and `expansion-01`.
Never create sibling timestamp folders for individual collections.
After editorial review and coverage annotation, publish with:

```powershell
py scripts/trend_run.py finish --run-dir "<run_dir>" --csv "<run_dir>/_internal/proposals.csv" --report "<run_dir>/_internal/report.md"
```

The finalizer validates the handoff and updates `results/trends/README.md`.
Lead the response with the run folder and **trend_ideas.csv** link.
The standalone raw collector keeps its timestamped `outputs/` default; that is
not the output layout for a complete agent run.
