/* Sample state for docs/preview.html — the exact shape GET /api/state returns.
   Dates are relative to today so the preview never looks stale. */
(function () {
  "use strict";

  function iso(offsetDays) {
    var d = new Date();
    d.setDate(d.getDate() + offsetDays);
    return d.getFullYear() + "-" +
      String(d.getMonth() + 1).padStart(2, "0") + "-" +
      String(d.getDate()).padStart(2, "0");
  }

  var today = iso(0);

  var tasks = [
    { id: "t1", title: "Ship the Vercel deploy", priority: "P1", done: false, due: iso(-2), project: "kandula-os" },
    { id: "t2", title: "Firebase service account", priority: "P1", done: false, due: today, project: "kandula-os" },
    { id: "t3", title: "Fill in the profile.md TODOs", priority: "P2", done: false, due: iso(5), project: "kandula-os" },
    { id: "t4", title: "Draft the weekly review prompt", priority: "P2", done: false, due: null, project: "routines" },
    { id: "t5", title: "Read the Firestore pricing page", priority: "P3", done: false, due: null, project: null },
    { id: "t6", title: "Confirm the build brief", priority: "P1", done: true, due: null, project: "kandula-os" },
    { id: "t7", title: "Pick a name for the repo", priority: "P2", done: true, due: null, project: "kandula-os" }
  ];

  var projects = [
    { name: "kandula-os", status: "active", next_action: "Deploy to Vercel, then run the first sync" },
    { name: "routines", status: "paused", next_action: "Resume after the dashboard is live" }
  ];

  var history = [9, 8, 8, 7, 5, 5, 4].map(function (open, i) {
    return { date: iso(i - 6), open: open, done: i, overdue: i > 3 ? 1 : 2 };
  });

  window.KandulaOS.render({
    generated_at: new Date(Date.now() - 9 * 60 * 1000).toISOString(),
    source: "preview",
    tasks: tasks,
    projects: projects,
    history: history,
    metrics: {
      today: today,
      open: 5,
      done: 2,
      total: 7,
      completion_rate: 0.286,
      by_priority: { P1: 2, P2: 2, P3: 1 },
      overdue: 1,
      overdue_ids: ["t1"],
      due_today: 1,
      due_this_week: 1,
      projects_active: 1,
      by_project: [
        { name: "kandula-os", open: 3, done: 2 },
        { name: "routines", open: 1, done: 0 },
        { name: "unfiled", open: 1, done: 0 }
      ],
      focus: ["t1", "t2", "t3"]
    }
  });
})();
