"use strict";

(() => {
  const panel = document.getElementById("monitor-panel");
  const status = document.getElementById("monitor-status");
  const runtime = document.getElementById("monitor-runtime");
  const development = document.getElementById("monitor-development");
  const browserEvents = [];
  let latest = null;
  let polling = false;

  function element(tag, text, className = "") {
    const node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function localTime(value) {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? "Time unavailable" : parsed.toLocaleTimeString();
  }

  window.priyaActivity = (stage, detail, eventStatus = "info", requestId = null) => {
    browserEvents.push({
      time: new Date().toISOString(), stage, detail, status: eventStatus,
      request_id: requestId, source: "This tab",
    });
    if (browserEvents.length > 80) browserEvents.shift();
    if (!panel.hidden && latest) renderRuntime();
  };

  function renderRuntime() {
    const metrics = latest.runtime;
    const summary = document.getElementById("monitor-metrics");
    summary.replaceChildren();
    for (const [label, value] of [
      ["API responses", metrics.requests], ["HTTP errors", metrics.errors],
      ["Average setup time", metrics.average_setup_ms === null ? "Not measured" : `${metrics.average_setup_ms} ms`],
      ["Active AI streams", metrics.active_ai_streams],
    ]) {
      const card = element("div", "", "monitor-metric");
      card.append(element("strong", String(value)), element("span", label));
      summary.append(card);
    }
    const feed = document.getElementById("monitor-events");
    feed.replaceChildren();
    const entries = [
      ...latest.events.map((event) => ({ ...event, source: "Server" })),
      ...browserEvents,
    ].sort((a, b) => Date.parse(b.time) - Date.parse(a.time)).slice(0, 100);
    for (const event of entries) {
      const row = element("li", "", `monitor-event${event.status === "error" ? " monitor-error" : ""}`);
      row.append(
        element("small", `${localTime(event.time)} | ${event.source}${event.request_id ? ` | ${event.request_id}` : ""}`),
        element("strong", event.stage),
        element("span", event.detail),
      );
      feed.append(row);
    }
  }

  function renderDevelopment() {
    const progress = document.getElementById("monitor-progress");
    progress.replaceChildren();
    const report = latest.verification;
    const total = Number.isInteger(report.total) ? report.total : 0;
    const completed = Number.isInteger(report.completed) ? report.completed : 0;
    progress.append(element("strong", `Automated verification: ${report.status}`));
    if (total) {
      const bar = document.createElement("progress");
      bar.max = total;
      bar.value = completed;
      progress.append(bar, element("p", `${completed}/${total} completed; ${report.passed} passed, ${report.failed} failed, ${report.errors} errors, ${report.skipped} skipped.`));
    }
    if (report.last_test) progress.append(element("code", report.last_test));
    if (report.finished_at) progress.append(element("small", `Finished ${localTime(report.finished_at)}`));
    if (report.message) progress.append(element("p", report.message));
    progress.append(element("small", "Run python -m app_monitor --test in the project terminal to publish real unittest progress. Browser checks below are developer-maintained, not automatically inferred."));
    const steps = document.getElementById("monitor-steps");
    steps.replaceChildren();
    const notes = latest.development;
    document.getElementById("monitor-development-status").textContent = `Development: ${notes.status}${notes.updated_at ? ` | updated ${localTime(notes.updated_at)}` : ""}`;
    if (notes.message) steps.append(element("li", notes.message));
    for (const step of notes.steps || []) {
      const row = element("li", "", "monitor-step");
      row.append(element("strong", step.name), element("small", step.status), element("p", step.evidence));
      steps.append(row);
    }
    const limits = document.getElementById("monitor-limitations");
    limits.replaceChildren();
    for (const limitation of notes.limitations || []) limits.append(element("li", limitation));
    const files = document.getElementById("monitor-files");
    files.replaceChildren();
    if (!latest.files.length) files.append(element("li", "No allowlisted file changes observed since this server started."));
    for (const file of latest.files) files.append(element("li", `${localTime(file.detected_at)} | ${file.file} | ${file.change}`));
  }

  async function poll() {
    if (polling || panel.hidden || document.visibilityState !== "visible") return;
    polling = true;
    try {
      const response = await window.priyaApi("/api/monitor");
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Monitoring request failed.");
      latest = result;
      renderRuntime();
      renderDevelopment();
      status.textContent = `Live | refreshed ${new Date().toLocaleTimeString()} | baseline ${localTime(result.runtime.started_at)}`;
      document.getElementById("monitor-privacy").textContent = result.privacy;
    } catch (error) {
      status.textContent = `Not live: ${error.message}. Previously displayed data may be stale.`;
    } finally {
      polling = false;
    }
  }
  for (const name of ["runtime", "development"]) {
    document.getElementById(`monitor-${name}-tab`).addEventListener("click", () => {
      runtime.hidden = name !== "runtime";
      development.hidden = name !== "development";
      for (const tab of ["runtime", "development"]) document.getElementById(`monitor-${tab}-tab`).setAttribute("aria-pressed", String(tab === name));
      poll();
    });
  }
  window.addEventListener("priya-panel-changed", (event) => {
    if (event.detail === "monitor-panel") poll();
  });
  document.addEventListener("visibilitychange", poll);
  setInterval(poll, 2000);
})();
