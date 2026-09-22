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
})();
