import { useState } from "react";
import { Check, KeyRound, Lock, Settings } from "lucide-react";
import { useWorkspace } from "../hooks/useWorkspace";
import {
  Badge,
  Button,
  ErrorState,
  PageHeader,
  SectionHeader,
  Tabs,
} from "../components/ui";
export default function SettingsPage() {
  const { system, refresh, refreshRecent } = useWorkspace();
  const [tab, setTab] = useState<"connection" | "workspace" | "shortcuts">(
      "connection",
    ),
    [key, setKey] = useState(sessionStorage.getItem("atlas-api-key") || ""),
    [saving, setSaving] = useState(false),
    [saved, setSaved] = useState(false),
    [error, setError] = useState("");
  async function connect() {
    setSaving(true);
    setError("");
    setSaved(false);
    const previous = sessionStorage.getItem("atlas-api-key");
    sessionStorage.setItem("atlas-api-key", key);
    try {
      await refresh();
      await refreshRecent();
      setSaved(true);
    } catch (e) {
      if (previous === null) sessionStorage.removeItem("atlas-api-key");
      else sessionStorage.setItem("atlas-api-key", previous);
      setError((e as Error).message);
      refresh().catch(() => {});
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="page settings-page">
      <PageHeader
        title="Settings"
        description="Manage your API connection and understand this workspace’s capabilities."
      />
      <Tabs
        value={tab}
        onChange={setTab}
        items={[
          { id: "connection", label: "Connection" },
          { id: "workspace", label: "Workspace" },
          { id: "shortcuts", label: "Keyboard shortcuts" },
        ]}
      />
      {tab === "connection" ? (
        <section className="settings-section">
          <SectionHeader
            title="API connection"
            description="The frontend connects to the current server through its same-origin /api proxy."
          />
          <div className="settings-form">
            <div className="field-group">
              <label className="field-label" htmlFor="api-origin">
                API path
              </label>
              <input
                id="api-origin"
                className="input"
                readOnly
                value={`${location.origin}/api`}
              />
            </div>
            <div className="field-group">
              <label className="field-label" htmlFor="api-key">
                Workspace API key
              </label>
              <input
                id="api-key"
                className="input"
                type="password"
                autoComplete="off"
                value={key}
                onChange={(e) => {
                  setKey(e.target.value);
                  setSaved(false);
                }}
                placeholder="Enter a key if your server requires one"
              />
              <small>
                Stored in this browser session only. Never sent to a third-party
                endpoint.
              </small>
            </div>
            {error && <ErrorState message={error} />}
            <Button variant="primary" disabled={saving} onClick={connect}>
              {saving ? (
                "Connecting…"
              ) : saved ? (
                <>
                  <Check size={15} />
                  Connected
                </>
              ) : (
                "Save connection"
              )}
            </Button>
          </div>
          <div className="settings-note">
            <Lock size={17} />
            <p>
              One trusted workspace is configured. Shared API-key access is not
              user or document-level authorization.
            </p>
          </div>
        </section>
      ) : tab === "workspace" ? (
        <section className="settings-section">
          <SectionHeader
            title="Research workspace"
            description="Current server configuration. Provider settings are managed on the server."
          />
          {system ? (
            <div className="settings-columns">
              <dl className="technical-list">
                {Object.entries({
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
              Connect to the API to view workspace configuration.
            </p>
          )}
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
