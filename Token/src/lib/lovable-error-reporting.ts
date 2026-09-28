type AppErrorContext = Record<string, unknown>;

declare global {
  interface Window {
    __appErrorTracker?: (payload: {
      message: string;
      stack?: string;
      filename?: string;
      context?: AppErrorContext;
    }) => void;
  }
}

export function reportAppError(error: unknown, context: AppErrorContext = {}) {
  if (typeof window === "undefined") return;

  const message =
    error instanceof Response
      ? `Response ${error.status}${error.url ? ` at ${error.url}` : ""}`
      : error instanceof Error
        ? error.message
        : String(error);
  const stack = error instanceof Error ? error.stack : undefined;

  window.__appErrorTracker?.({
    message,
    ...(stack !== undefined && { stack }),
    filename: window.location.pathname,
    context,
  });
}
