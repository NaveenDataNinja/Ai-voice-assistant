"use strict";

window.priyaApi = async (url, options = {}) => {
  const headers = new Headers(options.headers);
  const method = options.method || "GET";
  const tracked = url !== "/api/monitor" && !(method === "GET" && ["/api/tasks", "/api/status", "/api/session"].includes(url));
  const safePath = url.replace(/\/api\/tasks\/[^/]+$/, "/api/tasks/:id");
  if (tracked) window.priyaActivity?.("api.request", `${method} ${safePath}; request body is not logged.`);
  const token = document.querySelector('meta[name="csrf-token"]').content;
  if (token) headers.set("X-CSRF-Token", token);
  let response;
  try {
    response = await fetch(url, { ...options, headers, credentials: "same-origin" });
  } catch (error) {
    if (tracked) window.priyaActivity?.(
      error.name === "AbortError" ? "api.cancelled" : "api.failed",
      `${method} ${safePath}; ${error.name === "AbortError" ? "cancelled in this tab" : "network request failed"}.`,
      error.name === "AbortError" ? "info" : "error",
    );
    throw error;
  }
  if (response.status === 403 && (await response.clone().json()).code === "csrf") {
    const refreshed = await fetch("/api/session", { credentials: "same-origin" });
    if (refreshed.ok) {
      const session = await refreshed.json();
      document.querySelector('meta[name="csrf-token"]').content = session.csrf_token;
      headers.set("X-CSRF-Token", session.csrf_token);
      response = await fetch(url, { ...options, headers, credentials: "same-origin" });
    }
  }
  if (tracked) window.priyaActivity?.(
    "api.response", `${method} ${safePath}; HTTP ${response.status}.`,
    response.ok ? "ok" : "error", response.headers.get("X-Request-ID"),
  );
  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent("priya-session-expired"));
    throw new Error("Your session expired. Sign in again; your unsent text remains on this page.");
  }
  return response;
};

window.addEventListener("priya-session-expired", () => {
  document.getElementById("session-expired").hidden = false;
});
