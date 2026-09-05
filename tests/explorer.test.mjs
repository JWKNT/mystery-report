import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

// Small DOM fixture for data/render contracts; real-browser layout and keyboard QA
// is separate. The fixture deliberately uses the production datasets and renderer.
class Element {
  constructor(dataset = {}) {
    this.dataset = dataset;
    this.innerHTML = "";
    this.textContent = "";
    this.value = "all";
    this.listeners = {};
    this.attributes = {};
    this.interactions = [];
    this.classList = { toggle() {} };
  }
  addEventListener(type, callback) { this.listeners[type] = callback; }
  fire(type) { this.listeners[type]?.({ target: this }); }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; }
  insertAdjacentHTML(_position, html) { this.innerHTML += html; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  recordInteraction(kind, options) {
    const interaction = { kind, options: { ...options } };
    this.interactions.push(interaction);
    this.onInteraction?.(interaction);
  }
  focus(options) { this.recordInteraction("focus", options); }
  scrollIntoView(options) { this.recordInteraction("scrollIntoView", options); }
  append() {}
  click() {}
  remove() {}
  querySelectorAll(selector) {
    const [, attribute, value] = selector.match(/^\[data-([\w-]+)(?:="([^"]*)")?\]$/);
    const key = attribute.replace(/-([a-z])/g, (_, character) => character.toUpperCase());
    if (this.buttonMarkup !== this.innerHTML) {
      this.buttonMarkup = this.innerHTML;
      this.buttons = [...this.innerHTML.matchAll(/<button\b([^>]*)>/g)].map((match) => new Element(Object.fromEntries(
        [...match[1].matchAll(/data-([\w-]+)="([^"]*)"/g)]
          .map(([, key, value]) => [key.replace(/-([a-z])/g, (_, character) => character.toUpperCase()), value]),
      )));
    }
    return this.buttons.filter((button) => button.dataset[key] !== undefined && (value === undefined || button.dataset[key] === value));
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

async function explorer(version = "v2") {
  const elements = new Map();
  const get = (selector) => {
    if (!elements.has(selector)) elements.set(selector, new Element());
    return elements.get(selector);
  };
  const views = [new Element({ view: "works" }), new Element({ view: "selections" })];
  const tabs = [new Element({ dataset: "v1" }), new Element({ dataset: "v2" })];
  const downloads = [];
  const enhancements = [];
  class TestURL extends URL {
    static createObjectURL(blob) { downloads.push(blob); return "blob:test"; }
    static revokeObjectURL() {}
  }
  const context = {
    window: {
      location: { search: `?dataset=${version}`, href: `https://example.test/?dataset=${version}` },
      history: { replaceState() {} },
      setTimeout(callback) { callback(); },
      JehlpUI: { enhance(root) { enhancements.push(root); } },
    },
    document: {
      querySelector: get,
      querySelectorAll: (selector) => selector === ".view-button" ? views : tabs,
      addEventListener() {},
      createElement: () => new Element(),
      body: new Element(),
    },
    URL: TestURL, URLSearchParams, Blob,
  };
  const root = new URL("../", import.meta.url);
  for (const name of ["data/v3/consensus-data.js", "data/consensus-data.js", "assets/app.js"])
    vm.runInNewContext(await readFile(new URL(name, root), "utf8"), context);
  const change = (selector, value) => { get(selector).value = value; get(selector).fire("change"); };
  return { get, views, downloads, enhancements, change, data: context.window.MYSTERY_CONSENSUS_DATASETS[version === "v1" ? "v3" : "v4"] };
}

for (const version of ["v1", "v2"]) {
  test(`${version}: pagination renders new rows before focusing and scrolling results`, async () => {
    const ui = await explorer(version);
    const { get, change } = ui;
    const results = get("#results");
    const observations = [];
    results.onInteraction = (interaction) => observations.push({
      ...interaction,
      rows: get("#table-body").innerHTML,
      range: get("#range-status").textContent,
      page: get("#page-status").textContent,
    });
    const expectedInteractions = [
      { kind: "focus", options: { preventScroll: true } },
      { kind: "scrollIntoView", options: { block: "start", behavior: "instant" } },
    ];
    for (const view of ui.views) {
      view.fire("click");
      change("#page-size", "25");
      results.interactions.length = 0;
      observations.length = 0;
      const firstPage = get("#table-body").innerHTML;
      get("#previous-page").fire("click");
      assert.equal(results.interactions.length, 0, "the first-page boundary must not steal focus");
      assert.equal(get("#table-body").innerHTML, firstPage);

      get("#next-page").fire("click");
      const secondPage = get("#table-body").innerHTML;
      assert.notEqual(secondPage, firstPage, "next page must actually replace the rows");
      assert.equal((secondPage.match(/<tr>/g) || []).length, 25);
      assert.deepEqual(results.interactions, expectedInteractions);
      for (const observation of observations) {
        assert.equal(observation.rows, secondPage, "render must finish before focus or scrolling");
        assert.match(observation.range, /^26–50 of /);
        assert.match(observation.page, /^2 \/ /);
      }

      results.interactions.length = 0;
      observations.length = 0;
      get("#previous-page").fire("click");
      assert.equal(get("#table-body").innerHTML, firstPage, "previous page must restore the original rows");
      assert.deepEqual(results.interactions, expectedInteractions);
      for (const observation of observations) {
        assert.equal(observation.rows, firstPage);
        assert.match(observation.range, /^1–25 of /);
        assert.match(observation.page, /^1 \/ /);
      }

      get("#search-input").value = "impossible-unmatched-work-query";
      get("#search-input").fire("input");
      results.interactions.length = 0;
      get("#next-page").fire("click");
      get("#previous-page").fire("click");
      assert.equal(results.interactions.length, 0, "empty results must not focus or scroll on an invalid page turn");
      assert.equal(get("#page-status").textContent, "1 / 1");
      get("#reset-controls").fire("click");
    }
  });

  test(`${version}: responsive work rows preserve every sortable/exported column and pagination`, async () => {
    const ui = await explorer(version);
    const { get, change, data } = ui;
    assert.equal((get("#table-head").innerHTML.match(/<th\b/g) || []).length, 3 + data.axes.length);
    assert.equal((get("#table-head").innerHTML.match(/class="numeric axis-column"/g) || []).length, data.axes.length);
    assert.equal((get("#table-body").innerHTML.match(/<tr>/g) || []).length, 50);
    assert.match(get("#table-head").innerHTML, /↑<\/span>/);
    assert.doesNotMatch(get("#table-head").innerHTML, /[↑↓][12]/);
    assert.equal((get("#primary-sort").innerHTML.match(/<option\b/g) || []).length, 8 + data.axes.length);
    assert.match(get("#table-body").innerHTML, /class="row-meta"/);
    assert.match(get("#table-body").innerHTML, /raters/);
    change("#primary-sort", "creator");
    change("#secondary-sort", "year");
    assert.match(get("#result-status").textContent, /Creator, a to z · then Year, oldest first/);
    assert.equal(get("#secondary-direction").disabled, false);
    change("#page-size", "25");
    get("#next-page").fire("click");
    assert.match(get("#range-status").textContent, /^26–50 of /);
    get("#search-input").value = "impossible-unmatched-work-query";
    get("#search-input").fire("input");
    assert.ok(get("#table-body").innerHTML.includes(`colspan="${3 + data.axes.length}"`));
    assert.equal(get("#next-page").disabled, true);
    get("#reset-controls").fire("click");
    assert.equal(get("#primary-sort").value, "rank");
    get("#export-csv").fire("click");
    const csv = await ui.downloads.at(-1).text();
    assert.equal(csv.split("\n")[0].replace(/^\uFEFF/, "").split(",").length, 8 + data.axes.length);
    assert.equal(csv.split("\n").length, data.works.length + 1);
    assert.match(csv, /Creator,Year,Medium,Consensus score,Raters,Rater rate/);
    assert.equal(ui.enhancements.at(-1), get("#explorer"));
    assert.equal(ui.enhancements.length, 7);
  });

  test(`${version}: wide axis columns retain correct values, sorting, and header focus`, async () => {
    const { get, views, data } = await explorer(version);
    for (const view of views) {
      view.fire("click");
      const isWorks = view.dataset.view === "works";
      const firstRow = get("#table-body").innerHTML.match(/<tr>(.*?)<\/tr>/)[1];
      const sourceIndex = Number(firstRow.match(isWorks ? /data-open-work="(\d+)"/ : /data-selection="(\d+)"/)[1]);
      const source = isWorks ? data.works[sourceIndex] : data.selections[sourceIndex];
      data.axes.forEach((axis, index) => {
        const key = isWorks ? axis.key : `score_${axis.key}`;
        const expected = isWorks ? Number(source[12 + index]).toFixed(2) : source[9 + index];
        assert.ok(firstRow.includes(`<td class="numeric axis-column" data-column="${key}">${expected}</td>`));
        assert.ok(get("#table-head").innerHTML.includes(`class="numeric axis-column" data-column="${key}"`));
        assert.ok(get("#table-head").querySelector(`[data-sort="${key}"]`));
      });
      const sortKey = isWorks ? data.axes[0].key : `score_${data.axes[0].key}`;
      get("#table-head").querySelector(`[data-sort="${sortKey}"]`).fire("click");
      assert.match(get("#result-status").textContent, /high to low/);
      assert.ok(get("#table-head").innerHTML.includes(`data-column="${sortKey}" aria-sort="descending"`));
      assert.deepEqual(get("#table-head").querySelector(`[data-sort="${sortKey}"]`).interactions, [
        { kind: "focus", options: { preventScroll: true } },
      ]);
    }
  });

  test(`${version}: raw rows retain all scores in CSV and the exact selection dialog`, async () => {
    const ui = await explorer(version);
    const { get, change, data } = ui;
    ui.views[1].fire("click");
    assert.equal((get("#table-head").innerHTML.match(/<th\b/g) || []).length, 3 + data.axes.length);
    assert.equal((get("#table-head").innerHTML.match(/class="numeric axis-column"/g) || []).length, data.axes.length);
    assert.equal((get("#primary-sort").innerHTML.match(/<option\b/g) || []).length, 9 + data.axes.length);
    assert.match(get("#table-body").innerHTML, /data-selection="\d+"/);
    assert.match(get("#table-body").innerHTML, /ambition/);
    // Use the listeners created by renderBody rather than parsing UI into domain state.
    const rawButton = get("#table-body").querySelectorAll("[data-open-work]")[0];
    // Capture listener-bearing nodes during the next render.
    const originalQuery = get("#table-body").querySelectorAll.bind(get("#table-body"));
    let buttons;
    get("#table-body").querySelectorAll = (selector) => (buttons = originalQuery(selector));
    change("#axis-filter", "0");
    buttons[0].fire("click");
    assert.equal(get("#work-dialog").open, true);
    assert.equal(get("#dialog-selection").hidden, false);
    assert.match(get("#dialog-selection-stats").innerHTML, /Raw title/);
    assert.match(get("#dialog-selection-stats").innerHTML, /Canonical work/);
    assert.equal((get("#dialog-selection-stats").innerHTML.match(/<dt>/g) || []).length, 9 + data.axes.length);
    const selection = data.selections[Number(buttons[0].dataset.selection)];
    data.axes.forEach((axis, index) => assert.ok(get("#dialog-selection-stats").innerHTML.includes(`<dt>${axis.short} score</dt><dd>${selection[9 + index]}</dd>`)));
    get("#view-work-placements").fire("click");
    assert.equal(get("#work-dialog").open, false);
    assert.equal(get("#axis-filter").value, "all");
    assert.equal(get("#active-work-filter").hidden, false);
    assert.deepEqual(get("#results").interactions.map((interaction) => interaction.kind), ["focus", "scrollIntoView"]);
    get("#reset-controls").fire("click");
    change("#primary-sort", `score_${data.axes[0].key}`);
    assert.match(get("#result-status").textContent, /score, high to low/);
    get("#export-csv").fire("click");
    const csv = await ui.downloads.at(-1).text();
    assert.equal(csv.split("\n")[0].replace(/^\uFEFF/, "").split(",").length, 9 + data.axes.length);
    assert.equal(csv.split("\n").length, data.selections.length + 1);
    assert.match(csv, /Raw title,Raw creator,Year,Medium,Canonical work,Overall rank/);
    assert.ok(rawButton.dataset.selection !== undefined);
  });
}
