// "Show all" broaden: flips the results wrapper's data-scope to "all" so CSS
// reveals out-of-scope cards, without hitting the backend (SC-005). Also syncs
// the scope <select> so the UI stays coherent.
(function () {
  "use strict";

  document.addEventListener("click", function (evt) {
    var link = evt.target.closest && evt.target.closest(".search-broaden");
    if (!link) return;
    evt.preventDefault();
    var wrap = document.getElementById("search-results");
    if (wrap) wrap.setAttribute("data-scope", "all");
    var select = document.getElementById("search-scope-select");
    if (select) select.value = "all";
  });
})();
