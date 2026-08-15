import { reportFrontendError } from "../api/client";

// Errors React's boundary never sees: async callbacks, event handlers, and
// rejected promises. Installed once from main.tsx before the app renders, so a
// module-level throw is still captured.
export function installErrorReporter() {
  window.addEventListener("error", (event) => {
    const error = event.error;
    reportFrontendError(
      event.message || String(error),
      "onerror",
      error instanceof Error ? (error.stack ?? "") : `${event.filename}:${event.lineno}`,
    ).catch(() => {});
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    reportFrontendError(
      reason instanceof Error ? reason.message : String(reason),
      "unhandledrejection",
      reason instanceof Error ? (reason.stack ?? "") : "",
    ).catch(() => {});
  });
}
