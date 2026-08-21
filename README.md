# Mystery Report

A dependency-free browser app for comparing and exploring two 100-agent mystery-work consensus datasets.

Live site: <https://jehlp.net/mystery-report/>

For local development, place this repository beside a checkout of [`site-theme`](https://github.com/JWKNT/site-theme), serve their parent directory, and visit `/mystery-report/`. The page imports the common palette, typography, accessibility utilities, header, and saved light/dark theme from `/site-theme/v1/`; only report-specific layout remains in this repository.

## Features

- Switch between the original four-axis v3 survey and the five-axis v4 survey.
- Sort every column in either normalized works or raw-selection table, with an optional second field and field-aware directions.
- Search titles, original titles, creators, media, criteria, and agent numbers.
- Filter by medium and criterion.
- Inspect each work’s consensus score, posterior mean, uncertainty penalty, rank-adjusted and raw axis means, support, selection counts, and mean placement.
- Jump from a work to its raw selections and all five scores supplied with each selection.
- Export the current filtered and sorted view as CSV.
- Paginate 25, 50, or 100 rows at a time.
- Read a short definition of each of the five scored categories.

## Data models

V4 embeds 1,137 retained normalized works, 21,939 complete agent–work ratings, and 39,998 retained ranked selections from 100 valid agents. The collection produced exactly 40,000 placements; two nominations attached to one unverifiable work were excluded. Every retained singleton was checked against a catalogue, publisher, official, or reference record.

V3 embeds 1,036 retained normalized works, 20,002 complete agent–work ratings, and 29,997 retained ranked selections from a separate set of 100 valid agents. It preserves the original four scored axes and three discovery lists while using the same uncertainty treatment as v4.

Identity reconciliation merges alternate titles, release-year variants, and medium-label disagreements within the same form. TV shows, seasons, and episodes are represented by the encompassing `tv_series`; continuous stories across installments are represented by their encompassing series. A narratively self-contained component normally remains separate only when at least ten agents nominated it independently. Explicit audited work-unit rules can still consolidate a connected saga when component and series labels clearly describe the same intended work, as with the Golden Idol games. Adaptations in different media remain separate works.

Each agent selected and ranked 100 works independently for ambition, fairness, originality, and all-around achievement within the traditional mystery form. The natural union of those four lists was then scored on all five axes from 0 to 100. Influence was never a discovery or selection axis; it was scored only as a byproduct after selection. The traditional-mystery list contributes nominations and support, but its placement does not mechanically alter traditionality or any other score.

For ambition, fairness, and originality, each agent’s raw score receives a bounded placement correction. Rank 1 adds five points, rank 50 is approximately neutral, rank 100 subtracts five, and absence from that particular list is conservatively treated as censored rank 101. Influence and traditionality receive no rank correction.

Rank-adjusted axis means in both datasets are shrunk toward their corpus-wide means using ten virtual ratings. V4 uses these weights:

- Influence: 10%
- Ambition: 35%
- Fairness: 25%
- Traditionality: 10%
- Originality: 20%

V3 keeps its original weights:

- Influence: 10%
- Ambition: 40%
- Fairness: 25%
- Originality: 25%

The displayed consensus score is a one-sided 95% lower confidence score:

`consensus score = posterior weighted mean − 1.645 × global observation SD ÷ √(actual support)`

This gives lightly supported works an explicit uncertainty penalty without imposing a minimum-support cutoff or treating a work’s absence from another agent’s union as a zero.

## Published data

The source data and its audit trail are checked into the repository, rather than being available only through the rendered table:

- [`data/consensus-data.js`](data/consensus-data.js) and [`data/aggregate.json`](data/aggregate.json) — generated v4 browser payload and readable aggregate.
- [`data/raw_agents/`](data/raw_agents/) and [`data/audit/`](data/audit/) — v4 source reports and audit trail.
- [`data/v3/`](data/v3/) — v3 browser payload, readable aggregate, all 100 source reports, and audit trail.
- [`methodology/`](methodology/) and [`methodology/v3/`](methodology/v3/) — reproducible v4 and v3 validation, reconciliation, scoring, and dashboard-build scripts.

## Files

- `index.html` — semantic application shell.
- `assets/styles.css` — project-specific table and control layout.
- `assets/app.js` — sorting, filtering, pagination, detail dialog, and CSV export.
- `data/` — browser payload, readable aggregate, raw reports, and audit artifacts.
- `methodology/` — reproducible data-collection and aggregation materials.
- `tests/static-site.test.mjs` — structural and data-integrity checks.
