// Click-through from a semantic search snippet result → the matching card in
// #snippet-list. Scrolls the card into view and briefly flashes a highlight.
// Delegated listener so HTMX re-renders of the results pane keep working.
(function () {
  "use strict";

  function flash(el) {
    el.classList.add("snippet-card-flash");
    window.setTimeout(function () {
      el.classList.remove("snippet-card-flash");
    }, 1400);
  }

  document.addEventListener("click", function (evt) {
    var btn = evt.target.closest && evt.target.closest(".search-snippet-goto");
    if (!btn) return;
    var targetId = btn.getAttribute("data-snippet-target");
    if (!targetId) return;
    var target = document.getElementById(targetId);
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    flash(target);
  });

  // Clearing the search input (native X on type=search, or backspacing to empty)
  // wipes the results container so stale hits don't linger.
  function clearResultsIfEmpty(evt) {
    var el = evt.target;
    if (!el || el.id !== "search-input") return;
    if (el.value.trim().length === 0) {
      var container = document.getElementById("search-results-container");
      if (container) container.innerHTML = "";
    }
  }
  document.addEventListener("input", clearResultsIfEmpty);
  document.addEventListener("search", clearResultsIfEmpty);
})();
