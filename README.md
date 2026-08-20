# Mystery Consensus Explorer

A dependency-free browser app for exploring the fresh 100-agent mystery-work consensus dataset.

Live site: <https://jwknt.github.io/mystery-report/>

Open `index.html` directly, or serve `/Users/jw/Desktop/bin` with any static server and visit `/mystery-report/`. The repository includes its palette, typography, accessibility utilities, header, and saved light/dark theme, so the deployed site has no external runtime dependencies.

## Features

- Sort every column in the normalized works and raw-selection tables, with an optional second field and field-aware directions.
- Search titles, original titles, creators, media, criteria, and agent numbers.
- Filter by medium and criterion.
- Inspect each work’s consensus score, posterior mean, uncertainty penalty, rank-adjusted and raw axis means, support, selection counts, and mean placement.
- Jump from a work to its raw selections and all four scores supplied with each selection.
- Export the current filtered and sorted view as CSV.
- Paginate 25, 50, or 100 rows at a time.
- Read a short definition of each of the four ranking categories.

## Data model

The app embeds 1,037 retained normalized works, 20,032 complete agent–work ratings, and 29,991 ranked selections from 100 valid agents. Every retained singleton was checked against a catalogue, publisher, official, or reference record; three unverifiable or invalid work units were excluded.

Identity reconciliation merges alternate titles, release-year variants, and medium-label disagreements within the same form. TV shows, seasons, and episodes are represented by the encompassing `tv_series`; continuous prose stories across volumes are represented by their encompassing `book_series`. Genuinely self-contained prose installments may remain separate, and adaptations in different media remain separate works.

Each agent selected and ranked 100 works independently for ambition, fairness, and originality. The natural union of those lists was then scored on all four axes from 0 to 100. Influence was never a discovery or selection axis; it was scored only as a byproduct after selection.

For ambition, fairness, and originality, each agent’s raw score receives a bounded placement correction. Rank 1 adds five points, rank 50 is approximately neutral, rank 100 subtracts five, and absence from that particular list is conservatively treated as censored rank 101. Influence receives no rank correction.

Rank-adjusted axis means are shrunk toward their corpus-wide means using five virtual ratings. The posterior weighted mean uses these weights:

- Influence: 10%
- Ambition: 40%
- Fairness: 25%
- Originality: 25%

The displayed consensus score is a one-standard-error lower confidence score:

`consensus score = posterior weighted mean − global observation SD ÷ √(support + 5)`

This gives lightly supported works an explicit uncertainty penalty without imposing a minimum-support cutoff or treating a work’s absence from another agent’s union as a zero.

## Files

- `index.html` — semantic application shell.
- `assets/base.css` and `assets/theme.js` — self-contained shared theme and theme toggle.
- `assets/styles.css` — project-specific table and control layout.
- `assets/app.js` — sorting, filtering, pagination, detail dialog, and CSV export.
- `data/consensus-data.js` — generated scored survey dataset.
- `tests/static-site.test.mjs` — structural and data-integrity checks.
