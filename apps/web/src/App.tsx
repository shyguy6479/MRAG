import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { WorkspaceProvider, useWorkspace } from "./hooks/useWorkspace";
import { useRoute } from "./hooks/useRoute";
import { useResearch } from "./hooks/useResearch";
import AppShell from "./layouts/AppShell";
import ResearchHome from "./components/research/ResearchHome";
import ResearchSession from "./components/research/ResearchSession";
import UploadDialog from "./components/evidence/UploadDialog";
import DocumentDialog from "./components/evidence/DocumentDialog";
import { ErrorState, Skeleton } from "./components/ui";
const KnowledgePage = lazy(() => import("./pages/KnowledgePage"));
const SearchPage = lazy(() => import("./pages/SearchPage"));
const ExperimentsPage = lazy(() => import("./pages/ExperimentsPage"));
const EvaluationsPage = lazy(() => import("./pages/EvaluationsPage"));
const ObservabilityPage = lazy(() => import("./pages/ObservabilityPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
function Workspace() {
  const route = useRoute(),
    { error, refresh } = useWorkspace();
  const [activeSession, setActiveSession] = useState(route.session);
  useEffect(() => {
    if (route.page === "research") setActiveSession(route.session);
  }, [route.page, route.session]);
  const sessionRoute = useCallback(
    (id: string | null) => {
      setActiveSession(id);
      if (route.page === "research" || id === null)
        route.navigate("research", id);
    },
    [route.navigate, route.page],
  );
  const research = useResearch(
    route.page === "research" ? route.session : activeSession,
    sessionRoute,
  );
  const [upload, setUpload] = useState(false),
    [document, setDocument] = useState<string | null>(null),
    [searchDraft, setSearchDraft] = useState("");
  const newResearch = () => {
    setActiveSession(null);
    research.reset();
  };
  const explore = (value: string) => {
    setSearchDraft(value);
    route.navigate("search");
  };
  const composer = {
    value: research.question,
    onChange: research.setQuestion,
    onSend: () => research.send(),
    onUpload: () => setUpload(true),
    busy: research.busy,
    onStop: research.stop,
    mode: research.mode,
    onMode: research.setMode,
    sources: research.sources,
    onSources: research.setSources,
  };
  return (
    <AppShell
      page={route.page}
      navigate={(page) =>
        route.navigate(page, page === "research" ? activeSession : null)
      }
      onNew={newResearch}
      onUpload={() => setUpload(true)}
      onSession={(id) => route.navigate("research", id)}
    >
      {error && route.page !== "settings" && (
        <ErrorState message={error} retry={() => refresh().catch(() => {})} />
      )}
      <Suspense
        fallback={
          <div className="page">
            <Skeleton rows={8} />
          </div>
        }
      >
        {route.page === "research" ? (
          route.session ||
          research.turns.length ||
          research.busy ||
          research.loading ? (
            <ResearchSession
              turns={research.turns}
              busy={research.busy}
              loading={research.loading}
              pending={research.pending}
              elapsed={research.elapsed}
              error={research.error}
              onHome={newResearch}
              onDocument={setDocument}
              onSearch={explore}
              composer={composer}
              onRegenerate={(value) => research.send(value)}
            />
          ) : (
            <>
              {research.error && (
                <div className="page-error">
                  <ErrorState message={research.error} />
                </div>
              )}
              <ResearchHome
                composer={composer}
                onOpen={(id) => route.navigate("research", id)}
                onKnowledge={() => route.navigate("knowledge")}
                onPrompt={(value) => {
                  research.setQuestion(value);
                  window.document
                    .querySelector<HTMLTextAreaElement>("textarea")
                    ?.focus();
                }}
              />
            </>
          )
        ) : route.page === "knowledge" ? (
          <KnowledgePage
            onUpload={() => setUpload(true)}
            onDocument={setDocument}
          />
        ) : route.page === "search" ? (
          <SearchPage initialQuery={searchDraft} onDocument={setDocument} />
        ) : route.page === "experiments" ? (
          <ExperimentsPage onEvaluate={() => route.navigate("evaluations")} />
        ) : route.page === "evaluations" ? (
          <EvaluationsPage
            onExperiments={() => route.navigate("experiments")}
          />
        ) : route.page === "observability" ? (
          <ObservabilityPage />
        ) : (
          <SettingsPage />
        )}
      </Suspense>
      {upload && (
        <UploadDialog
          onClose={() => setUpload(false)}
          onKnowledge={() => {
            setUpload(false);
            route.navigate("knowledge");
          }}
        />
      )}
      {document && (
        <DocumentDialog id={document} onClose={() => setDocument(null)} />
      )}
    </AppShell>
  );
}
export default function App() {
  return (
    <WorkspaceProvider>
      <Workspace />
    </WorkspaceProvider>
  );
}
