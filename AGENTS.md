# YouTube Trend Finder

Collect broad YouTube Data API evidence, then use a required editorial profile
to rank fit, compare presentation mechanics, and create original video proposals.

## Skills

This repo ships one agent skill:

- `$youtube-trend-finder` - require and validate an editorial profile, collect broad YouTube Data API evidence, rank fit separately from trend strength, and create profile-adapted video proposals. Supports `flash`, `weekly`, `monthly`, `evergreen`, and `compare` windows plus `discovery`, `production`, `evergreen`, and `news-reactive` ranking intent.

Codex should read `skills/youtube-trend-finder/SKILL.md` when the user asks for YouTube trend discovery, niche research, or currently trending themes based on YouTube data. `.agents/skills/youtube-trend-finder/SKILL.md` mirrors the same workflow for local workspace discovery.

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

Refresh profile-declared cross-channel presentation research with
`py scripts/collect_presentation_references.py --profile <id> --refresh-captions`.
It reads bounded title metadata and small declared caption openings only; video,
audio, thumbnails, runtime, editing, and visuals stay out of scope.

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
- Keep trend strength, profile fit, and sensationalism potential separate. Lists,
  kill counts, extremes, and hard numbers require evidence for their boundary.
- Reject identity-only creator lookups unless identity changes a consequence,
  mechanism, or central contradiction.
- Do not commit `.env`, generated `outputs/`, `__pycache__/`, or `.pyc` files.
- Keep the root `collector.py` shim unless all agent prompts have migrated to the package or CLI.

## Proposal count and channel memory

`editorialize.py --top 15` is the default generation handoff: up to 15 distinct,
evidence-backed proposals, with an explicit shortfall if fewer qualify. It
rechecks the enclosing `tracking/covered_subjects.txt` for the selected profile.
Already covered exact subjects stay ranked and produce notices with topic, date
and run. Similar wording is only `related`; explicit `blocked` entries remain
excluded. Preserve `tracking_*` in the final CSV and recheck after subject edits.

## Viral-recycle lane

Beside the trend proposals, a run proposes up to `--recycle` films (default 5)
that each answer one recent breakout video in the niche with our own film on
the same subject: same question, the conclusions its audience rewarded, our
research, order, register and words, plus what its comment section says it got
wrong or left out.

- `scripts/viral_scan.py --run-dir <run> --profile <id>` reads every batch of
  the run, screens format and profile exclusions without quota, then measures
  the 40 fastest videos from the last 45 days against the median of their own
  channel's recent uploads (`collector_outlier_ratio`; `breakout` is 5x or
  more, `strong` 2x). About 70 units. Writes `_internal/viral/viral_candidates.csv`.
- `scripts/viral_study.py --run-dir <run> --video <id>` writes
  `_internal/viral/<id>/`: thumbnail, captions, about 400 comments, chapters,
  the most-replayed curve, `signals.json` (comment piles, commented timestamps,
  replayed moments, narration lines commenters quoted back) and a pending
  `study.md`. About 5 units. It never downloads the video; `/watch` frames need
  an `allow` from the researcher's `check_download.py`.
- The format screen is lexical (`eligible`, `needs-review`, `rejected`); the
  agent confirms it from the transcript. Commentary, theory, compilation,
  ranking, documentary, essay, review and reaction are recyclable; the work
  itself, trailers, music, gameplay, performances and raw news clips are not.
- Originality is enforced twice: `trend_run.py finish` rejects a proposal whose
  title shares more than half its content words with the reference title or
  whose text repeats eight words of the reference transcript, and
  `scripts/check_recycle_copy.py` runs the same transcript check on a film's
  brief.
- Thresholds are named constants at the top of
  `src/youtube_trend_finder/viral.py`, pinned by `tests/test_viral.py`.

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
