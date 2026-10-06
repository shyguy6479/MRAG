import { useCallback, useEffect, useState } from "react";
export type Page =
  | "research"
  | "knowledge"
  | "search"
  | "experiments"
  | "evaluations"
  | "observability"
  | "settings";
const pages: Page[] = [
  "research",
  "knowledge",
  "search",
  "experiments",
  "evaluations",
  "observability",
  "settings",
];
function read() {
  const path = window.location.pathname.slice(1);
  return {
    page: (pages.includes(path as Page) ? path : "research") as Page,
    session: new URLSearchParams(window.location.search).get("session"),
  };
}
export function useRoute() {
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const listener = () => setRoute(read());
    window.addEventListener("popstate", listener);
    return () => window.removeEventListener("popstate", listener);
  }, []);
  const navigate = useCallback((page: Page, session?: string | null) => {
    history.pushState(
      {},
      "",
      `/${page}${session ? `?session=${encodeURIComponent(session)}` : ""}`,
    );
    setRoute({ page, session: session || null });
  }, []);
  return { ...route, navigate };
}
