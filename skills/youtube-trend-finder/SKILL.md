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
profile fit and separately ranks evidence-derived presentation options. The
profile must visibly affect:

- selection and rejection;
- profile-fit score and rationale;
- editorial angle;
- primary and alternate titles;
- hook and thesis;
- video structure;
- differentiation from the complete reference catalog;
- saturation risk and opportunity window.

For each candidate, compare the five presentation archetypes declared by the
profile: escalating case ladder, familiar-work thematic lens, answerable
mystery, quantified stakes, and extreme comparison. A kill count, top/bottom
list, `EVERY` survey, hard number, or superlative is eligible only when evidence
supports its units and boundary. Reject a creator/identity lookup unless the
identity changes a documented consequence, mechanism, or central contradiction.

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
- `presentation_archetype`
- `sensationalism_potential_score`
- `sensationalism_rationale`
- `title_mechanic`
- `approach`
- `reference_pattern_evidence`
- `saturation_risk`
- `opportunity_window`

Keep relevant raw evidence fields too. Never copy or closely paraphrase a
reference title or transcript. Extract recurring grammar and structure while
keeping proposals original.

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

## Presentation reference research

Profiles may also declare several presentation references. Refresh their
bounded title windows and small caption-opening samples with:

```powershell
py scripts/collect_presentation_references.py --profile <profile_id> --refresh-captions
```

This collector reads at most the configured number of recent Videos-tab title
records and the first configured number of words from declared caption samples.
It uses exact English subtitle languages, stores raw VTT files only in ignored
`.slash_tmp/`, and never downloads video, audio, or thumbnails. Captions serve
only to test how an opening pays off its title. Runtime, editing, and visuals are
outside this analysis.

`editorialize.py` loads the compact analysis and crosses every trend with all
presentation archetypes. `sensationalism_potential_score` is truthful packaging
headroom from 0-100, separate from trend strength and profile fit. Never treat
it as factual probability or permission to invent stakes.

## Final response

Lead with the run folder and clickable `trend_ideas.csv` link.
Report the selected profile, keywords, window/intent, final CSV, up to 15 adapted
titles and source themes, collection counts and quota, incompatible discards,
coverage notices with matching topic/date/run, any shortfall,
and any reference/transcript limitations. Finish with:

```text
/research --themes-csv "<run_dir>/trend_ideas.csv" --rank 1
```
