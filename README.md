# Mystery Report

A dependency-free browser app for exploring the fresh 100-agent mystery-work consensus dataset.

Live site: <https://jehlp.net/mystery-report/>

For local development, place this repository beside a checkout of [`site-theme`](https://github.com/JWKNT/site-theme), serve their parent directory, and visit `/mystery-report/`. The page imports the common palette, typography, accessibility utilities, header, and saved light/dark theme from `/site-theme/v1/`; only report-specific layout remains in this repository.

## Features

- Sort every column in the normalized works and raw-selection tables, with an optional second field and field-aware directions.
- Search titles, original titles, creators, media, criteria, and agent numbers.
- Filter by medium and criterion.
- Inspect each work’s consensus score, posterior mean, uncertainty penalty, rank-adjusted and raw axis means, support, selection counts, and mean placement.
- Jump from a work to its raw selections and all five scores supplied with each selection.
- Export the current filtered and sorted view as CSV.
- Paginate 25, 50, or 100 rows at a time.
- Read a short definition of each of the five scored categories.

## Data model

The app embeds 1,142 retained normalized works, 21,958 complete agent–work ratings, and 39,998 retained ranked selections from 100 valid agents. The collection produced exactly 40,000 placements; two nominations attached to one unverifiable work were excluded. Every retained singleton was checked against a catalogue, publisher, official, or reference record.

Identity reconciliation merges alternate titles, release-year variants, and medium-label disagreements within the same form. TV shows, seasons, and episodes are represented by the encompassing `tv_series`; continuous prose stories across volumes are represented by their encompassing `book_series`. A narratively self-contained component remains separate only when at least ten agents nominated it independently. Adaptations in different media remain separate works.

Each agent selected and ranked 100 works independently for ambition, fairness, originality, and all-around achievement within the traditional mystery form. The natural union of those four lists was then scored on all five axes from 0 to 100. Influence was never a discovery or selection axis; it was scored only as a byproduct after selection. The traditional-mystery list contributes nominations and support, but its placement does not mechanically alter traditionality or any other score.

For ambition, fairness, and originality, each agent’s raw score receives a bounded placement correction. Rank 1 adds five points, rank 50 is approximately neutral, rank 100 subtracts five, and absence from that particular list is conservatively treated as censored rank 101. Influence and traditionality receive no rank correction.

Rank-adjusted axis means are shrunk toward their corpus-wide means using ten virtual ratings. The posterior weighted mean uses these weights:

- Influence: 10%
- Ambition: 30%
- Fairness: 25%
- Traditionality: 20%
- Originality: 15%

The displayed consensus score is a one-sided 95% lower confidence score:

`consensus score = posterior weighted mean − 1.645 × global observation SD ÷ √(actual support)`

This gives lightly supported works an explicit uncertainty penalty without imposing a minimum-support cutoff or treating a work’s absence from another agent’s union as a zero.

## Published data

The source data and its audit trail are checked into the repository, rather than being available only through the rendered table:

- [`data/consensus-data.js`](data/consensus-data.js) — compact, generated payload loaded by the browser app.
- [`data/aggregate.json`](data/aggregate.json) — reconciled aggregate with the normalized works, observations, ranked selections, and calculated scores in readable JSON.
- [`data/raw_agents/`](data/raw_agents/) — the 100 original validated agent reports, one JSON file per agent.
- [`data/audit/`](data/audit/) — integrity, reconciliation, exclusion, and verification records.
- [`methodology/`](methodology/) — collection prompt and schema plus the validation, reconciliation, scoring, verification, and dashboard-build scripts.

## Files

- `index.html` — semantic application shell.
- `assets/styles.css` — project-specific table and control layout.
- `assets/app.js` — sorting, filtering, pagination, detail dialog, and CSV export.
- `data/` — browser payload, readable aggregate, raw reports, and audit artifacts.
- `methodology/` — reproducible data-collection and aggregation materials.
- `tests/static-site.test.mjs` — structural and data-integrity checks.
