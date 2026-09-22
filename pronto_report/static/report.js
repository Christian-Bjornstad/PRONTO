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
})();
