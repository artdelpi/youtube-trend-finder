# YouTube Trend Finder

Use this repository's profile-aware YouTube trend workflow.

1. Read `skills/youtube-trend-finder/SKILL.md`.
2. Require an explicit `--profile`; validate it with `py scripts/profiles.py validate <id>` before any network call. Missing, unknown, or path-like values fail the command.
3. Parse optional `--window` and `--intent`; defaults are `monthly` and `production`.
4. Choose broad English niche keywords and run `py scripts/collect.py` with the validated `--profile`. Use 7/30/60-day collections for `compare`.
5. Read every raw API file and profile-context snapshot, then build candidate themes with dated evidence.
6. Run `py scripts/editorialize.py --profile <id> --input <candidates>`.
7. Use the generated profile ranking and generation prompt to create original proposals. The profile must alter selection, score, title, angle, hook, thesis, structure, differentiation, saturation risk, and rationale.
8. Preserve `api_*`, `collector_*`, `codex_*`, and `profile_*` boundaries. Record incompatible discards; never copy or closely paraphrase reference titles or transcripts.
9. Write `*-trending_themes.csv` with `theme` plus the proposal fields required by the profile.
10. Finish with profile id, keywords, window/intent, CSV path, top five adapted titles and source themes, evidence/quota counts, discards, limitations, and:

```text
/research --themes-csv "<path-to-trending_themes.csv>" --rank 1
```
