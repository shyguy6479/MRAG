// VITE_* values are public configuration, never credentials.
export const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/+$/, "");
export const grafanaUrl = import.meta.env.VITE_GRAFANA_URL ||
  (import.meta.env.DEV ? "http://127.0.0.1:3001" : undefined);
