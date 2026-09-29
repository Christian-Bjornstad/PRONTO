(() => {
  "use strict";

  const tablist = document.querySelector('[role="tablist"]');
  if (!tablist) return;

  const topbar = document.querySelector('.report-topbar');
  if (topbar) {
    new ResizeObserver(() => {
      document.documentElement.style.setProperty('--report-topbar-height', `${topbar.getBoundingClientRect().height}px`);
    }).observe(topbar);
  }

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
  } else if (!window.location.hash) {
    activateTab(document.getElementById("tab-variant-review"), { focus: false, updateHash: false });
  }

  const editButton = document.getElementById("edit-btn");
  document.getElementById('preview-report')?.addEventListener('click', (event) => {
    event.preventDefault();
    activateTab(document.getElementById('tab-tumour-board'));
  });
  const editControls = Array.from(document.querySelectorAll(".report-edit-controls"));
  const dirtyLabel = document.getElementById("dirty-lbl");
  const reviewDownload = document.getElementById("download-review");
  const saveButton = document.getElementById("save-btn");
  const finalizeButton = document.getElementById("finalize-btn");
  const finalizeHint = document.getElementById("finalize-hint");
  const corrections = new Map();
  const removedCorrections = new Set();
  let savedCorrections = new Map();
  let reviewDirty = false;
  let saving = false;
  let finalizing = false;
  const attributionConfig = document.getElementById('attribution-config');
  const initialsRequired = attributionConfig?.dataset.required === 'true';
  let askingInitials = false;
  async function actionInitials(action) {
    if (!initialsRequired) return undefined;
    if (askingInitials) return null;
    askingInitials = true;
    try { return await window.requestDeclaredInitials(action); }
    finally { askingInitials = false; }
  }
  function updateAttribution() {
    const element = document.getElementById('review-attribution');
    if (!element) return;
    const entries = [];
    if (reviewState.lastSavedAttribution) entries.push(`Saved by: ${reviewState.lastSavedAttribution.declaredInitials}`);
    if (reviewState.finalizationAttribution) entries.push(`Finalized by: ${reviewState.finalizationAttribution.declaredInitials}`);
    element.textContent = entries.join(' · ') || 'No initials recorded';
    element.hidden = entries.length === 0;
    const savedBy = document.getElementById('board-saved-attribution');
    if (savedBy) savedBy.textContent = reviewState.lastSavedAttribution
      ? `Last saved by: ${reviewState.lastSavedAttribution.declaredInitials}`
      : 'Last saved by: no initials recorded';
    const savedRevision = document.getElementById('board-saved-revision');
    if (savedRevision) savedRevision.textContent = `Saved revision: ${reviewState.revision}`;
  }

  function refreshDirty() {
    const sourceDirty = corrections.size > 0 || removedCorrections.size > 0;
    dirtyLabel.textContent = finalizing ? "Finalizing …" : saving ? "Saving …" : sourceDirty ? "Unsaved source corrections" :
      reviewDirty ? "Unsaved review" : saveButton?.dataset.saveUrl ? "All changes saved" : "Local view only";
    if (reviewDownload) reviewDownload.disabled = sourceDirty;
    if (saveButton?.dataset.saveUrl) saveButton.disabled = saving || finalizing ||
      reviewState.status !== "DRAFT" || (!sourceDirty && !reviewDirty);
    if (finalizeButton) {
      finalizeButton.disabled = saving || finalizing || sourceDirty || reviewDirty || reviewState.status !== "DRAFT";
      if (finalizeHint) finalizeHint.textContent = sourceDirty || reviewDirty ? "Save changes before finalizing." : "";
    }
  }

  function recordCorrection(path, candidate) {
    const saved = savedCorrections.get(path);
    if (!candidate) {
      corrections.delete(path);
      if (saved) removedCorrections.add(path);
      else removedCorrections.delete(path);
    } else if (saved && candidate.correctedValue === saved.correctedValue &&
               candidate.reason === saved.reason) {
      corrections.delete(path);
      removedCorrections.delete(path);
    } else {
      corrections.set(path, candidate);
      removedCorrections.delete(path);
    }
    refreshDirty();
  }

  function updateReason(path, value) {
    const correction = corrections.get(path) || savedCorrections.get(path);
    if (correction) recordCorrection(path, { ...correction, reason: value.trim() });
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
  if (tmbGauge && !tmbGauge.disabled) {
    const number = document.getElementById("tmb-edit-value");
    const reason = document.getElementById("tmb-correction-reason");
    const status = document.getElementById("tmb-correction-status");
    const display = document.querySelector('[data-metric="tmb"] .metric-card__value');
    const original = Number(tmbGauge.dataset.originalValue);
    const path = tmbGauge.dataset.correctionPath;
    let currentValue = Number(number.value);

    function updateTmb(raw) {
      const value = Number(raw);
      if (raw === "" || !Number.isFinite(value) || value < 0) {
        number.value = String(currentValue);
        return;
      }
      currentValue = value;
      const changed = value !== original;
      if (changed) {
        recordCorrection(path, {
          path, originalValue: original, correctedValue: value, reason: reason.value.trim(),
        });
      } else {
        recordCorrection(path, null);
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

    tmbGauge.addEventListener("input", () => {
      if (editButton && editButton.getAttribute('aria-pressed') !== 'true') editButton.click();
      updateTmb(tmbGauge.value);
    });
    number.addEventListener("change", () => updateTmb(number.value));
    reason.addEventListener("input", () => {
      updateReason(path, reason.value);
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
        input.setCustomValidity("Enter a value between 0 and 100");
        input.reportValidity();
        return;
      }
      input.setCustomValidity("");
      const changed = value !== original;
      card.querySelector(".metric-card__value").textContent =
        `${new Intl.NumberFormat("nb-NO", { maximumFractionDigits: 2 }).format(value)} %`;
      card.dataset.correctionPending = String(changed);
      if (changed) {
        recordCorrection(path, {
          path, originalValue: original, correctedValue: value, reason: reason.value.trim(),
        });
      } else {
        recordCorrection(path, null);
        reason.value = "";
      }
      reason.disabled = !changed;
      reason.required = changed;
      refreshDirty();
    });
    reason.addEventListener("input", () => {
      updateReason(path, reason.value);
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
      field.querySelector("dd").textContent = proposed || "Not reported";
      field.dataset.correctionPending = String(changed);
      if (changed) {
        recordCorrection(path, {
          path,
          originalValue: field.dataset.availability === "UNAVAILABLE" ? null : original,
          correctedValue: proposed || null,
          reason: reason.value.trim(),
        });
      } else {
        recordCorrection(path, null);
        reason.value = "";
      }
      reason.disabled = !changed;
      reason.required = changed;
      refreshDirty();
    });
    reason.addEventListener("input", () => {
      updateReason(path, reason.value);
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
    count.textContent = `${visible} of ${rows.length} occurrences`;
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
      `${reviewed} of ${uniqueDecisions.size} variants reviewed`;
    document.querySelectorAll('#key-variant-table tr[data-variant-id]').forEach((row) => {
      const activity = activities.get(row.dataset.variantId);
      const decision = activity?.reportingDecision || 'UNREVIEWED';
      const igv = activity?.igvAssessment || 'NOT_REVIEWED';
      const decisionLabel = { UNREVIEWED: 'Unreviewed', INCLUDE: 'Included', EXCLUDE: 'Excluded' };
      const igvLabel = { NOT_REVIEWED: 'Not reviewed', SUPPORTS: 'Supports', DOES_NOT_SUPPORT: 'Does not support', INCONCLUSIVE: 'Inconclusive', NOT_APPLICABLE: 'Not applicable' };
      row.querySelector('[data-review-summary="decision"]').textContent = decisionLabel[decision];
      row.querySelector('[data-review-summary="decision"]').dataset.status = decision;
      row.querySelector('[data-review-summary="igv"]').textContent = igvLabel[igv];
    });
    const decisions = Array.from(activities.values());
    document.getElementById('kpi-inc').textContent = String(decisions.filter((item) => item.reportingDecision === 'INCLUDE').length);
    document.getElementById('kpi-exc').textContent =
      `${decisions.filter((item) => item.reportingDecision === 'EXCLUDE').length} excluded · ${reviewDirty ? 'unsaved review' : `revision ${reviewState.revision}`}`;
    rows.forEach((row) => {
      row.querySelectorAll('[data-quick-field]').forEach((button) => {
        const select = row.querySelector(`select[data-review-field="${button.dataset.quickField}"]`);
        button.setAttribute('aria-pressed', String(select?.value === button.dataset.quickValue));
      });
    });
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
      const groups = document.querySelectorAll('#panel-cnv-plots .plot-group');
      if (groups.length) {
        groups.forEach((group) => { group.hidden = group.id !== targetId; });
      } else {
        document.querySelectorAll("#panel-cnv-plots .plot-figure").forEach((figure) => {
          figure.hidden = figure.id !== targetId;
        });
      }
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
    const printStatus = document.createElement('p');
    printStatus.id = 'print-status';
    printStatus.setAttribute('role', 'status');
    printMdt.after(printStatus);
    let pendingPrint = null;
    let printing = false;
    printMdt.addEventListener("click", async () => {
      if (printing || askingInitials || saving || finalizing) return;
      if (attributionConfig?.dataset.printUrl && (reviewDirty || corrections.size || removedCorrections.size)) {
        printStatus.textContent = 'Save changes before printing.';
        return;
      }
      if (!attributionConfig?.dataset.printUrl) {
        printStatus.textContent = 'Local print — not recorded in the database.';
        document.body.classList.add('print-mdt');
        window.print();
        return;
      }
      printing = true;
      printMdt.disabled = true;
      try {
        const initials = await window.requestDeclaredInitials('Initials for printing');
        if (initials === null) return;
        if (reviewDirty || corrections.size || removedCorrections.size || saving || finalizing) {
          printStatus.textContent = 'Save changes before printing.';
          return;
        }
        const revision = reviewState.revision;
        if (!pendingPrint || pendingPrint.revision !== revision || pendingPrint.declaredInitials !== initials) {
          pendingPrint = {schemaVersion: '1.0', revision, declaredInitials: initials, requestId: crypto.randomUUID()};
        }
        const response = await fetch(attributionConfig.dataset.printUrl, {
          method: 'POST', credentials: 'same-origin',
          headers: {'Content-Type': 'application/json', 'X-CSRFToken': attributionConfig.dataset.csrfToken},
          body: JSON.stringify(pendingPrint),
        });
        const event = await response.json();
        if (!response.ok || event.requestId !== pendingPrint.requestId || event.reportId !== reviewState.reportId ||
            event.revision !== revision || event.declaredInitials !== initials || event.method !== 'SELF_REPORTED' ||
            event.action !== 'PRINT_REQUESTED' || !Number.isFinite(Date.parse(event.requestedAt))) throw new Error('Print not acknowledged');
        if (reviewDirty || corrections.size || removedCorrections.size || reviewState.revision !== revision) throw new Error('Review changed');
        printStatus.textContent = `Print requested by ${initials} · revision ${revision} · ${event.requestedAt} · ${reviewState.status}`;
        pendingPrint = null;
        document.body.classList.add('print-mdt');
        window.print();
      } catch (_) {
        printStatus.textContent = 'Print was not recorded, or this view changed. Save the latest revision and try again.';
      } finally {
        printing = false;
        printMdt.disabled = false;
      }
    });
    window.addEventListener("afterprint", () => document.body.classList.remove("print-mdt"));
  }

  const reviewData = document.getElementById("review-state-data");
  if (!reviewData) return;
  const reviewState = JSON.parse(reviewData.textContent);
  savedCorrections = new Map(reviewState.valueCorrections.map((item) => [item.path, item]));
  const activities = new Map(reviewState.variantReviews.map((item) => [item.variantId, item]));
  const feedback = document.getElementById("review-feedback");
  const download = document.getElementById("download-review");
  const saveError = document.getElementById("save-error");
  const recovery = document.getElementById("save-recovery");
  const saveFeedback = document.getElementById("save-feedback");
  updateReviewSummary();
  refreshDirty();

  function localDraft() {
    const draft = JSON.parse(JSON.stringify(reviewState));
    const byPath = new Map(draft.valueCorrections.map((item) => [item.path, item]));
    removedCorrections.forEach((path) => byPath.delete(path));
    corrections.forEach((item, path) => {
      byPath.set(path, {
        ...item, author: saveButton.dataset.actorId, timestamp: new Date().toISOString(),
      });
    });
    draft.valueCorrections = Array.from(byPath.values());
    return draft;
  }

  function downloadJson(data, suffix) {
    const blob = new Blob([JSON.stringify(data, null, 2) + "\n"], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${reviewState.reportId}-${suffix}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  if (saveButton?.dataset.saveUrl) {
    const editableInputs = Array.from(document.querySelectorAll(
      '.report-edit-controls input, textarea[data-review-note], #variant-table select[data-review-field], #variant-table textarea[data-review-field], [data-bulk-decision], [data-quick-field], #qc-review-status, #qc-review-comment'
    ));
    function lockInputs() {
      const previouslyDisabled = editableInputs.map((input) => input.disabled);
      editableInputs.forEach((input) => { input.disabled = true; });
      return () => editableInputs.forEach((input, index) => { input.disabled = previouslyDisabled[index]; });
    }
    window.addEventListener("beforeunload", (event) => {
      if (!reviewDirty && !corrections.size && !removedCorrections.size && !saving && !finalizing) return;
      event.preventDefault();
      event.returnValue = "";
    });
    document.getElementById("export-local-draft").addEventListener("click", () => {
      downloadJson(localDraft(), "local-draft");
    });
    document.getElementById("reload-latest").addEventListener("click", () => {
      if (window.confirm("Local changes will be lost. Load the latest saved revision?")) {
        reviewDirty = false;
        corrections.clear();
        removedCorrections.clear();
        window.location.reload();
      }
    });
    saveButton.addEventListener("click", async () => {
      if (saving || askingInitials || (!reviewDirty && !corrections.size && !removedCorrections.size)) return;
      saveError.hidden = true;
      recovery.hidden = true;
      saveFeedback.hidden = true;
      const missingReason = Array.from(corrections.values()).find((item) => !item.reason);
      if (missingReason) {
        saveError.textContent = "Give a reason for every source correction before saving.";
        saveError.hidden = false;
        saveFeedback.hidden = false;
        document.querySelector(`[data-correction-path="${missingReason.path}"]`)?.focus();
        return;
      }
      const declaredInitials = await actionInitials('Initials for saving');
      if (declaredInitials === null) return;
      const baseRevision = reviewState.revision;
      const draft = localDraft();
      const hadCorrectionEdits = corrections.size > 0 || removedCorrections.size > 0;
      saving = true;
      const unlockInputs = lockInputs();
      refreshDirty();
      feedback.textContent = "Saving changes …";
      try {
        const response = await fetch(saveButton.dataset.saveUrl, {
          method: "POST", credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-CSRFToken": saveButton.dataset.csrfToken },
          body: JSON.stringify({ schemaVersion: "1.0", reportId: reviewState.reportId, baseRevision, draft, declaredInitials }),
        });
        const result = await response.json();
        if (response.status === 409 && result.error?.code === "REVISION_CONFLICT") {
          saveError.textContent = `Another saved revision exists (${result.error.currentRevision}). Your local changes remain. Download them before loading the latest revision.`;
          saveError.hidden = false;
          recovery.hidden = false;
          saveFeedback.hidden = false;
          return;
        }
        if (!response.ok || result.review?.reportId !== reviewState.reportId ||
            result.review?.revision !== baseRevision + 1) {
          throw new Error("Save was not confirmed. Changes remain local.");
        }
        Object.assign(reviewState, result.review);
        updateAttribution();
        activities.clear();
        reviewState.variantReviews.forEach((item) => activities.set(item.variantId, item));
        corrections.clear();
        removedCorrections.clear();
        savedCorrections = new Map(reviewState.valueCorrections.map((item) => [item.path, item]));
        reviewDirty = false;
        feedback.textContent = `Saved as revision ${reviewState.revision}.`;
        if (hadCorrectionEdits) window.location.reload();
      } catch (_error) {
        saveError.textContent = "Save could not be confirmed. Changes remain local. Try again or download a local copy.";
        saveError.hidden = false;
        recovery.hidden = false;
        saveFeedback.hidden = false;
      } finally {
        saving = false;
        unlockInputs();
        refreshDirty();
        updateReviewSummary();
      }
    });
    if (finalizeButton) finalizeButton.addEventListener("click", async () => {
      if (saving || finalizing || askingInitials || reviewDirty || corrections.size || removedCorrections.size || reviewState.status !== "DRAFT") return;
      if (!window.confirm("Finalize this report? Further editing will be locked.")) return;
      const declaredInitials = await actionInitials('Initials for finalization');
      if (declaredInitials === null) return;
      saveError.hidden = true;
      recovery.hidden = true;
      saveFeedback.hidden = true;
      const baseRevision = reviewState.revision;
      finalizing = true;
      const unlockInputs = lockInputs();
      refreshDirty();
      let completed = false;
      try {
        const response = await fetch(finalizeButton.dataset.finalizeUrl, {
          method: "POST", credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-CSRFToken": saveButton.dataset.csrfToken },
          body: JSON.stringify({
            schemaVersion: "1.0", reportId: reviewState.reportId,
            baseRevision, draft: localDraft(), declaredInitials,
          }),
        });
        const result = await response.json();
        if (response.status === 409 && result.error?.code === "REVISION_CONFLICT") {
          saveError.textContent = `This report is now at revision ${result.error.currentRevision}. Local data remains; download a copy before loading the latest revision.`;
          saveError.hidden = false;
          recovery.hidden = false;
          saveFeedback.hidden = false;
          return;
        }
        if (!response.ok || result.review?.reportId !== reviewState.reportId ||
            result.review?.revision !== baseRevision + 1 || result.review?.status !== "FINAL") {
          throw new Error("Finalization was not confirmed.");
        }
        Object.assign(reviewState, result.review);
        reviewDirty = false;
        corrections.clear();
        removedCorrections.clear();
        completed = true;
      } catch (_error) {
        saveError.textContent = "Finalization could not be confirmed. This view remains a draft. Check the latest saved revision before trying again.";
        saveError.hidden = false;
        recovery.hidden = false;
        saveFeedback.hidden = false;
      } finally {
        finalizing = false;
        unlockInputs();
        refreshDirty();
        if (completed) window.location.reload();
      }
    });
  }

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
      item.append(` · ${row.cells[1].textContent} · ${row.cells[2].textContent} · Classification: `);
      item.append(row.querySelector('select[data-review-field="clinicalClassification"]').selectedOptions[0].textContent);
      const comment = row.querySelector('textarea[data-review-field="comment"]').value.trim();
      if (comment) item.append(` · Comment: ${comment}`);
      list.append(item);
    });
    list.hidden = shown.size === 0;
    document.getElementById("board-empty").hidden = shown.size !== 0;
    const selectedCount = document.getElementById('preview-selected-count');
    if (selectedCount) selectedCount.textContent = String(shown.size);
  }
  updateBoardFindings();

  table.tBodies[0].addEventListener('click', (event) => {
    const button = event.target.closest('button[data-quick-field]');
    if (!button || reviewState.status !== 'DRAFT' || saving || finalizing) return;
    const select = button.closest('tr').querySelector(`select[data-review-field="${button.dataset.quickField}"]`);
    if (!select) return;
    const defaultValue = button.dataset.quickField === 'reportingDecision' ? 'UNREVIEWED' : 'UNCLASSIFIED';
    select.value = select.value === button.dataset.quickValue ? defaultValue : button.dataset.quickValue;
    select.dispatchEvent(new Event('change', { bubbles: true }));
  });

  ['status', 'comment'].forEach((field) => {
    const input = document.getElementById(`qc-review-${field}`);
    input?.addEventListener(field === 'comment' ? 'input' : 'change', () => {
      if (reviewState.status !== 'DRAFT' || saving || finalizing) return;
      reviewState.runQcAssessment[field] = input.value;
      reviewDirty = true;
      refreshDirty();
      feedback.textContent = 'QC assessment changed. Save the review to keep it.';
    });
  });

  document.querySelectorAll("textarea[data-review-note]").forEach((input) => {
    input.addEventListener("input", () => {
      if (reviewState.status !== "DRAFT") return;
      const key = input.dataset.reviewNote;
      reviewState.notes[key] = input.value;
      document.querySelector(`[data-print-note="${key}"]`).textContent = input.value;
      reviewDirty = true;
      refreshDirty();
      feedback.textContent = "Changes are not saved. Download ReviewState to keep a local copy.";
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
    const noun = eligible.size === 1 ? "unique variant" : "unique variants";
    const action = button.dataset.bulkDecision === "INCLUDE" ? "included" : "excluded";
    if (!window.confirm(`Mark ${eligible.size} ${noun} as ${action}? Only visible, unreviewed variants will change.`)) return;
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
    feedback.textContent = `${eligible.size} ${noun} changed locally. Changes are not saved.`;
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
    feedback.textContent = "Changes are not saved. Download ReviewState to keep a local copy.";
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
    feedback.textContent = "Changes are not saved. Download ReviewState to keep a local copy.";
  });

  download.addEventListener("click", () => {
    const exported = JSON.parse(JSON.stringify(reviewState));
    if (exported.status !== "FINAL" && !saveButton?.dataset.saveUrl) {
      exported.revision += 1;
      exported.updatedAt = new Date().toISOString();
    }
    downloadJson(exported, "review-state");
    feedback.textContent = "ReviewState downloaded. Store the file in approved storage.";
  });
})();
