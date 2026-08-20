import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function source(relativePath) {
  return readFile(path.join(root, relativePath), "utf8");
}

async function dataset() {
  const context = { window: {} };
  vm.runInNewContext(await source("data/consensus-data.js"), context);
  return context.window.MYSTERY_CONSENSUS_DATA;
}

test("page embeds its theme assets and exposes the core controls", async () => {
  const html = await source("index.html");
  assert.match(html, /assets\/theme\.js/);
  assert.match(html, /assets\/base\.css/);
  assert.match(html, /data-view="works"/);
  assert.match(html, /data-view="selections"/);
  assert.match(html, /id="search-input"/);
  assert.match(html, /id="primary-sort"/);
  assert.match(html, /id="secondary-sort"/);
  assert.match(html, /id="export-csv"/);
  assert.match(html, /id="work-dialog"/);
  assert.match(html, /What each category measures/);
  assert.match(html, /Rank-adjusted mean/);
  assert.match(html, /Influence · 10%[\s\S]*Ambition · 40%[\s\S]*Fairness · 25%[\s\S]*Originality · 25%/);
  assert.doesNotMatch(html, /id="method"|Placement-only Borda consensus/);
  assert.doesNotMatch(html, /id="status-filter"|quick-stats|Browse the normalized works/i);
});

test("embedded data contains the complete scored three-list survey", async () => {
  const data = await dataset();
  assert.equal(data.meta.agents, 100);
  assert.equal(data.meta.works, 1_037);
  assert.equal(data.meta.observations, 20_032);
  assert.equal(data.meta.selections, 29_991);
  assert.equal(data.meta.verified_singletons, 192);
  assert.equal(data.meta.excluded, 3);
  assert.equal(data.meta.priorStrength, 5);
  assert.equal(data.meta.rankAdjustmentMax, 5);
  assert.equal(data.meta.lowerBoundZ, 1);
  assert.ok(data.meta.globalCompositeSd > 8 && data.meta.globalCompositeSd < 9);
  assert.equal(data.works.length, 1_037);
  assert.equal(data.selections.length, 29_991);
  assert.deepEqual(Array.from(data.axes, (axis) => axis.key), ["influence", "ambition", "fairness", "originality"]);
  assert.deepEqual(Array.from(data.axes, (axis) => axis.weight), [0.1, 0.4, 0.25, 0.25]);
  assert.deepEqual(Array.from(data.axes, (axis) => axis.selectionAxis), [false, true, true, true]);
  assert.deepEqual(Array.from(data.selectionAxes), ["ambition", "fairness", "originality"]);
  assert.equal(data.axes.reduce((sum, axis) => sum + axis.weight, 0), 1);
  assert.ok(data.works.every((row) => row.length === 30));
  assert.ok(data.selections.every((row) => row.length === 13));
});

test("known work-unit variants are reconciled and TV labels are unified", async () => {
  const data = await dataset();
  const title = (work) => data.strings[work[1]];
  const medium = (work) => data.strings[work[5]];
  const exact = (query) => data.works.filter((work) => title(work) === query);

  assert.equal(exact("The Southern Reach Series").length, 1);
  assert.equal(exact("The New York Trilogy").length, 1);
  assert.equal(exact("Zero Escape").length, 1);
  assert.equal(exact("Danganronpa: Trigger Happy Havoc").length, 1);
  assert.equal(exact("The 8 Mansion Murders").length, 1);
  assert.equal(exact("Professor Layton").length, 0);
  assert.ok(data.works.every((work) => !["tv_season", "tv_episode"].includes(medium(work))));
  assert.ok(data.selections.every((row) => !["tv_season", "tv_episode"].includes(data.strings[row[7]])));
});

test("every raw row is a valid selection with four complete integer scores", async () => {
  const data = await dataset();
  const groups = new Map();
  for (const row of data.selections) {
    const [agent, , axis, rank, , , , , workIndex, ...scores] = row;
    assert.ok(Number.isInteger(workIndex) && workIndex >= 0 && workIndex < data.works.length);
    assert.ok(Number.isInteger(rank) && rank >= 1 && rank <= 100);
    assert.ok(scores.every((score) => Number.isInteger(score) && score >= 0 && score <= 100));
    const key = `${agent}:${axis}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(rank);
  }
  assert.equal(groups.size, 100 * 3);
  let omitted = 0;
  for (const ranks of groups.values()) {
    assert.equal(new Set(ranks).size, ranks.length);
    assert.ok(ranks.length >= 99 && ranks.length <= 100);
    omitted += 100 - ranks.length;
  }
  assert.equal(omitted, 9);
});

test("consensus scores combine rank adjustment, Bayesian shrinkage, and uncertainty", async () => {
  const data = await dataset();
  for (const work of data.works) {
    assert.ok(Number.isInteger(work[10]) && work[10] >= 1 && work[10] <= 100);
    assert.equal(work[11], work[10] / 100);
    const expectedPosterior = data.axes.reduce((sum, axis, index) => sum + axis.weight * work[12 + index], 0);
    const expectedRaw = data.axes.reduce((sum, axis, index) => sum + axis.weight * work[20 + index], 0);
    const expectedPenalty = data.meta.globalCompositeSd / Math.sqrt(work[10] + data.meta.priorStrength);
    assert.ok(Math.abs(expectedPosterior - work[7]) < 1e-5, `${data.strings[work[1]]}: posterior mismatch`);
    assert.ok(Math.abs(expectedRaw - work[8]) < 1e-5, `${data.strings[work[1]]}: raw mismatch`);
    assert.ok(Math.abs(expectedPenalty - work[9]) < 1e-5, `${data.strings[work[1]]}: penalty mismatch`);
    assert.ok(Math.abs(work[7] - work[9] - work[6]) < 1e-5, `${data.strings[work[1]]}: consensus mismatch`);
  }
  assert.deepEqual(
    Array.from(data.works.slice(0, 3), (work) => data.strings[work[1]]),
    ["Outer Wilds", "Return of the Obra Dinn", "Umineko When They Cry"],
  );
  assert.ok(data.works.slice(0, 25).every((work) => work[10] >= 68));
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
  assert.match(app, /work\[16 \+ axisIndex\]/);
  assert.match(app, /selectionAxes/);
  assert.match(app, /column\.kind === "year"/);
  assert.match(app, /\["text", "category"\]\.includes/);
  assert.doesNotMatch(app, /Borda/i);
  assert.doesNotMatch(app, /nominations|Placement points/i);
});
