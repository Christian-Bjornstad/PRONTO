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

  const editButton = document.getElementById("edit-btn");
  const editControls = Array.from(document.querySelectorAll(".report-edit-controls"));
  const dirtyLabel = document.getElementById("dirty-lbl");
  const reviewDownload = document.getElementById("download-review");
  const corrections = new Map();
  let reviewDirty = false;

  function refreshDirty() {
    const sourceDirty = corrections.size > 0;
    dirtyLabel.textContent = sourceDirty ? "Ulagrede kildekorreksjoner" :
      reviewDirty ? "Ulagret gjennomgang" : "Kun lokal visning";
    if (reviewDownload) reviewDownload.disabled = sourceDirty;
  }

  if (editButton && !editButton.disabled) {
    editButton.addEventListener("click", () => {
      const editing = editButton.getAttribute("aria-pressed") !== "true";
      editButton.setAttribute("aria-pressed", String(editing));
      editButton.textContent = `Edit mode: ${editing ? "ON" : "OFF"}`;
      editControls.forEach((control) => { control.hidden = !editing; });
    });
  }

  const tmbGauge = document.getElementById("tmb-gauge");
  if (tmbGauge) {
    const number = document.getElementById("tmb-edit-value");
    const reason = document.getElementById("tmb-correction-reason");
    const status = document.getElementById("tmb-correction-status");
    const display = document.querySelector('[data-metric="tmb"] .metric-card__value');
    const original = Number(tmbGauge.dataset.originalValue);
    const path = tmbGauge.dataset.correctionPath;
    let currentValue = original;

    function updateTmb(raw) {
      const value = Number(raw);
      if (raw === "" || !Number.isFinite(value) || value < 0) {
        number.value = String(currentValue);
        return;
      }
      currentValue = value;
      const changed = value !== original;
      if (changed) {
        corrections.set(path, {
          path, originalValue: original, correctedValue: value, reason: reason.value.trim(),
        });
      } else {
        corrections.delete(path);
      }
      number.value = String(value);
      tmbGauge.value = String(Math.min(value, Number(tmbGauge.max)));
      display.textContent = `${new Intl.NumberFormat("nb-NO", { maximumFractionDigits: 1 }).format(value)} mut/Mb`;
      reason.disabled = !changed;
      reason.required = changed;
      status.hidden = !changed;
      if (!changed) reason.value = "";
      refreshDirty();
    }

    tmbGauge.addEventListener("input", () => updateTmb(tmbGauge.value));
    number.addEventListener("change", () => updateTmb(number.value));
    reason.addEventListener("input", () => {
      const correction = corrections.get(path);
      if (correction) correction.reason = reason.value.trim();
    });
  }

  document.querySelectorAll("input[data-metric-correction-path]").forEach((input) => {
    const card = input.closest("[data-metric]");
    const reason = document.getElementById(`${card.dataset.metric}-correction-reason`);
    const original = Number(input.dataset.originalValue);
    const path = input.dataset.metricCorrectionPath;
    input.addEventListener("change", () => {
      const value = Number(input.value);
      if (!input.value || !Number.isFinite(value) || value < 0 || value > 100) {
        input.setCustomValidity("Oppgi en verdi mellom 0 og 100");
        input.reportValidity();
        return;
      }
      input.setCustomValidity("");
      const changed = value !== original;
      card.querySelector(".metric-card__value").textContent =
        `${new Intl.NumberFormat("nb-NO", { maximumFractionDigits: 2 }).format(value)} %`;
      card.dataset.correctionPending = String(changed);
      if (changed) {
        corrections.set(path, {
          path, originalValue: original, correctedValue: value, reason: reason.value.trim(),
        });
      } else {
        corrections.delete(path);
        reason.value = "";
      }
      reason.disabled = !changed;
      reason.required = changed;
      refreshDirty();
    });
    reason.addEventListener("input", () => {
      const correction = corrections.get(path);
      if (correction) correction.reason = reason.value.trim();
    });
  });

  document.querySelectorAll("[data-fact] input[data-correction-path]").forEach((input) => {
    const field = input.closest("[data-fact]");
    const reason = document.getElementById(`${field.dataset.fact}-correction-reason`);
    const path = input.dataset.correctionPath;
    const original = input.dataset.originalValue;
    input.addEventListener("input", () => {
      const proposed = input.value.trim();
      const changed = proposed !== original;
      field.querySelector("dd").textContent = proposed || "Ikke oppgitt";
      field.dataset.correctionPending = String(changed);
      if (changed) {
        corrections.set(path, {
          path,
          originalValue: field.dataset.availability === "UNAVAILABLE" ? null : original,
          correctedValue: proposed || null,
          reason: reason.value.trim(),
        });
      } else {
        corrections.delete(path);
        reason.value = "";
      }
      reason.disabled = !changed;
      reason.required = changed;
      refreshDirty();
    });
    reason.addEventListener("input", () => {
      const correction = corrections.get(path);
      if (correction) correction.reason = reason.value.trim();
    });
  });

  const table = document.getElementById("variant-table");
  const search = document.getElementById("variant-search");
  if (!table || !search) return;
  const rows = Array.from(table.tBodies[0].querySelectorAll("tr[data-occurrence-id]"));
  const commentsByVariant = new Map();
  rows.forEach((row) => {
    const comment = row.querySelector('textarea[data-review-field="comment"]');
    if (!comment) return;
    const peers = commentsByVariant.get(comment.dataset.variantId) || [];
    peers.push(comment);
    commentsByVariant.set(comment.dataset.variantId, peers);
  });
  const count = document.getElementById("variant-count");
  const noMatch = document.getElementById("variant-no-match");
  const reviewFilterButtons = Array.from(document.querySelectorAll("[data-review-filter]"));
  const bulkButtons = Array.from(document.querySelectorAll("[data-bulk-decision]"));
  let reviewFilter = "all";

  function decisionForRow(row) {
    return row.querySelector('select[data-review-field="reportingDecision"]')?.value || "UNREVIEWED";
  }

  function classificationForRow(row) {
    return row.querySelector('select[data-review-field="clinicalClassification"]')?.value || "UNCLASSIFIED";
  }

  function filterRows() {
    const query = search.value.trim().toLocaleLowerCase("nb");
    let visible = 0;
    rows.forEach((row) => {
      const matchesReview = reviewFilter === "all" ||
        (reviewFilter === "PATHOGENIC" || reviewFilter === "UNCERTAIN"
          ? classificationForRow(row) === reviewFilter
          : decisionForRow(row) === reviewFilter);
      row.hidden = !row.dataset.search.includes(query) || !matchesReview;
      if (!row.hidden) visible += 1;
    });
    count.textContent = `${visible} av ${rows.length} forekomster`;
    noMatch.hidden = visible !== 0 || rows.length === 0;
    const hasEligible = rows.some((row) => !row.hidden && decisionForRow(row) === "UNREVIEWED");
    bulkButtons.forEach((button) => { button.disabled = !hasEligible; });
  }
  search.addEventListener("input", filterRows);

  function updateReviewSummary() {
    if (!reviewFilterButtons.length) return;
    const counts = { all: rows.length, INCLUDE: 0, EXCLUDE: 0, UNREVIEWED: 0, PATHOGENIC: 0, UNCERTAIN: 0 };
    const uniqueDecisions = new Map();
    rows.forEach((row) => {
      const decision = decisionForRow(row);
      counts[decision] += 1;
      const classification = classificationForRow(row);
      if (classification in counts) counts[classification] += 1;
      const variantId = row.querySelector("select[data-variant-id]").dataset.variantId;
      uniqueDecisions.set(variantId, decision);
    });
    reviewFilterButtons.forEach((button) => {
      button.querySelector("span").textContent = String(counts[button.dataset.reviewFilter]);
    });
    const reviewed = Array.from(uniqueDecisions.values()).filter((decision) => decision !== "UNREVIEWED").length;
    const progress = document.getElementById("review-progress-bar");
    progress.max = Math.max(uniqueDecisions.size, 1);
    progress.value = reviewed;
    document.getElementById("review-progress").textContent =
      `${reviewed} av ${uniqueDecisions.size} varianter vurdert`;
    filterRows();
  }

  reviewFilterButtons.forEach((button) => button.addEventListener("click", () => {
    reviewFilter = button.dataset.reviewFilter;
    reviewFilterButtons.forEach((item) => {
      item.setAttribute("aria-pressed", String(item === button));
    });
    filterRows();
  }));

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

  const printMdt = document.getElementById("print-mdt-btn");
  if (printMdt) {
    printMdt.addEventListener("click", () => {
      document.body.classList.add("print-mdt");
      window.print();
    });
    window.addEventListener("afterprint", () => document.body.classList.remove("print-mdt"));
  }

  const reviewData = document.getElementById("review-state-data");
  if (!reviewData) return;
  const reviewState = JSON.parse(reviewData.textContent);
  const activities = new Map(reviewState.variantReviews.map((item) => [item.variantId, item]));
  const feedback = document.getElementById("review-feedback");
  const download = document.getElementById("download-review");
  updateReviewSummary();

  function updateBoardFindings() {
    const list = document.getElementById("board-findings");
    if (!list) return;
    list.replaceChildren();
    const shown = new Set();
    rows.forEach((row) => {
      if (decisionForRow(row) !== "INCLUDE") return;
      const variantId = row.querySelector("select[data-variant-id]").dataset.variantId;
      if (shown.has(variantId)) return;
      shown.add(variantId);
      const item = document.createElement("li");
      const gene = document.createElement("strong");
      gene.textContent = row.cells[0].textContent;
      item.append(gene);
      item.append(` · ${row.cells[1].textContent} · ${row.cells[2].textContent} · Klassifikasjon: `);
      item.append(row.querySelector('select[data-review-field="clinicalClassification"]').selectedOptions[0].textContent);
      const comment = row.querySelector('textarea[data-review-field="comment"]').value.trim();
      if (comment) item.append(` · Kommentar: ${comment}`);
      list.append(item);
    });
    list.hidden = shown.size === 0;
    document.getElementById("board-empty").hidden = shown.size !== 0;
  }
  updateBoardFindings();

  document.querySelectorAll("textarea[data-review-note]").forEach((input) => {
    input.addEventListener("input", () => {
      if (reviewState.status !== "DRAFT") return;
      const key = input.dataset.reviewNote;
      reviewState.notes[key] = input.value;
      document.querySelector(`[data-print-note="${key}"]`).textContent = input.value;
      reviewDirty = true;
      refreshDirty();
      feedback.textContent = "Endringer er ikke lagret. Last ned ReviewState for å bevare dem.";
    });
  });

  function activityFor(variantId) {
    let activity = activities.get(variantId);
    if (!activity) {
      activity = {
        variantId,
        reportingDecision: "UNREVIEWED",
        clinicalClassification: "UNCLASSIFIED",
        igvAssessment: "NOT_REVIEWED",
      };
      activities.set(variantId, activity);
      reviewState.variantReviews.push(activity);
    }
    return activity;
  }

  bulkButtons.forEach((button) => button.addEventListener("click", () => {
    if (reviewState.status !== "DRAFT") return;
    const eligible = new Set(rows.filter((row) => !row.hidden && decisionForRow(row) === "UNREVIEWED")
      .map((row) => row.querySelector("select[data-variant-id]").dataset.variantId));
    if (!eligible.size) return;
    const noun = eligible.size === 1 ? "unik variant" : "unike varianter";
    const action = button.dataset.bulkDecision === "INCLUDE" ? "inkludert" : "ekskludert";
    if (!window.confirm(`Merk ${eligible.size} ${noun} som ${action}? Kun synlige, ikke-vurderte varianter endres. Kodende status er ikke verifisert.`)) return;
    eligible.forEach((variantId) => {
      activityFor(variantId).reportingDecision = button.dataset.bulkDecision;
    });
    rows.forEach((row) => {
      const select = row.querySelector('select[data-review-field="reportingDecision"]');
      if (eligible.has(select.dataset.variantId)) select.value = button.dataset.bulkDecision;
    });
    reviewDirty = true;
    refreshDirty();
    updateReviewSummary();
    updateBoardFindings();
    feedback.textContent = `${eligible.size} ${noun} endret lokalt. Endringene er ikke lagret.`;
  }));

  table.tBodies[0].addEventListener("change", (event) => {
    const control = event.target.closest("select[data-review-field]");
    if (!control || reviewState.status === "FINAL") return;
    const variantId = control.dataset.variantId;
    const activity = activityFor(variantId);
    activity[control.dataset.reviewField] = control.value;
    reviewDirty = true;
    refreshDirty();
    table.tBodies[0].querySelectorAll("select[data-variant-id]").forEach((peer) => {
      if (peer.dataset.variantId === variantId && peer.dataset.reviewField === control.dataset.reviewField) {
        peer.value = control.value;
      }
    });
    updateReviewSummary();
    updateBoardFindings();
    feedback.textContent = "Endringer er ikke lagret. Last ned ReviewState for å bevare dem.";
  });

  table.tBodies[0].addEventListener("input", (event) => {
    const control = event.target.closest('textarea[data-review-field="comment"]');
    if (!control || reviewState.status === "FINAL") return;
    const variantId = control.dataset.variantId;
    activityFor(variantId).comment = control.value;
    (commentsByVariant.get(variantId) || []).forEach((peer) => {
      if (peer !== control && peer.dataset.variantId === variantId) peer.value = control.value;
    });
    reviewDirty = true;
    refreshDirty();
    updateBoardFindings();
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
