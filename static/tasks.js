"use strict";

(() => {
  const panels = [...document.querySelectorAll(".tool-panel")];
  const status = document.getElementById("task-status");
  const list = document.getElementById("task-list");
  const empty = document.getElementById("task-empty");
  const form = document.getElementById("task-form");
  const title = document.getElementById("task-title");
  const due = document.getElementById("task-due");
  const banner = document.getElementById("reminder-banner");
  const shown = new Set();
  let tasks = [];
  let refreshing = null;

  function openPanel(id) {
    panels.forEach((panel) => { panel.hidden = panel.id !== id; });
    window.dispatchEvent(new CustomEvent("priya-panel-changed", { detail: id }));
  }
  document.querySelectorAll("[data-open-panel]").forEach((button) => {
    button.addEventListener("click", () => openPanel(button.dataset.openPanel));
  });
  document.querySelectorAll("[data-close-panel]").forEach((button) => {
    button.addEventListener("click", () => {
      button.closest(".tool-panel").hidden = true;
      window.dispatchEvent(new CustomEvent("priya-panel-changed", { detail: "" }));
    });
  });
  window.addEventListener("priya-open-panel", (event) => openPanel(event.detail));

  async function request(url, options = {}) {
    const response = await window.priyaApi(url, options);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The task request failed.");
    return result;
  }

  async function change(task, changes) {
    try {
      const result = await request(`/api/tasks/${encodeURIComponent(task.id)}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes),
      });
      tasks = tasks.map((item) => item.id === task.id ? result.task : item);
      render();
      status.textContent = "Task updated.";
    } catch (error) {
      status.textContent = `Task changes were not confirmed: ${error.message}`;
      render();
    }
  }

  function render() {
    list.replaceChildren();
    empty.hidden = tasks.length > 0;
    const overdue = tasks.filter((task) => !task.done && !task.acknowledged && task.due && Date.parse(task.due) <= Date.now());
    banner.hidden = !overdue.length;
    document.getElementById("reminder-text").textContent = overdue.length
      ? `Reminder due: ${overdue.map((task) => task.title).join(", ")}`
      : "";
    tasks.forEach((task) => {
      const row = document.createElement("li");
      if (task.done) row.classList.add("done");
      if (overdue.includes(task)) row.classList.add("overdue");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = task.done;
      checkbox.setAttribute("aria-label", `Mark ${task.title} ${task.done ? "incomplete" : "complete"}`);
      checkbox.addEventListener("change", () => change(task, { done: checkbox.checked }));
      const info = document.createElement("div");
      info.className = "task-info";
      const name = document.createElement("strong");
      name.textContent = task.title;
      info.append(name);
      if (task.due) {
        const time = document.createElement("small");
        time.textContent = `Reminder: ${new Date(task.due).toLocaleString()}${task.acknowledged ? " (acknowledged)" : ""}`;
        info.append(time);
      }
      if (overdue.includes(task)) {
        const acknowledge = document.createElement("button");
        acknowledge.className = "notification-button";
        acknowledge.type = "button";
        acknowledge.textContent = "Acknowledge reminder";
        acknowledge.setAttribute("aria-label", `Acknowledge ${task.title}`);
        acknowledge.addEventListener("click", () => change(task, { acknowledged: true }));
        info.append(acknowledge);
      }
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "task-delete";
      remove.textContent = "×";
      remove.setAttribute("aria-label", `Delete ${task.title}`);
      remove.addEventListener("click", async () => {
        try {
          await request(`/api/tasks/${encodeURIComponent(task.id)}`, { method: "DELETE" });
          tasks = tasks.filter((item) => item.id !== task.id);
          render();
          status.textContent = "Task deleted.";
        } catch (error) {
          status.textContent = `Deletion was not confirmed: ${error.message}`;
        }
      });
      row.append(checkbox, info, remove);
      list.append(row);
    });
    if (document.visibilityState === "visible" && "Notification" in window && Notification.permission === "granted") {
      overdue.filter((task) => !shown.has(task.id)).forEach((task) => {
        try {
          new Notification("Priya reminder", { body: task.title, tag: task.id });
          shown.add(task.id);
        } catch (error) {
          status.textContent = `Reminder is due; desktop alert failed: ${error.message}`;
        }
      });
    }
  }

  function refresh() {
    if (refreshing) return refreshing;
    refreshing = request("/api/tasks").then((result) => {
      tasks = result.tasks;
      render();
    }).finally(() => { refreshing = null; });
    return refreshing;
  }

  async function addTask(text, dueDate = null) {
    try {
      const result = await request("/api/tasks", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: text, due: dueDate ? dueDate.toISOString() : null, id: crypto.randomUUID() }),
      });
      tasks = [...tasks.filter((item) => item.id !== result.task.id), result.task];
      render();
      status.textContent = "Task saved on your Priya server.";
      return { ok: true, task: result.task };
    } catch (error) {
      status.textContent = `Task saving was not confirmed: ${error.message}`;
      return { ok: false, error: error.message };
    }
  }
  window.priyaTasks = { addTask, refresh };
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button");
    button.disabled = true;
    const result = await addTask(title.value, due.value ? new Date(due.value) : null);
    if (result.ok) form.reset();
    button.disabled = false;
  });

  document.getElementById("enable-notifications").addEventListener("click", async () => {
    if (!("Notification" in window)) {
      status.textContent = "Desktop alerts are not supported; overdue reminders still appear here.";
      return;
    }
    try {
      const permission = await Notification.requestPermission();
      status.textContent = permission === "granted" ? "Desktop alerts enabled while the page is open." : `Desktop alerts ${permission}; overdue reminders remain visible here.`;
      render();
    } catch (error) {
      status.textContent = `Could not enable desktop alerts: ${error.message}`;
    }
  });

  async function initialize() {
    try {
      const saved = localStorage.getItem("priya.tasks.v1");
      if (saved !== null) {
        await request("/api/tasks/import", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tasks: JSON.parse(saved) }),
        });
        localStorage.removeItem("priya.tasks.v1");
      }
    } catch (error) {
      status.textContent = `Old browser tasks were not removed: migration failed (${error.message}).`;
    }
    try {
      await refresh();
    } catch (error) {
      status.textContent = `Tasks could not be loaded: ${error.message}`;
    }
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") refresh().catch((error) => { status.textContent = `Task refresh failed: ${error.message}`; });
  });
  setInterval(() => {
    render();
    if (document.visibilityState === "visible") refresh().catch((error) => { status.textContent = `Task refresh failed: ${error.message}`; });
  }, 10000);
  initialize();
})();
