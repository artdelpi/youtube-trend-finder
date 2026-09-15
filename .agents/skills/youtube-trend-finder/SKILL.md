---
name: youtube-trend-finder
description: Find current YouTube trend evidence for a niche, then rank and turn it into original video proposals for one explicitly selected editorial profile. Requires --profile on every run.
---

# YouTube Trend Finder

Collect broad YouTube evidence first. Apply one validated editorial profile to
selection, ranking, and proposal generation afterward. Never run without an
explicit `--profile`; there is no default profile or generic fallback.

## Profile gate

Validate before any network call:

```powershell
py scripts/profiles.py validate <profile_id>
```

List available profiles:

```powershell
py scripts/profiles.py list
```

Reject missing, unknown, malformed, absolute, or path-like names. Profiles load
only from the enclosing Slop Factory `profiles/<id>/editorial-profile.json`.


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

## Workflow

1. Resolve:

- topic or niche;
- required profile id;
- time window;
- ranking intent;
- `--top`, a positive integer, default 15 distinct proposals;
- region and language, normally `US` and `en`;
- 6-10 broad English keywords covering core, adjacent, format, and emerging
  entity terms.

Windows: `flash` 3 days, `weekly` 7, `monthly` 30, `evergreen` 90, and
`compare` 7/30/60 with one keyword set. Intents: `discovery`, `production`,
`evergreen`, and `news-reactive`.

2. Initialize one run as above from the enclosing Slop Factory root. Then collect
from the trend_finder repository root using the absolute run directory:

```powershell
py scripts/collect.py "<topic>" --profile <profile_id> --days <days> --keyword "<keyword-1>" --keyword "<keyword-2>" --pages-per-keyword 2 --out-dir "<run_dir>/_internal/youtube/<batch>" --no-timestamp
```

For `compare`, repeat at 7, 30, and 60 days with the same profile and keywords.
The default depth is two 50-result pages per keyword. Read every generated
`*-api_videos.csv`, `*-api_payload.json`, and `*-profile_context.json`.

`collector.collect(...)` remains a raw collection primitive. It is not a full
trend_finder run and does not replace the profile gate.

3. Build `<run_dir>/_internal/trend_candidates.csv` from evidence. Preserve source boundaries:

- `api_*`: YouTube API returns;
- `collector_*`: local calculations;
- `codex_*`: agent inference;
- `profile_*`: editorial profile decisions.

Each candidate must retain dated evidence URLs and values for recency, velocity,
engagement, cross-platform confirmation when available, saturation, and expected
useful life. Normalize those six judgments as `codex_recency_score`,
`codex_growth_score`, `codex_engagement_score`, `codex_cross_platform_score`,
`codex_saturation_score`, and `codex_lifespan_score` on a 0-100 scale, each with
an evidence note.

4. Apply the profile and check channel coverage:

```powershell
py scripts/editorialize.py --profile <profile_id> --input "<candidate-csv-or-json>" --top 15
```

The CLI checks the enclosing `tracking/covered_subjects.txt` on every call.
Keep `covered` candidates and their ranks; notify with topic, date and run.
`related` means possible overlap, not the same exact topic; only explicit
`blocked` entries are exclusions. Retain `tracking_*` fields in every proposal.
Recheck the final CSV using the enclosing `scripts/coverage.py annotate` after
writing exact subjects.

Read `*-profile-ranked.json`, `*-profile-drafts.json`, and
`*-generation-prompt.md`. Deterministic scoring separates trend strength from
profile fit. The profile must visibly affect:

- selection and rejection;
- profile-fit score and rationale;
- editorial angle;
- primary and alternate titles;
- hook and thesis;
- video structure;
- differentiation from the complete reference catalog;
- saturation risk and opportunity window.

Discard incompatible popularity with a reason. Do not hide discarded candidates.
Crowding is a risk label, not an automatic rejection.

5. Produce up to 15 distinct evidence-backed proposals (or the requested
`--top`), ranked `1..N`. Expand collection within the quota budget if short;
report a shortage rather than padding or counting alternate titles as ideas.
Write reviewed rows to `<run_dir>/_internal/proposals.csv`, then use the
finalizer above to publish exactly one `trend_ideas.csv` at the run root. Keep a `theme` column for downstream
compatibility and include:

- `profile_id`
- `title`
- `alternate_titles`
- `source_trend`
- `evidence_urls_and_dates`
- `trend_score`
- `trend_score_components`
- `trend_signal_gaps`
- `profile_fit_score`
- `profile_fit_reason`
- `angle`
- `hook`
- `thesis`
- `structure`
- `research_or_validation_needed`
- `difference_from_existing_content`
- `saturation_risk`
- `opportunity_window`

Keep relevant raw evidence fields too. Never copy or closely paraphrase a
reference title or transcript. Extract recurring grammar and structure while
keeping proposals original.

## Reference research

Profiles may declare a public reference channel, complete catalog, and analysis.
Refresh it without downloading video or audio:

```powershell
py scripts/collect_reference_channel.py --profile <profile_id> --refresh-captions
```

The command traverses the full YouTube uploads playlist, checks public Shorts and
Lives tabs, fetches batched public metadata, caches available English captions in
the enclosing repository's ignored `.slash_tmp/`, records every missing
transcript, and writes compact catalog/analysis JSON at profile-declared paths.
One failed or unavailable transcript must not abort the corpus.

## Final response

Lead with the run folder and clickable `trend_ideas.csv` link.
Report the selected profile, keywords, window/intent, final CSV, up to 15 adapted
titles and source themes, collection counts and quota, incompatible discards,
coverage notices with matching topic/date/run, any shortfall,
and any reference/transcript limitations. Finish with:

```text
/research --themes-csv "<run_dir>/trend_ideas.csv" --rank 1
```
