(() => {
  "use strict";

  const datasets = window.MYSTERY_CONSENSUS_DATASETS || {};
  const requestedDataset = new URLSearchParams(window.location.search).get("dataset");
  const datasetKey = requestedDataset === "v3" ? "v3" : "v4";
  const data = datasets[datasetKey] || window.MYSTERY_CONSENSUS_DATA;
  if (!data || !Array.isArray(data.works) || !Array.isArray(data.selections)) {
    document.querySelector("#result-status").textContent = "The embedded dataset could not be loaded.";
    return;
  }

  const strings = data.strings;
  const works = data.works;
  const selections = data.selections;
  const axes = data.axes;
  const selectionAxes = data.selectionAxes;
  const selectionLists = data.selectionLists || selectionAxes.map((key) => ({ key, label: key, scoreAxis: key }));
  const selectionLabel = (index) => selectionLists[index]?.label || selectionAxes[index] || "";
  const axisCount = axes.length;
  const adjustedStart = 12;
  const placementAdjustedStart = adjustedStart + axisCount;
  const rawStart = placementAdjustedStart + axisCount;
  const selectionCountStart = rawStart + axisCount;
  const meanPlacementStart = selectionCountStart + selectionAxes.length;
  const text = (id) => (id == null || id < 0 ? "" : strings[id] || "");
  const mediumLabel = (id) => text(id).replaceAll("_", " ");
  const fixed = (value, digits = 2) => (value == null ? "—" : Number(value).toFixed(digits));
  const percent = (value) => `${(Number(value) * 100).toFixed(1)}%`;
  const integer = (value) => Number(value).toLocaleString();
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
  const categoryDescriptions = {
    influence: "Importance to mystery and later works that borrowed from it. Scored after candidate selection; never used to choose candidates.",
    ambition: "Grandeur, complexity, scope, and the challenge of coherently resolving many moving parts.",
    fairness: "Whether revelations follow from rules, evidence, mechanisms, and expectations established beforehand.",
    traditionality: "How closely the work follows the recognizable traditional mystery form. This measures form, not quality.",
    originality: "How distinctive the setting, questions, construction, tricks, and resolution feel to audiences now.",
  };

  const state = {
    view: "works",
    query: "",
    axis: "all",
    medium: "all",
    sorts: [{ key: "rank", direction: 1 }, { key: null, direction: 1 }],
    page: 0,
    pageSize: 50,
    workFilter: null,
    selectedWork: null,
    currentIndices: [],
  };

  const els = {
    search: document.querySelector("#search-input"),
    axisControl: document.querySelector("#axis-control"),
    axis: document.querySelector("#axis-filter"),
    medium: document.querySelector("#medium-filter"),
    pageSize: document.querySelector("#page-size"),
    reset: document.querySelector("#reset-controls"),
    export: document.querySelector("#export-csv"),
    primarySort: document.querySelector("#primary-sort"),
    primaryDirection: document.querySelector("#primary-direction"),
    secondarySort: document.querySelector("#secondary-sort"),
    secondaryDirection: document.querySelector("#secondary-direction"),
    viewButtons: [...document.querySelectorAll(".view-button")],
    activeFilter: document.querySelector("#active-work-filter"),
    activeFilterLabel: document.querySelector("#active-work-filter-label"),
    clearWorkFilter: document.querySelector("#clear-work-filter"),
    resultsKicker: document.querySelector("#results-kicker"),
    resultsTitle: document.querySelector("#results-title"),
    resultStatus: document.querySelector("#result-status"),
    tableHead: document.querySelector("#table-head"),
    tableBody: document.querySelector("#table-body"),
    rangeStatus: document.querySelector("#range-status"),
    pageStatus: document.querySelector("#page-status"),
    previous: document.querySelector("#previous-page"),
    next: document.querySelector("#next-page"),
    dialog: document.querySelector("#work-dialog"),
    dialogClose: document.querySelector("#dialog-close"),
    dialogDone: document.querySelector("#dialog-done"),
    dialogKicker: document.querySelector("#dialog-kicker"),
    dialogTitle: document.querySelector("#dialog-title"),
    dialogSubtitle: document.querySelector("#dialog-subtitle"),
    dialogStats: document.querySelector("#dialog-stats"),
    dialogAxisBody: document.querySelector("#dialog-axis-body"),
    viewWorkPlacements: document.querySelector("#view-work-placements"),
    datasetSummary: document.querySelector("#dataset-summary"),
    datasetTabs: [...document.querySelectorAll("[data-dataset]")],
    categoryGuide: document.querySelector("#category-guide"),
  };

  const workColumns = [
    { key: "rank", label: "Rank", kind: "rank", value: (row) => row[0], show: (row) => row[0], className: "numeric" },
    { key: "title", label: "Title", kind: "text", value: (row) => text(row[1]), show: (row) => text(row[1]), className: "title-cell" },
    { key: "creator", label: "Creator", kind: "text", value: (row) => text(row[3]), show: (row) => text(row[3]), className: "creator-cell" },
    { key: "year", label: "Year", kind: "year", value: (row) => row[4], show: (row) => row[4], className: "numeric" },
    { key: "medium", label: "Medium", kind: "category", value: (row) => mediumLabel(row[5]), show: (row) => mediumLabel(row[5]) },
    { key: "consensusScore", label: "Consensus score", kind: "score", value: (row) => row[6], show: (row) => fixed(row[6]), className: "numeric" },
    { key: "posteriorMean", label: "Posterior mean", kind: "score", value: (row) => row[7], show: (row) => fixed(row[7]), className: "numeric" },
    { key: "uncertaintyPenalty", label: "Uncertainty penalty", kind: "score", value: (row) => row[9], show: (row) => fixed(row[9]), className: "numeric" },
    { key: "support", label: "Raters", kind: "count", value: (row) => row[10], show: (row) => integer(row[10]), className: "numeric" },
    { key: "supportRate", label: "Rater rate", kind: "score", value: (row) => row[11], show: (row) => percent(row[11]), className: "numeric" },
    ...axes.map((axis, index) => ({
      key: axis.key,
      label: axis.short,
      kind: "score",
      value: (row) => row[adjustedStart + index],
      show: (row) => fixed(row[adjustedStart + index]),
      className: "numeric",
    })),
  ];

  const selectionColumns = [
    { key: "agent", label: "Agent", kind: "number", value: (row) => row[0], show: (row) => String(row[0]).padStart(3, "0"), className: "numeric" },
    { key: "axis", label: "Selection criterion", kind: "category", value: (row) => selectionLabel(row[2]), show: (row) => selectionLabel(row[2]) },
    { key: "place", label: "Place", kind: "rank", value: (row) => row[3], show: (row) => row[3], className: "numeric" },
    { key: "rawTitle", label: "Raw title", kind: "text", value: (row) => text(row[4]), show: (row) => text(row[4]), className: "title-cell" },
    { key: "rawCreator", label: "Raw creator", kind: "text", value: (row) => text(row[5]), show: (row) => text(row[5]), className: "creator-cell" },
    { key: "year", label: "Year", kind: "year", value: (row) => row[6], show: (row) => row[6], className: "numeric" },
    { key: "medium", label: "Medium", kind: "category", value: (row) => mediumLabel(row[7]), show: (row) => mediumLabel(row[7]) },
    { key: "canonical", label: "Canonical work", kind: "text", value: (row) => text(works[row[8]][1]), show: (row) => text(works[row[8]][1]), className: "title-cell" },
    { key: "overallRank", label: "Overall rank", kind: "rank", value: (row) => works[row[8]][0], show: (row) => works[row[8]][0], className: "numeric" },
    ...axes.map((axis, index) => ({
      key: `score_${axis.key}`,
      label: `${axis.short} score`,
      kind: "score",
      value: (row) => row[9 + index],
      show: (row) => row[9 + index],
      className: "numeric",
    })),
  ];

  const workSearch = works.map((row) => [text(row[1]), text(row[2]), text(row[3]), mediumLabel(row[5]), row[4]].join(" ").toLocaleLowerCase());
  const selectionSearch = selections.map((row) => [
    `agent ${row[0]}`, text(row[1]), selectionLabel(row[2]), text(row[4]), text(row[5]), row[6],
    mediumLabel(row[7]), text(works[row[8]][1]), text(works[row[8]][3]),
  ].join(" ").toLocaleLowerCase());

  function columns() { return state.view === "works" ? workColumns : selectionColumns; }
  function rows() { return state.view === "works" ? works : selections; }

  function directionChoices(column) {
    if (!column) return [{ value: 1, label: "Ascending" }, { value: -1, label: "Descending" }];
    if (["text", "category"].includes(column.kind)) return [{ value: 1, label: "A to Z" }, { value: -1, label: "Z to A" }];
    if (column.kind === "year") return [{ value: 1, label: "Oldest first" }, { value: -1, label: "Newest first" }];
    if (column.kind === "rank") return [{ value: 1, label: "Best first" }, { value: -1, label: "Worst first" }];
    return [{ value: -1, label: "High to low" }, { value: 1, label: "Low to high" }];
  }

  function defaultDirection(key) {
    return directionChoices(columns().find((column) => column.key === key))[0].value;
  }

  function directionLabel(key, direction) {
    const choice = directionChoices(columns().find((column) => column.key === key)).find((item) => item.value === direction);
    return (choice?.label || "Ascending").toLocaleLowerCase();
  }

  function compareValues(left, right) {
    if (left === right) return 0;
    if (left == null) return 1;
    if (right == null) return -1;
    if (typeof left === "number" && typeof right === "number") return left - right;
    return String(left).localeCompare(String(right), undefined, { numeric: true, sensitivity: "base" });
  }

  function filteredIndices() {
    const source = rows();
    const search = state.view === "works" ? workSearch : selectionSearch;
    const tokens = state.query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
    const filtered = [];
    for (let index = 0; index < source.length; index += 1) {
      const row = source[index];
      if (tokens.length && !tokens.every((token) => search[index].includes(token))) continue;
      if (state.view === "works") {
        if (state.medium !== "all" && text(row[5]) !== state.medium) continue;
      } else {
        if (state.axis !== "all" && row[2] !== Number(state.axis)) continue;
        if (state.medium !== "all" && text(row[7]) !== state.medium) continue;
        if (state.workFilter !== null && row[8] !== state.workFilter) continue;
      }
      filtered.push(index);
    }
    filtered.sort((leftIndex, rightIndex) => {
      for (const sort of state.sorts) {
        if (!sort.key) continue;
        const column = columns().find((item) => item.key === sort.key);
        const comparison = column ? compareValues(column.value(source[leftIndex]), column.value(source[rightIndex])) : 0;
        if (comparison) return comparison * sort.direction;
      }
      return leftIndex - rightIndex;
    });
    return filtered;
  }

  function renderHeader() {
    els.tableHead.innerHTML = columns().map((column) => {
      const priority = state.sorts.findIndex((sort) => sort.key === column.key);
      const active = priority >= 0;
      const direction = active ? state.sorts[priority].direction : 1;
      const ariaSort = priority === 0 ? (direction === 1 ? "ascending" : "descending") : "";
      const marker = active ? ` ${direction === 1 ? "↑" : "↓"}${priority + 1}` : "";
      return `<th class="${escapeHtml(column.className || "")}"${ariaSort ? ` aria-sort="${ariaSort}"` : ""}${active ? ` data-sort-priority="${priority + 1}"` : ""}><button type="button" data-sort="${escapeHtml(column.key)}">${escapeHtml(column.label)}${marker}</button></th>`;
    }).join("");
    els.tableHead.querySelectorAll("[data-sort]").forEach((button) => button.addEventListener("click", () => {
      const key = button.dataset.sort;
      state.sorts[0] = state.sorts[0].key === key
        ? { key, direction: state.sorts[0].direction * -1 }
        : { key, direction: defaultDirection(key) };
      state.sorts[1] = { key: null, direction: 1 };
      state.page = 0;
      render();
    }));
  }

  function workTitleButton(workIndex, label) {
    return `<button type="button" class="row-link" data-open-work="${workIndex}">${escapeHtml(label)}</button>`;
  }

  function renderBody(indices) {
    const source = rows();
    const pageIndices = indices.slice(state.page * state.pageSize, (state.page + 1) * state.pageSize);
    if (!pageIndices.length) {
      els.tableBody.innerHTML = `<tr class="empty-row"><td colspan="${columns().length}">No rows match the current search and filters.</td></tr>`;
      return;
    }
    els.tableBody.innerHTML = pageIndices.map((sourceIndex) => {
      const row = source[sourceIndex];
      const workIndex = state.view === "works" ? sourceIndex : row[8];
      const cells = columns().map((column) => {
        const value = column.show(row);
        const linked = (state.view === "works" && column.key === "title") || (state.view === "selections" && column.key === "canonical");
        return `<td class="${escapeHtml(column.className || "")}" data-column="${escapeHtml(column.key)}">${linked ? workTitleButton(workIndex, value) : escapeHtml(value)}</td>`;
      }).join("");
      return `<tr>${cells}</tr>`;
    }).join("");
    els.tableBody.querySelectorAll("[data-open-work]").forEach((button) => button.addEventListener("click", () => openWork(Number(button.dataset.openWork))));
  }

  function renderFooter(indices) {
    const pages = Math.max(1, Math.ceil(indices.length / state.pageSize));
    if (state.page >= pages) state.page = pages - 1;
    const start = indices.length ? state.page * state.pageSize + 1 : 0;
    const end = Math.min(indices.length, (state.page + 1) * state.pageSize);
    els.rangeStatus.textContent = `${integer(start)}–${integer(end)} of ${integer(indices.length)} rows`;
    els.pageStatus.textContent = `${state.page + 1} / ${pages}`;
    els.previous.disabled = state.page === 0;
    els.next.disabled = state.page >= pages - 1;
  }

  function renderDirectionSelect(select, sort, disabled = false) {
    select.innerHTML = directionChoices(columns().find((column) => column.key === sort.key))
      .map((choice) => `<option value="${choice.value}">${escapeHtml(choice.label)}</option>`).join("");
    select.value = String(sort.direction);
    select.disabled = disabled;
  }

  function renderSortBuilder() {
    const available = columns();
    els.primarySort.innerHTML = available.map((column) => `<option value="${escapeHtml(column.key)}">${escapeHtml(column.label)}</option>`).join("");
    els.primarySort.value = state.sorts[0].key;
    els.secondarySort.innerHTML = ['<option value="">None</option>', ...available.map((column) => `<option value="${escapeHtml(column.key)}"${column.key === state.sorts[0].key ? " disabled" : ""}>${escapeHtml(column.label)}</option>`)].join("");
    els.secondarySort.value = state.sorts[1].key || "";
    renderDirectionSelect(els.primaryDirection, state.sorts[0]);
    renderDirectionSelect(els.secondaryDirection, state.sorts[1], !state.sorts[1].key);
  }

  function renderControls() {
    const isWorks = state.view === "works";
    els.axisControl.hidden = isWorks;
    els.activeFilter.hidden = isWorks || state.workFilter === null;
    if (!els.activeFilter.hidden) els.activeFilterLabel.textContent = `Raw selections for ${text(works[state.workFilter][1])}`;
    els.viewButtons.forEach((button) => {
      const active = button.dataset.view === state.view;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    els.resultsKicker.textContent = isWorks ? "Normalized catalogue" : "Unaggregated source rows";
    els.resultsTitle.textContent = isWorks ? "Works" : "Raw selections";
    renderSortBuilder();
  }

  function render() {
    renderControls();
    renderHeader();
    const indices = filteredIndices();
    const pages = Math.max(1, Math.ceil(indices.length / state.pageSize));
    if (state.page >= pages) state.page = pages - 1;
    state.currentIndices = indices;
    renderBody(indices);
    renderFooter(indices);
    const description = state.sorts.filter((sort) => sort.key).map((sort) => {
      const column = columns().find((item) => item.key === sort.key);
      return `${column.label}, ${directionLabel(sort.key, sort.direction)}`;
    });
    els.resultStatus.textContent = `${integer(indices.length)} matching rows · ${description.join(" · then ")}`;
  }

  function openWork(index) {
    const work = works[index];
    if (!work) return;
    state.selectedWork = index;
    els.dialogKicker.textContent = `Overall rank ${work[0]}`;
    els.dialogTitle.textContent = text(work[1]);
    els.dialogSubtitle.textContent = `${text(work[3])} · ${work[4]} · ${mediumLabel(work[5])}${text(work[2]) ? ` · ${text(work[2])}` : ""}`;
    els.dialogStats.innerHTML = [
      ["Consensus score", fixed(work[6])],
      ["Posterior mean", fixed(work[7])],
      ["Raw weighted mean", fixed(work[8])],
      ["Uncertainty penalty", fixed(work[9])],
      ["Raters", integer(work[10])],
      ["Rater rate", percent(work[11])],
    ].map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("");
    els.dialogAxisBody.innerHTML = axes.map((axis, axisIndex) => {
      const selectionIndex = selectionLists.findIndex((selection) => selection.scoreAxis === axis.key);
      const count = selectionIndex < 0 ? "—" : integer(work[selectionCountStart + selectionIndex]);
      const meanRank = selectionIndex < 0 ? "—" : fixed(work[meanPlacementStart + selectionIndex], 2);
      return `<tr><td>${escapeHtml(axis.label)}</td><td>${(axis.weight * 100).toFixed(0)}%</td><td>${fixed(work[adjustedStart + axisIndex])}</td><td>${fixed(work[placementAdjustedStart + axisIndex])}</td><td>${fixed(work[rawStart + axisIndex])}</td><td>${count}</td><td>${meanRank}</td></tr>`;
    }).join("");
    els.dialog.showModal();
  }

  function closeDialog() { if (els.dialog.open) els.dialog.close(); }

  function switchView(view, options = {}) {
    state.view = view;
    state.page = 0;
    state.sorts = [{ key: view === "works" ? "rank" : "agent", direction: 1 }, { key: null, direction: 1 }];
    state.axis = "all";
    els.axis.value = "all";
    if (!options.keepWorkFilter) state.workFilter = null;
    render();
  }

  function resetControls() {
    state.query = "";
    state.axis = "all";
    state.medium = "all";
    state.workFilter = null;
    state.page = 0;
    state.sorts = [{ key: state.view === "works" ? "rank" : "agent", direction: 1 }, { key: null, direction: 1 }];
    els.search.value = "";
    els.axis.value = "all";
    els.medium.value = "all";
    render();
  }

  function csvCell(value) {
    const string = String(value ?? "");
    return /[",\n]/.test(string) ? `"${string.replaceAll('"', '""')}"` : string;
  }

  function exportCsv() {
    const source = rows();
    const currentColumns = columns();
    const lines = [currentColumns.map((column) => csvCell(column.label)).join(",")];
    state.currentIndices.forEach((index) => lines.push(currentColumns.map((column) => csvCell(column.show(source[index]))).join(",")));
    const blob = new Blob(["\ufeff", lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = state.view === "works"
      ? `mystery-report-${datasetKey}-works.csv`
      : `mystery-report-${datasetKey}-raw-selections.csv`;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function populateControls() {
    els.datasetTabs.forEach((tab) => {
      const active = tab.dataset.dataset === datasetKey;
      tab.classList.toggle("is-active", active);
      if (active) tab.setAttribute("aria-current", "page");
      else tab.removeAttribute("aria-current");
    });
    els.axis.insertAdjacentHTML("beforeend", selectionLists.map((selection, index) => `<option value="${index}">${escapeHtml(selection.label)}</option>`).join(""));
    const media = [...new Set([...works.map((row) => text(row[5])), ...selections.map((row) => text(row[7]))])].sort((a, b) => a.localeCompare(b));
    els.medium.insertAdjacentHTML("beforeend", media.map((medium) => `<option value="${escapeHtml(medium)}">${escapeHtml(medium.replaceAll("_", " "))}</option>`).join(""));
    els.categoryGuide.innerHTML = axes.map((axis) => `<div><dt>${escapeHtml(axis.label)} · ${(axis.weight * 100).toFixed(0)}%</dt><dd>${escapeHtml(categoryDescriptions[axis.key] || "")}</dd></div>`).join("");
    els.datasetSummary.textContent = `Consensus dataset v${data.meta.version} · ${integer(data.meta.agents)} valid agents · ${integer(data.meta.observations)} complete agent–work ratings · ±${fixed(data.meta.rankAdjustmentMax, 0)} placement correction · one-sided 95% support penalty`;
  }

  els.viewButtons.forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
  els.primarySort.addEventListener("change", () => {
    const key = els.primarySort.value;
    state.sorts[0] = { key, direction: defaultDirection(key) };
    if (state.sorts[1].key === key) state.sorts[1] = { key: null, direction: 1 };
    state.page = 0;
    render();
  });
  els.primaryDirection.addEventListener("change", () => { state.sorts[0].direction = Number(els.primaryDirection.value); state.page = 0; render(); });
  els.secondarySort.addEventListener("change", () => {
    const key = els.secondarySort.value || null;
    state.sorts[1] = { key, direction: key ? defaultDirection(key) : 1 };
    state.page = 0;
    render();
  });
  els.secondaryDirection.addEventListener("change", () => { state.sorts[1].direction = Number(els.secondaryDirection.value); state.page = 0; render(); });
  els.search.addEventListener("input", () => { state.query = els.search.value; state.page = 0; render(); });
  els.axis.addEventListener("change", () => { state.axis = els.axis.value; state.page = 0; render(); });
  els.medium.addEventListener("change", () => { state.medium = els.medium.value; state.page = 0; render(); });
  els.pageSize.addEventListener("change", () => { state.pageSize = Number(els.pageSize.value); state.page = 0; render(); });
  els.reset.addEventListener("click", resetControls);
  els.export.addEventListener("click", exportCsv);
  els.previous.addEventListener("click", () => { if (state.page > 0) { state.page -= 1; render(); } });
  els.next.addEventListener("click", () => { if (state.page < Math.ceil(state.currentIndices.length / state.pageSize) - 1) { state.page += 1; render(); } });
  els.clearWorkFilter.addEventListener("click", () => { state.workFilter = null; state.page = 0; render(); });
  els.dialogClose.addEventListener("click", closeDialog);
  els.dialogDone.addEventListener("click", closeDialog);
  els.dialog.addEventListener("click", (event) => { if (event.target === els.dialog) closeDialog(); });
  els.viewWorkPlacements.addEventListener("click", () => {
    if (state.selectedWork == null) return;
    state.query = "";
    state.medium = "all";
    state.workFilter = state.selectedWork;
    els.search.value = "";
    els.medium.value = "all";
    closeDialog();
    switchView("selections", { keepWorkFilter: true });
    document.querySelector("#results").scrollIntoView({ block: "start" });
  });
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLocaleLowerCase() === "k") {
      event.preventDefault();
      els.search.focus();
      els.search.select();
    }
  });

  populateControls();
  render();
})();
