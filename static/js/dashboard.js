/* Kandula OS dashboard — vanilla JS, one page, no build step.
   The server computes every number (see api/services/metrics.py); this file
   only renders them, filters the lists, and handles input. */
(function () {
  "use strict";

  var CACHE_KEY = "kos:state";
  var ETAG_KEY = "kos:etag";
  var THEME_KEY = "kos:theme";

  var $ = function (id) { return document.getElementById(id); };
  var msg = $("message");
  var main = $("main");
  var authBtn = $("auth-btn");
  var themeBtn = $("theme-btn");
  var paletteBtn = $("palette-btn");
  var palette = $("palette");
  var paletteInput = $("palette-input");
  var paletteResults = $("palette-results");
  var searchInput = $("search");
  var showDone = $("show-done");

  var state = null;
  var filters = { text: "", priority: "all", done: false };
  var paletteIndex = 0;
  var paletteItems = [];

  /* ---------- tiny helpers ---------- */

  function store(key, value) {
    try {
      if (value === null) { localStorage.removeItem(key); }
      else { localStorage.setItem(key, value); }
    } catch (e) { /* storage unavailable — the page works without it */ }
  }

  function read(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (text !== undefined && text !== null) { n.textContent = String(text); }
    return n;
  }

  function clear(node) { while (node.firstChild) { node.removeChild(node.firstChild); } }

  function show(text, isError) {
    msg.hidden = false;
    msg.textContent = text;
    msg.className = "msg" + (isError ? " error" : "");
  }

  function localToday() {
    var d = new Date();
    return d.getFullYear() + "-" +
      String(d.getMonth() + 1).padStart(2, "0") + "-" +
      String(d.getDate()).padStart(2, "0");
  }

  function daysBetween(fromISO, toISO) {
    var a = Date.parse(fromISO + "T00:00:00");
    var b = Date.parse(toISO + "T00:00:00");
    return Math.round((b - a) / 86400000);
  }

  function dueLabel(due, today) {
    var d = daysBetween(today, due);
    if (d === 0) { return "today"; }
    if (d === 1) { return "tomorrow"; }
    if (d === -1) { return "1d late"; }
    if (d < 0) { return Math.abs(d) + "d late"; }
    if (d <= 7) { return "in " + d + "d"; }
    return due;
  }

  /* ---------- theme ---------- */

  function currentTheme() {
    var set = document.documentElement.getAttribute("data-theme");
    if (set) { return set; }
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function toggleTheme() {
    var next = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    store(THEME_KEY, next);
  }

  themeBtn.addEventListener("click", toggleTheme);

  /* ---------- rendering ---------- */

  function renderTiles(m) {
    $("m-open").textContent = m.open;
    $("m-open-sub").textContent = m.total + " tracked";

    $("m-overdue").textContent = m.overdue;
    $("m-overdue-sub").textContent = m.overdue ? "needs attention" : "all clear";
    $("m-overdue").parentNode.className = "tile" + (m.overdue ? " alert" : " good");

    $("m-today").textContent = m.due_today;
    $("m-today-sub").textContent = m.due_this_week + " this week";

    $("m-rate").textContent = Math.round(m.completion_rate * 100) + "%";
    $("m-rate-sub").textContent = m.done + " done";
  }

  function renderFocus(m, byId) {
    var list = $("focus");
    clear(list);
    if (!m.focus.length) {
      list.appendChild(el("p", "empty", "Nothing open. Enjoy it."));
      return;
    }
    m.focus.forEach(function (id) {
      var t = byId[id];
      if (!t) { return; }
      var li = el("li");
      li.appendChild(el("span", "prio " + t.priority.toLowerCase(), t.priority));
      var body = el("span", "task-title", t.title);
      if (t.project) { body.appendChild(el("span", "tag", t.project)); }
      li.appendChild(body);
      if (t.due) {
        var overdue = m.overdue_ids.indexOf(t.id) !== -1;
        li.appendChild(el("span", "due" + (overdue ? " is-overdue" : ""), dueLabel(t.due, m.today)));
      }
      list.appendChild(li);
    });
  }

  var PRIORITY_COLOR = { P1: "var(--clay)", P2: "var(--amber)", P3: "var(--sage)" };

  function renderPriorityChart(m) {
    var host = $("chart-priority");
    clear(host);
    host.appendChild(el("p", "chart-title", "Open by priority"));
    var max = Math.max(1, m.by_priority.P1, m.by_priority.P2, m.by_priority.P3);
    ["P1", "P2", "P3"].forEach(function (key) {
      var count = m.by_priority[key];
      var row = el("div", "bar-row");
      row.appendChild(el("span", "bar-label", key));
      var track = el("div", "bar-track");
      var fill = el("div", "bar-fill");
      fill.style.width = (count / max * 100) + "%";
      fill.style.background = PRIORITY_COLOR[key];
      track.appendChild(fill);
      row.appendChild(track);
      row.appendChild(el("span", "bar-count", count));
      host.appendChild(row);
    });
  }

  var SVG_NS = "http://www.w3.org/2000/svg";

  function svg(tag, attrs) {
    var n = document.createElementNS(SVG_NS, tag);
    Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    return n;
  }

  function renderTrendChart(history) {
    var host = $("chart-trend");
    clear(host);
    host.appendChild(el("p", "chart-title", "Open tasks over time"));

    var points = (history || []).slice(-30);
    if (points.length < 2) {
      host.appendChild(el("p", "empty", "Two syncs needed before a trend appears."));
      return;
    }

    var w = 300, h = 68, pad = 3;
    var max = Math.max.apply(null, points.map(function (p) { return p.open; })) || 1;
    var stepX = (w - pad * 2) / (points.length - 1);
    var coords = points.map(function (p, i) {
      return [pad + i * stepX, h - pad - (p.open / max) * (h - pad * 2)];
    });

    var line = coords.map(function (c, i) {
      return (i ? "L" : "M") + c[0].toFixed(1) + " " + c[1].toFixed(1);
    }).join(" ");

    var chart = svg("svg", {
      viewBox: "0 0 " + w + " " + h,
      preserveAspectRatio: "none",
      role: "img",
      "aria-label": "Open tasks across the last " + points.length + " syncs"
    });
    chart.appendChild(svg("path", {
      d: line + " L" + coords[coords.length - 1][0].toFixed(1) + " " + (h - pad) +
         " L" + coords[0][0].toFixed(1) + " " + (h - pad) + " Z",
      fill: "var(--clay-wash)"
    }));
    chart.appendChild(svg("path", {
      d: line, fill: "none", stroke: "var(--clay)",
      "stroke-width": "2", "stroke-linejoin": "round", "stroke-linecap": "round",
      "vector-effect": "non-scaling-stroke"
    }));
    var last = coords[coords.length - 1];
    chart.appendChild(svg("circle", {
      cx: last[0].toFixed(1), cy: last[1].toFixed(1), r: "2.5", fill: "var(--clay)",
      "vector-effect": "non-scaling-stroke"
    }));
    host.appendChild(chart);

    var range = el("p", "chart-title", points[0].date + "  →  " + points[points.length - 1].date);
    range.style.marginTop = "8px";
    range.style.marginBottom = "0";
    host.appendChild(range);
  }

  function matches(task) {
    if (!filters.done && task.done) { return false; }
    if (filters.priority !== "all" && task.priority !== filters.priority) { return false; }
    if (!filters.text) { return true; }
    var hay = (task.title + " " + (task.project || "")).toLowerCase();
    return hay.indexOf(filters.text) !== -1;
  }

  function renderTasks() {
    var m = state.metrics;
    var list = $("tasks");
    var empty = $("tasks-empty");
    clear(list);

    var visible = (state.tasks || []).filter(matches);
    if (!visible.length) {
      empty.hidden = false;
      empty.textContent = filters.text || filters.priority !== "all"
        ? "No tasks match this filter."
        : "No open tasks. Add one in TASKS.md and sync.";
      return;
    }
    empty.hidden = true;

    visible.forEach(function (t) {
      var li = el("li");
      li.appendChild(el("span", "prio " + t.priority.toLowerCase(), t.priority));
      var body = el("span", "task-title" + (t.done ? " is-done" : ""), t.title);
      if (t.project) { body.appendChild(el("span", "tag", t.project)); }
      li.appendChild(body);
      if (t.due) {
        var overdue = m.overdue_ids.indexOf(t.id) !== -1;
        var soon = !overdue && daysBetween(m.today, t.due) <= 2;
        li.appendChild(el("span",
          "due" + (overdue ? " is-overdue" : soon ? " is-soon" : ""),
          dueLabel(t.due, m.today)));
      }
      list.appendChild(li);
    });
  }

  function renderProjects() {
    var list = $("projects");
    clear(list);
    var counts = {};
    state.metrics.by_project.forEach(function (r) { counts[r.name] = r; });

    var projects = state.projects || [];
    if (!projects.length) {
      list.appendChild(el("p", "empty", "No project files in memory/ yet."));
      return;
    }
    projects.forEach(function (p) {
      var li = el("li");
      li.appendChild(el("span", "status " + p.status, p.status));
      var body = el("div", "proj-body");
      body.appendChild(el("span", "proj-name", p.name));
      if (p.next_action) { body.appendChild(el("span", "next", "→ " + p.next_action)); }
      li.appendChild(body);
      var row = counts[p.name];
      if (row) { li.appendChild(el("span", "counts", row.open + " open")); }
      list.appendChild(li);
    });
  }

  function render(next) {
    if (next.empty) {
      show("No state synced yet. Run `python scripts/sync_state.py` from the repo root.");
      return;
    }
    state = next;
    var byId = {};
    (state.tasks || []).forEach(function (t) { byId[t.id] = t; });

    msg.hidden = true;
    $("last-sync").textContent = "synced " + new Date(state.generated_at).toLocaleString();

    renderTiles(state.metrics);
    renderFocus(state.metrics, byId);
    renderPriorityChart(state.metrics);
    renderTrendChart(state.history);
    renderTasks();
    renderProjects();

    main.hidden = false;
    requestAnimationFrame(function () { main.classList.add("loaded"); });
  }

  /* ---------- filters ---------- */

  searchInput.addEventListener("input", function () {
    filters.text = searchInput.value.trim().toLowerCase();
    if (state) { renderTasks(); }
  });

  showDone.addEventListener("change", function () {
    filters.done = showDone.checked;
    if (state) { renderTasks(); }
  });

  Array.prototype.forEach.call(document.querySelectorAll(".chip"), function (chip) {
    chip.addEventListener("click", function () {
      filters.priority = chip.dataset.prio;
      Array.prototype.forEach.call(document.querySelectorAll(".chip"), function (c) {
        c.classList.toggle("is-on", c === chip);
      });
      if (state) { renderTasks(); }
    });
  });

  /* ---------- command palette ---------- */

  var COMMANDS = [
    { kind: "cmd", label: "Toggle theme", run: toggleTheme },
    { kind: "cmd", label: "Clear filters", run: function () {
        filters = { text: "", priority: "all", done: false };
        searchInput.value = "";
        showDone.checked = false;
        Array.prototype.forEach.call(document.querySelectorAll(".chip"), function (c) {
          c.classList.toggle("is-on", c.dataset.prio === "all");
        });
        if (state) { renderTasks(); }
      } },
    { kind: "cmd", label: "Refresh from server", run: function () {
        if (firebase.auth().currentUser) { loadState(firebase.auth().currentUser, true); }
      } },
    { kind: "cmd", label: "Sign out", run: function () { firebase.auth().signOut(); } }
  ];

  function paletteCandidates(query) {
    var q = query.trim().toLowerCase();
    var out = COMMANDS.filter(function (c) {
      return !q || c.label.toLowerCase().indexOf(q) !== -1;
    });
    if (state && q) {
      (state.tasks || []).forEach(function (t) {
        if (t.title.toLowerCase().indexOf(q) !== -1) {
          out.push({ kind: t.priority, label: t.title, run: function () {
            searchInput.value = t.title;
            filters.text = t.title.toLowerCase();
            renderTasks();
            document.getElementById("tasks").scrollIntoView({ block: "center" });
          } });
        }
      });
      (state.projects || []).forEach(function (p) {
        if (p.name.toLowerCase().indexOf(q) !== -1) {
          out.push({ kind: "proj", label: p.name, run: function () {
            document.getElementById("projects").scrollIntoView({ block: "center" });
          } });
        }
      });
    }
    return out.slice(0, 12);
  }

  function renderPalette() {
    clear(paletteResults);
    paletteItems.forEach(function (item, i) {
      var li = el("li");
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", i === paletteIndex ? "true" : "false");
      li.appendChild(el("span", "palette-kind", item.kind));
      li.appendChild(el("span", null, item.label));
      li.addEventListener("click", function () { runPalette(i); });
      paletteResults.appendChild(li);
    });
  }

  function refreshPalette() {
    paletteItems = paletteCandidates(paletteInput.value);
    paletteIndex = 0;
    renderPalette();
  }

  function runPalette(i) {
    var item = paletteItems[i];
    closePalette();
    if (item) { item.run(); }
  }

  function openPalette() {
    paletteInput.value = "";
    refreshPalette();
    if (!palette.open) { palette.showModal(); }
    paletteInput.focus();
  }

  function closePalette() { if (palette.open) { palette.close(); } }

  paletteBtn.addEventListener("click", openPalette);
  paletteInput.addEventListener("input", refreshPalette);

  paletteInput.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!paletteItems.length) { return; }
      paletteIndex = (paletteIndex + (e.key === "ArrowDown" ? 1 : -1) + paletteItems.length)
        % paletteItems.length;
      renderPalette();
    } else if (e.key === "Enter") {
      e.preventDefault();
      runPalette(paletteIndex);
    }
  });

  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (palette.open) { closePalette(); } else { openPalette(); }
    } else if (e.key === "/" && document.activeElement === document.body) {
      e.preventDefault();
      searchInput.focus();
    }
  });

  /* ---------- data ---------- */

  function loadState(user, force) {
    var cached = read(CACHE_KEY);
    if (cached && !state) {
      try { render(JSON.parse(cached)); } catch (e) { store(CACHE_KEY, null); }
    }
    if (!state) { show("Loading…"); }

    user.getIdToken()
      .then(function (token) {
        var headers = { Authorization: "Bearer " + token };
        var etag = read(ETAG_KEY);
        if (etag && !force && cached) { headers["If-None-Match"] = etag; }
        return fetch("/api/state?today=" + localToday(), { headers: headers });
      })
      .then(function (res) {
        if (res.status === 304) { return null; }
        if (res.status === 403) { throw new Error("This Google account is not on the allowlist."); }
        if (!res.ok) { throw new Error("Server error (" + res.status + ")"); }
        store(ETAG_KEY, res.headers.get("ETag"));
        return res.json();
      })
      .then(function (data) {
        if (!data) { return; }
        if (!data.empty) { store(CACHE_KEY, JSON.stringify(data)); }
        render(data);
      })
      .catch(function (e) {
        if (state) { $("last-sync").textContent = "offline — showing last known state"; }
        else { show(e.message, true); }
      });
  }

  /* Rendering is pure DOM work against a state object, so it is exposed for the
     offline preview page and for driving the UI in a browser check. Nothing
     here reads or writes the network. */
  window.KandulaOS = { render: render };

  /* ---------- auth ---------- */

  var config;
  try { config = JSON.parse(document.body.dataset.firebaseConfig || "{}"); }
  catch (e) { config = {}; }

  if (!config.apiKey) {
    show("FIREBASE_WEB_CONFIG is not set on the server. See docs/DEPLOY.md.", true);
    authBtn.disabled = true;
    return;
  }

  firebase.initializeApp(config);
  var auth = firebase.auth();

  authBtn.addEventListener("click", function () {
    if (auth.currentUser) {
      auth.signOut();
    } else {
      auth.signInWithPopup(new firebase.auth.GoogleAuthProvider()).catch(function (e) {
        show("Sign-in failed: " + e.message, true);
      });
    }
  });

  auth.onAuthStateChanged(function (user) {
    if (user) {
      authBtn.textContent = "Sign out";
      loadState(user, false);
    } else {
      authBtn.textContent = "Sign in";
      state = null;
      main.hidden = true;
      main.classList.remove("loaded");
      store(CACHE_KEY, null);
      store(ETAG_KEY, null);
      show("Sign in to load your dashboard.");
    }
  });
})();
