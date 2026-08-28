/* Runs in <head> before first paint: applies a stored theme so the page never
   flashes the wrong one. Everything else about theming lives in dashboard.js. */
(function () {
  "use strict";
  try {
    var saved = localStorage.getItem("kos:theme");
    if (saved === "light" || saved === "dark") {
      document.documentElement.setAttribute("data-theme", saved);
    }
  } catch (e) {
    /* storage blocked (private window, site-data off) — system theme still applies */
  }
})();
