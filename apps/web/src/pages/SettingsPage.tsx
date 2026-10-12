import { useEffect, useState } from "react";
import { api } from "../api";
import { useWorkspace } from "../hooks/useWorkspace";
import { PageHeader, SectionHeader, Tabs } from "../components/ui";
export default function SettingsPage() {
  const { system } = useWorkspace();
  const [reference, setReference] = useState("");
  useEffect(() => {
    api<{ workspace_id: string }>("/workspace").then((value) => setReference(value.workspace_id)).catch(() => {});
  }, []);
  const [tab, setTab] = useState<"workspace" | "shortcuts">("workspace");
  return (
    <div className="page settings-page">
      <PageHeader
        title="Settings"
        description="Manage your private research workspace and keyboard shortcuts."
      />
      <Tabs
        value={tab}
        onChange={setTab}
        items={[
          { id: "workspace", label: "Workspace" },
          { id: "shortcuts", label: "Keyboard shortcuts" },
        ]}
      />
      {tab === "workspace" ? (
        <section className="settings-section">
          <SectionHeader
            title="Research workspace"
            description="Your documents and research history belong to this browser’s private workspace. Other visitors cannot access them."
          />
          {system ? (
            <div className="settings-columns">
              <dl className="technical-list">
                {Object.entries({
                  "Workspace reference": reference || "Loading…",
                  Environment: system.profile,
                  "Dense backend": system.dense_backend,
                  "Embedding model": system.embedding_model,
                  "Vector store": system.vector_backend,
                  Reranker: system.reranker,
                  Generator: system.generator,
                }).map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
              <dl className="technical-list">
                {Object.entries({
                  "Maximum agent steps": system.max_agent_steps,
                  "Query deadline": `${system.query_timeout_seconds} seconds`,
                  "Context budget": `${system.context_budget_bytes} UTF-8 bytes`,
                  Collections: "Unavailable",
                  "Workspace switching": "Unavailable",
                  "Live agent streaming": "Unavailable",
                }).map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ) : (
            <p className="muted">
              Workspace details are loading.
            </p>
          )}
          <p className="subtle-note">This workspace stays with this browser. Clearing its cookies starts a new workspace; devices are not synced.</p>
          <p className="subtle-note">
            Deep Analysis uses a broader ten-chunk retrieval budget with the
            same configured provider. Exact support scores are heuristic and are
            not calibrated probabilities.
          </p>
        </section>
      ) : (
        <section className="settings-section">
          <SectionHeader title="Move through your research faster" />
          <div className="shortcut-list">
            {[
              ["Open command menu", "⌘ / Ctrl + K"],
              ["Send a research question", "Enter"],
              ["Insert a new line", "Shift + Enter"],
              ["Close a dialog or sheet", "Escape"],
              ["Navigate focusable controls", "Tab / Shift + Tab"],
              ["Move between inspector tabs", "← / →"],
            ].map(([label, key]) => (
              <div key={label}>
                <span>{label}</span>
                <kbd>{key}</kbd>
              </div>
            ))}
          </div>
          <p className="subtle-note">
            Motion respects your operating system’s reduced-motion setting.
            Collapse the sidebar to create more room for research.
          </p>
        </section>
      )}
    </div>
  );
}
