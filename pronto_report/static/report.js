(() => {
  "use strict";

  const tablist = document.querySelector('[role="tablist"]');
  if (!tablist) return;

  const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));
  const panels = tabs.map((tab) => document.getElementById(tab.getAttribute("aria-controls")));

  function activateTab(nextTab, { focus = true, updateHash = true } = {}) {
    const nextIndex = tabs.indexOf(nextTab);
    if (nextIndex < 0 || !panels[nextIndex]) return;

    tabs.forEach((tab, index) => {
      const selected = index === nextIndex;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
      panels[index].hidden = !selected;
    });

    if (focus) nextTab.focus();
    if (updateHash) history.replaceState(null, "", `#${panels[nextIndex].id}`);
  }

  tablist.addEventListener("click", (event) => {
    const tab = event.target.closest('[role="tab"]');
    if (tab && tablist.contains(tab)) activateTab(tab);
  });

  tablist.addEventListener("keydown", (event) => {
    const currentIndex = tabs.indexOf(event.target);
    if (currentIndex < 0) return;

    let nextIndex;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    if (nextIndex === undefined) return;

    event.preventDefault();
    activateTab(tabs[nextIndex]);
  });

  const hashPanel = document.getElementById(window.location.hash.slice(1));
  if (hashPanel?.getAttribute("role") === "tabpanel") {
    const hashTab = tabs.find((tab) => tab.getAttribute("aria-controls") === hashPanel.id);
    if (hashTab) activateTab(hashTab, { focus: false, updateHash: false });
  }

  const tmbGauge = document.getElementById("tmb-gauge");
  if (tmbGauge) {
    const number = document.getElementById("tmb-edit-value");
    const reason = document.getElementById("tmb-correction-reason");
    const display = document.querySelector('[data-metric="tmb"] .metric-card__value');
    const dirtyLabel = document.getElementById("dirty-lbl");
    const reviewDownload = document.getElementById("download-review");
    const original = Number(tmbGauge.dataset.originalValue);
    let pendingTmbCorrection = null;

    function updateTmb(raw) {
      const value = Number(raw);
      if (!Number.isFinite(value) || value < 0) return;
      pendingTmbCorrection = value === original ? null : { originalValue: original, correctedValue: value };
      number.value = String(value);
      tmbGauge.value = String(Math.min(value, Number(tmbGauge.max)));
      display.textContent = `${new Intl.NumberFormat("nb-NO", { maximumFractionDigits: 1 }).format(value)} mut/Mb`;
      reason.disabled = pendingTmbCorrection === null;
      if (!pendingTmbCorrection) reason.value = "";
      dirtyLabel.textContent = pendingTmbCorrection ? "Ulagret TMB-korreksjon" : "Kun lokal visning";
      if (reviewDownload) reviewDownload.disabled = pendingTmbCorrection !== null;
    }

    tmbGauge.addEventListener("input", () => updateTmb(tmbGauge.value));
    number.addEventListener("change", () => updateTmb(number.value));
  }

  const table = document.getElementById("variant-table");
  const search = document.getElementById("variant-search");
  if (!table || !search) return;
  const rows = Array.from(table.tBodies[0].querySelectorAll("tr[data-occurrence-id]"));
  const count = document.getElementById("variant-count");
  const noMatch = document.getElementById("variant-no-match");

  function filterRows() {
    const query = search.value.trim().toLocaleLowerCase("nb");
    let visible = 0;
    rows.forEach((row) => {
      row.hidden = !row.dataset.search.includes(query);
      if (!row.hidden) visible += 1;
    });
    count.textContent = `${visible} av ${rows.length} varianter`;
    noMatch.hidden = visible !== 0 || rows.length === 0;
  }
  search.addEventListener("input", filterRows);

  table.tHead.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-sort]");
    if (!button) return;
    const column = button.dataset.sort;
    const header = button.closest("th");
    const direction = header.getAttribute("aria-sort") === "ascending" ? "descending" : "ascending";
    table.tHead.querySelectorAll("th[aria-sort]").forEach((item) => item.removeAttribute("aria-sort"));
    header.setAttribute("aria-sort", direction);
    const sorted = rows.map((row, index) => ({ row, index }));
    sorted.sort((left, right) => {
      const a = column === "vaf" ? Number(left.row.dataset.vaf || -1) : left.row.cells[0].textContent;
      const b = column === "vaf" ? Number(right.row.dataset.vaf || -1) : right.row.cells[0].textContent;
      const comparison = column === "vaf" ? a - b : a.localeCompare(b, "nb");
      return (direction === "ascending" ? comparison : -comparison) || left.index - right.index;
    });
    sorted.forEach(({ row }) => table.tBodies[0].append(row));
  });

  const plotDialog = document.getElementById("plot-dialog");
  let plotTrigger = null;
  document.addEventListener("click", (event) => {
    const selector = event.target.closest("button[data-plot-select]");
    if (selector) {
      const targetId = selector.dataset.plotSelect;
      document.querySelectorAll("#panel-cnv-plots .plot-figure").forEach((figure) => {
        figure.hidden = figure.id !== targetId;
      });
      document.querySelectorAll("button[data-plot-select]").forEach((button) => {
        button.setAttribute("aria-pressed", String(button === selector));
      });
      return;
    }
    const enlarge = event.target.closest("button[data-enlarge]");
    if (!enlarge) return;
    const figure = document.getElementById(enlarge.dataset.enlarge);
    const source = figure?.querySelector("img");
    if (!source) return;
    plotTrigger = enlarge;
    const image = document.getElementById("dialog-plot-image");
    image.src = source.src;
    image.alt = source.alt;
    document.getElementById("dialog-plot-caption").textContent = figure.querySelector("figcaption").textContent;
    plotDialog.showModal();
    document.getElementById("close-plot").focus();
  });
  document.getElementById("close-plot").addEventListener("click", () => plotDialog.close());
  plotDialog.addEventListener("close", () => plotTrigger?.focus());

  const reviewData = document.getElementById("review-state-data");
  if (!reviewData) return;
  const reviewState = JSON.parse(reviewData.textContent);
  const feedback = document.getElementById("review-feedback");
  const download = document.getElementById("download-review");

  table.tBodies[0].addEventListener("change", (event) => {
    const control = event.target.closest("select[data-review-field]");
    if (!control || reviewState.status === "FINAL") return;
    const variantId = control.dataset.variantId;
    let activity = reviewState.variantReviews.find((item) => item.variantId === variantId);
    if (!activity) {
      activity = {
        variantId,
        reportingDecision: "UNREVIEWED",
        clinicalClassification: "UNCLASSIFIED",
        igvAssessment: "NOT_REVIEWED",
      };
      reviewState.variantReviews.push(activity);
    }
    activity[control.dataset.reviewField] = control.value;
    table.tBodies[0].querySelectorAll("select[data-variant-id]").forEach((peer) => {
      if (peer.dataset.variantId === variantId && peer.dataset.reviewField === control.dataset.reviewField) {
        peer.value = control.value;
      }
    });
    feedback.textContent = "Endringer er ikke lagret. Last ned ReviewState for å bevare dem.";
  });

  download.addEventListener("click", () => {
    if (reviewState.status !== "FINAL") {
      reviewState.revision += 1;
      reviewState.updatedAt = new Date().toISOString();
    }
    const blob = new Blob([JSON.stringify(reviewState, null, 2) + "\n"], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${reviewState.reportId}-review-state.json`;
    link.click();
    URL.revokeObjectURL(url);
    feedback.textContent = "ReviewState er lastet ned. Oppbevar filen i godkjent lagring.";
  });
})();
