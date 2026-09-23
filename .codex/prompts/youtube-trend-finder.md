# YouTube Trend Finder

Use `$youtube-trend-finder` with an explicit `--profile <profile_id>`. Validate
the profile before network access, collect broad US/English YouTube evidence,
and keep volatile trend strength separate from stable editorial fit.

After creating a dated candidate CSV, run:

```powershell
py scripts/editorialize.py --profile <profile_id> --input "<candidate-csv>"
```

Read the ranked JSON, presentation options, draft JSON, and generation prompt.
Produce original profile-adapted proposals in `*_trending_themes.csv`, retaining `theme` for
downstream compatibility. Each proposal must identify the profile and include
primary/alternate titles, source trend and dated evidence, trend score, profile
fit score and reason, angle, hook, thesis, structure, research gaps,
differentiation, saturation risk, and opportunity window. Discard incompatible
popularity with a reason. Never copy or closely paraphrase reference material.
Choose the strongest supported case ladder, thematic lens, answerable mystery,
quantified stakes, or extreme comparison. Reject identity-only creator lookups;
counts and superlatives require evidence. Include presentation archetype,
sensationalism potential, rationale, title mechanic, approach, and reference
pattern evidence in every proposal.

Finish with profile id, keywords, resolved window/intent, CSV path, top five
adapted titles and themes, collection/quota counts, discards, limitations, and:

```text
/research --themes-csv "<path-to-trending_themes.csv>" --rank 1
```
