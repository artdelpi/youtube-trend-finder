# YouTube Trend Finder

Collect broad YouTube Data API evidence, then use a required editorial profile
to rank fit and create original video proposals.

## Skills

This repo ships one agent workflow:

- `$youtube-trend-finder` - require and validate an editorial profile, collect broad YouTube Data API evidence, rank fit separately from trend strength, and create profile-adapted video proposals. Supports `flash`, `weekly`, `monthly`, `evergreen`, and `compare` windows plus `discovery`, `production`, `evergreen`, and `news-reactive` ranking intent.

Claude should use `.claude/commands/youtube-trend-finder.md` for a slash-command style entry point and `skills/youtube-trend-finder/SKILL.md` as the canonical workflow. `.agents/skills/youtube-trend-finder/SKILL.md` mirrors the same workflow for local workspace discovery.

## Build & Test

```powershell
py -m compileall collector.py src scripts tests
py -m unittest discover -s tests
```

## Run

Use the CLI for manual collection:

```powershell
py scripts/collect.py "<topic>" --profile <profile_id> --days 30 --keyword "<keyword>" --pages-per-keyword 2
```

Agent window presets:

```text
flash=3 days, weekly=7 days, monthly=30 days, evergreen=90 days, compare=7/30/60 days
```

Agent ranking intents:

```text
discovery, production, evergreen, news-reactive
```

`collector.collect(...)` remains a raw collection primitive, not a complete
trend_finder execution. Complete runs must pass `--profile` through the CLI and
then call `scripts/editorialize.py` before generating proposals.

Raw collection code may still use:

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
