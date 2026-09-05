import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function source(relativePath) {
  return readFile(path.join(root, relativePath), "utf8");
}

async function datasets() {
  const context = { window: {} };
  vm.runInNewContext(await source("data/v3/consensus-data.js"), context);
  vm.runInNewContext(await source("data/consensus-data.js"), context);
  return context.window.MYSTERY_CONSENSUS_DATASETS;
}

async function dataset() {
  return (await datasets()).v4;
}

test("page imports the shared site theme and exposes the core controls", async () => {
  const html = await source("index.html");
  assert.match(html, /\/site-theme\/v2\/theme\.js/);
  assert.match(html, /\/site-theme\/v2\/base\.css/);
  assert.match(html, /favicons\/mystery-report\.png/);
  assert.match(html, /<details class="sort-details">[\s\S]*<summary>Advanced sorting<\/summary>/);
  assert.match(html, /data\/v3\/consensus-data\.js/);
  assert.match(html, /assets\/app\.js\?v=20260905-editorial-2/);
  assert.match(html, /href="\?dataset=v1" data-dataset="v1">Version 1 · four axes<[\s\S]*href="\?dataset=v2" data-dataset="v2">Version 2 · five axes</);
  assert.match(html, /<h1 id="results-title">Works<\/h1>/);
  assert.match(html, /data-view="works"/);
  assert.match(html, /data-view="selections"/);
  assert.match(html, /id="search-input"/);
  assert.match(html, /id="primary-sort"/);
  assert.match(html, /id="secondary-sort"/);
  assert.match(html, /id="export-csv"/);
  assert.match(html, /id="work-dialog"/);
  assert.match(html, /<h2 id="categories-title">Scoring key<\/h2>/);
  assert.match(html, /Placement-adjusted mean/);
  assert.match(html, /id="category-guide"/);
  assert.doesNotMatch(html, /<footer\b|dataset-summary/);
  assert.doesNotMatch(html, /id="method"|Placement-only Borda consensus/);
  assert.doesNotMatch(html, /id="status-filter"|quick-stats|Browse the normalized works/i);
  assert.doesNotMatch(html, /<a\b[^>]*href="(?:https:\/\/jehlp\.net\/|\/)"/);
});

test("embedded v4 data contains the complete scored four-list survey", async () => {
  const data = await dataset();
  assert.equal(data.meta.agents, 100);
  assert.equal(data.meta.works, 1_136);
  assert.equal(data.meta.observations, 21_939);
  assert.equal(data.meta.selections, 39_998);
  assert.equal(data.meta.verified_singletons, 306);
  assert.equal(data.meta.excluded, 1);
  assert.equal(data.meta.priorStrength, 10);
  assert.equal(data.meta.rankAdjustmentMax, 5);
  assert.equal(data.meta.lowerBoundZ, 1.645);
  assert.ok(data.meta.globalCompositeSd > 8.4 && data.meta.globalCompositeSd < 8.5);
  assert.equal(data.works.length, 1_136);
  assert.equal(data.selections.length, 39_998);
  assert.deepEqual(Array.from(data.axes, (axis) => axis.key), ["influence", "ambition", "fairness", "traditionality", "originality"]);
  assert.deepEqual(Array.from(data.axes, (axis) => axis.weight), [0.1, 0.35, 0.25, 0.1, 0.2]);
  assert.deepEqual(Array.from(data.axes, (axis) => axis.selectionAxis), [false, true, true, true, true]);
  assert.deepEqual(Array.from(data.selectionAxes), ["ambition", "fairness", "traditional_mystery", "originality"]);
  assert.equal(data.axes.reduce((sum, axis) => sum + axis.weight, 0), 1);
  assert.ok(data.works.every((row) => row.length === 35));
  assert.ok(data.selections.every((row) => row.length === 14));
});

test("repository publishes the reconciled aggregate and all 100 source reports", async () => {
  const aggregate = JSON.parse(await source("data/aggregate.json"));
  assert.equal(aggregate.agent_count, 100);
  assert.equal(aggregate.works.length, 1_136);
  assert.equal(aggregate.raw_selections.length, 39_998);
  assert.equal(aggregate.collected_raw_selection_count, 40_000);
  assert.equal(aggregate.excluded_raw_selection_count, 2);
  assert.equal(aggregate.unique_agent_work_observation_count, 21_939);
  assert.equal(aggregate.excluded.length, 1);

  const rawDirectory = path.join(root, "data", "raw_agents");
  const filenames = (await readdir(rawDirectory))
    .filter((filename) => /^agent_\d{3}\.json$/.test(filename))
    .sort();
  assert.equal(filenames.length, 100);

  const reports = await Promise.all(
    filenames.map(async (filename) => JSON.parse(await readFile(path.join(rawDirectory, filename), "utf8"))),
  );
  assert.equal(new Set(reports.map((report) => report.agent_id)).size, 100);
  assert.ok(reports.every((report) => report.works.length >= 100 && report.works.length <= 400));
  assert.ok(reports.every((report) => Object.keys(report.axes).sort().join(",") === "ambition,fairness,originality,traditional_mystery"));
  assert.ok(reports.every((report) => Object.values(report.axes).every((ranking) => ranking.length === 100)));
});

test("known work-unit variants are reconciled and TV labels are unified", async () => {
  const data = await dataset();
  const title = (work) => data.strings[work[1]];
  const medium = (work) => data.strings[work[5]];
  const exact = (query) => data.works.filter((work) => title(work) === query);

  assert.equal(exact("The Southern Reach Series").length, 1);
  assert.equal(exact("The New York Trilogy").length, 1);
  assert.equal(exact("Zero Escape").length, 1);
  assert.equal(exact("Danganronpa").length, 1);
  assert.equal(exact("Danganronpa")[0][10], 82);
  assert.equal(exact("Danganronpa: Trigger Happy Havoc").length, 0);
  assert.equal(exact("Danganronpa 2: Goodbye Despair").length, 0);
  assert.equal(exact("Danganronpa V3: Killing Harmony").length, 0);
  assert.equal(exact("The 8 Mansion Murders").length, 1);
  assert.equal(exact("Sherlock Holmes Canon").length, 1);
  assert.equal(exact("The Valley of Fear").length, 0);
  assert.equal(exact("The Hound of the Baskervilles").length, 1);
  assert.equal(exact("Father Brown Stories").length, 1);
  assert.equal(exact("The Blue Cross").length, 0);
  assert.equal(exact("The Golden Idol Series").length, 1);
  assert.equal(exact("The Case of the Golden Idol").length, 0);
  assert.equal(exact("The Rise of the Golden Idol").length, 0);
  assert.equal(exact("The Golden Idol Series")[0][10], 100);
  assert.equal(exact("Inspector Maigret").length, 0);
  assert.equal(exact("Martin Beck Novels").length, 0);
  assert.equal(exact("Inspector Sejer Novels").length, 0);
  assert.ok(data.works.every((work) => !["tv_season", "tv_episode"].includes(medium(work))));
  assert.ok(data.selections.every((row) => !["tv_season", "tv_episode"].includes(data.strings[row[7]])));
});

test("every retained raw row is a valid selection with five complete integer scores", async () => {
  const data = await dataset();
  const groups = new Map();
  for (const row of data.selections) {
    const [agent, , axis, rank, , , , , workIndex, ...scores] = row;
    assert.ok(Number.isInteger(workIndex) && workIndex >= 0 && workIndex < data.works.length);
    assert.ok(Number.isInteger(rank) && rank >= 1 && rank <= 100);
    assert.equal(scores.length, 5);
    assert.ok(scores.every((score) => Number.isInteger(score) && score >= 0 && score <= 100));
    const key = `${agent}:${axis}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(rank);
  }
  assert.equal(groups.size, 100 * 4);
  let omitted = 0;
  for (const ranks of groups.values()) {
    assert.equal(new Set(ranks).size, ranks.length);
    assert.ok(ranks.length >= 99 && ranks.length <= 100);
    omitted += 100 - ranks.length;
  }
  assert.equal(omitted, 2);
});

test("consensus scores combine rank adjustment, Bayesian shrinkage, and uncertainty", async () => {
  const data = await dataset();
  for (const work of data.works) {
    assert.ok(Number.isInteger(work[10]) && work[10] >= 1 && work[10] <= 100);
    assert.equal(work[11], work[10] / 100);
    const expectedPosterior = data.axes.reduce((sum, axis, index) => sum + axis.weight * work[12 + index], 0);
    const expectedRaw = data.axes.reduce((sum, axis, index) => sum + axis.weight * work[22 + index], 0);
    const expectedPenalty = data.meta.lowerBoundZ * data.meta.globalCompositeSd / Math.sqrt(work[10]);
    assert.ok(Math.abs(expectedPosterior - work[7]) < 1e-5, `${data.strings[work[1]]}: posterior mismatch`);
    assert.ok(Math.abs(expectedRaw - work[8]) < 1e-5, `${data.strings[work[1]]}: raw mismatch`);
    assert.ok(Math.abs(expectedPenalty - work[9]) < 1e-5, `${data.strings[work[1]]}: penalty mismatch`);
    assert.ok(Math.abs(work[7] - work[9] - work[6]) < 1e-5, `${data.strings[work[1]]}: consensus mismatch`);
  }
  assert.deepEqual(
    Array.from(data.works.slice(0, 3), (work) => data.strings[work[1]]),
    ["Return of the Obra Dinn", "The Name of the Rose", "The Murder of Roger Ackroyd"],
  );
  assert.ok(data.works.slice(0, 25).every((work) => work[10] >= 60));
});

test("v3 preserves its four axes while using the v4 uncertainty treatment", async () => {
  const data = (await datasets()).v3;
  assert.equal(data.meta.agents, 100);
  assert.equal(data.meta.works, 1_034);
  assert.equal(data.meta.observations, 19_988);
  assert.equal(data.meta.selections, 29_997);
  assert.equal(data.meta.verified_singletons, 192);
  assert.equal(data.meta.excluded, 3);
  assert.equal(data.meta.priorStrength, 10);
  assert.equal(data.meta.lowerBoundZ, 1.645);
  assert.ok(data.meta.globalCompositeSd > 8.2 && data.meta.globalCompositeSd < 8.3);
  assert.deepEqual(Array.from(data.axes, (axis) => axis.key), ["influence", "ambition", "fairness", "originality"]);
  assert.deepEqual(Array.from(data.axes, (axis) => axis.weight), [0.1, 0.4, 0.25, 0.25]);
  assert.deepEqual(Array.from(data.selectionAxes), ["ambition", "fairness", "originality"]);
  assert.equal(data.axes.reduce((sum, axis) => sum + axis.weight, 0), 1);
  assert.ok(data.works.every((row) => row.length === 30));
  assert.ok(data.selections.every((row) => row.length === 13));

  for (const work of data.works) {
    const expectedPosterior = data.axes.reduce((sum, axis, index) => sum + axis.weight * work[12 + index], 0);
    const expectedPenalty = data.meta.lowerBoundZ * data.meta.globalCompositeSd / Math.sqrt(work[10]);
    assert.ok(Math.abs(expectedPosterior - work[7]) < 1e-5);
    assert.ok(Math.abs(expectedPenalty - work[9]) < 1e-5);
    assert.ok(Math.abs(work[7] - work[9] - work[6]) < 1e-5);
  }
  assert.deepEqual(
    Array.from(data.works.slice(0, 3), (work) => data.strings[work[1]]),
    ["Outer Wilds", "Return of the Obra Dinn", "Umineko When They Cry"],
  );
  const goldenIdol = data.works.filter((work) => data.strings[work[1]] === "The Golden Idol Series");
  assert.equal(goldenIdol.length, 1);
  assert.equal(goldenIdol[0][10], 99);
  const danganronpa = data.works.filter((work) => data.strings[work[1]] === "Danganronpa");
  assert.equal(danganronpa.length, 1);
  assert.equal(danganronpa[0][10], 54);
  assert.equal(data.works.filter((work) => [
    "Danganronpa: Trigger Happy Havoc",
    "Danganronpa 2: Goodbye Despair",
    "Danganronpa V3: Killing Harmony",
  ].includes(data.strings[work[1]])).length, 0);
  assert.ok(data.works.slice(0, 100).every((work) => work[10] >= 10));
});

test("repository publishes the v3 aggregate and all 100 v3 source reports", async () => {
  const aggregate = JSON.parse(await source("data/v3/aggregate.json"));
  assert.equal(aggregate.agent_count, 100);
  assert.equal(aggregate.works.length, 1_034);
  assert.equal(aggregate.raw_selections.length, 29_997);
  assert.equal(aggregate.collected_raw_selection_count, 30_000);
  assert.equal(aggregate.excluded_raw_selection_count, 3);
  assert.equal(aggregate.unique_agent_work_observation_count, 19_988);
  assert.equal(aggregate.method.prior_strength, 10);
  assert.equal(aggregate.method.lower_bound_z, 1.645);
  assert.equal(aggregate.method.confidence_support_denominator, "sqrt(actual agent support)");

  const singletons = JSON.parse(await source("data/v3/audit/singletons.json"));
  const verifiedSingletons = JSON.parse(await source("data/v3/audit/singleton-verification-final.json"));
  assert.deepEqual(verifiedSingletons.map((record) => record.work), singletons);

  const rawDirectory = path.join(root, "data", "v3", "raw_agents");
  const filenames = (await readdir(rawDirectory))
    .filter((filename) => /^agent_\d{3}\.json$/.test(filename))
    .sort();
  assert.equal(filenames.length, 100);
  const reports = await Promise.all(
    filenames.map(async (filename) => JSON.parse(await readFile(path.join(rawDirectory, filename), "utf8"))),
  );
  assert.ok(reports.every((report) => Object.keys(report.axes).sort().join(",") === "ambition,fairness,originality"));
  assert.ok(reports.every((report) => Object.values(report.axes).every((ranking) => ranking.length === 100)));
});

test("application code supports sorting, filtering, pagination, details, and export", async () => {
  const app = await source("assets/app.js");
  assert.match(app, /data-sort/);
  assert.match(app, /state\.sorts/);
  assert.match(app, /directionChoices/);
  assert.match(app, /secondarySort/);
  assert.match(app, /filteredIndices/);
  assert.match(app, /state\.pageSize/);
  assert.match(app, /showModal/);
  assert.match(app, /exportCsv/);
  assert.match(app, /Raw weighted mean/);
  assert.match(app, /Uncertainty penalty/);
  assert.match(app, /placementAdjustedStart \+ axisIndex/);
  assert.match(app, /selectionAxes/);
  assert.match(app, /MYSTERY_CONSENSUS_DATASETS/);
  assert.match(app, /requestedDataset/);
  assert.match(app, /\["v1", "v3"\]\.includes\(requestedDataset\)/);
  assert.match(app, /replaceState\(null, "", canonicalUrl\)/);
  assert.match(app, /categoryDescriptions/);
  assert.match(app, /column\.kind === "year"/);
  assert.match(app, /\["text", "category"\]\.includes/);
  const workColumns = app.slice(app.indexOf("const workColumns"), app.indexOf("const selectionColumns"));
  assert.doesNotMatch(workColumns, /posteriorMean|uncertaintyPenalty|Posterior mean|Uncertainty penalty/);
  assert.doesNotMatch(app, /Borda/i);
  assert.doesNotMatch(app, /nominations|Placement points/i);
});
