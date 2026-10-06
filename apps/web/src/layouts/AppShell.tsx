import { useEffect, useState, type ReactNode } from "react";
import {
  Activity,
  ArrowLeftToLine,
  ArrowRightFromLine,
  BookOpen,
  Check,
  ChevronDown,
  Command,
  FlaskConical,
  Layers3,
  Menu,
  MessageSquare,
  MoreHorizontal,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  SquareChartGantt,
  X,
} from "lucide-react";
import { useWorkspace, readLocal } from "../hooks/useWorkspace";
import type { Page } from "../hooks/useRoute";
import { Button, Dialog, IconButton } from "../components/ui";
export const navigation = [
  { id: "research", label: "Research", icon: MessageSquare },
  { id: "knowledge", label: "Knowledge Base", icon: BookOpen },
  { id: "search", label: "Search", icon: Search },
  { id: "experiments", label: "Experiments", icon: FlaskConical },
  { id: "evaluations", label: "Evaluations", icon: SquareChartGantt },
  { id: "observability", label: "Observability", icon: Activity },
] as const;
export default function AppShell({
  page,
  navigate,
  onNew,
  onUpload,
  onSession,
  children,
}: {
  page: Page;
  navigate: (page: Page) => void;
  onNew: () => void;
  onUpload: () => void;
  onSession: (id: string) => void;
  children: ReactNode;
}) {
  const { system, recent, error } = useWorkspace();
  const [collapsed, setCollapsed] = useState(() =>
      readLocal("atlas-sidebar-collapsed", false),
    ),
    [mobile, setMobile] = useState(false),
    [command, setCommand] = useState(false),
    [search, setSearch] = useState("");
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommand((value) => !value);
        setSearch("");
      }
      if (e.key === "Escape") setMobile(false);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const go = (next: Page) => {
    navigate(next);
    setMobile(false);
  };
  const commands = [
    { label: "New research", icon: Plus, action: onNew },
    { label: "Upload documents", icon: BookOpen, action: onUpload },
    {
      label: "Search knowledge base",
      icon: Search,
      action: () => go("search"),
    },
    {
      label: "Open experiments",
      icon: FlaskConical,
      action: () => go("experiments"),
    },
    {
      label: "Open evaluations",
      icon: SquareChartGantt,
      action: () => go("evaluations"),
    },
    {
      label: "Open observability",
      icon: Activity,
      action: () => go("observability"),
    },
    {
      label: "Workspace & settings",
      icon: Settings,
      action: () => go("settings"),
    },
    ...recent.slice(0, 6).map((item) => ({
      label: item.title,
      icon: MessageSquare,
      action: () => onSession(item.id),
    })),
  ].filter((item) => item.label.toLowerCase().includes(search.toLowerCase()));
  return (
    <div className={`workspace-shell ${collapsed ? "nav-collapsed" : ""}`}>
      {mobile && (
        <button
          className="mobile-scrim"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className={`app-sidebar ${mobile ? "mobile-open" : ""}`}>
        <div className="sidebar-brand">
          <Layers3 size={23} />
          <strong>
            M<span>RAG</span>
          </strong>
          <IconButton
            label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={() => {
              setCollapsed(!collapsed);
              localStorage.setItem(
                "atlas-sidebar-collapsed",
                JSON.stringify(!collapsed),
              );
            }}
          >
            {collapsed ? (
              <ArrowRightFromLine size={16} />
            ) : (
              <ArrowLeftToLine size={16} />
            )}
          </IconButton>
        </div>
        <button
          className="workspace-picker"
          onClick={() => go("settings")}
          title="Workspace settings"
        >
          <span className="workspace-avatar">A</span>
          <span>
            Research workspace
            <small>{system?.profile || "Local"} environment</small>
          </span>
          <ChevronDown size={14} />
        </button>
        <Button
          variant="primary"
          className="new-session"
          onClick={() => {
            onNew();
            setMobile(false);
          }}
          title="New research"
        >
          <Plus size={17} />
          <span>New research</span>
        </Button>
        <nav aria-label="Main navigation">
          {navigation.map((item) => (
            <button
              className={page === item.id ? "selected" : ""}
              key={item.id}
              onClick={() => go(item.id)}
              title={item.label}
              aria-current={page === item.id ? "page" : undefined}
            >
              <item.icon size={18} />
              <span>{item.label}</span>
              {item.id === "knowledge" && (
                <small>{system?.documents ?? "—"}</small>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-recent">
          <div className="sidebar-section-label">RECENT RESEARCH</div>
          {recent.slice(0, 5).map((item) => (
            <div className="recent-item" key={item.id}>
              <button
                className="recent-title"
                onClick={() => {
                  onSession(item.id);
                  setMobile(false);
                }}
                title={item.title}
              >
                {item.title}
              </button>
              <details className="recent-menu">
                <summary aria-label={`Actions for ${item.title}`}>
                  <MoreHorizontal size={15} />
                </summary>
                <div>
                  <button onClick={() => onSession(item.id)}>
                    Open research
                  </button>
                  <button
                    onClick={() => {
                      onNew();
                      setMobile(false);
                    }}
                  >
                    Start new research
                  </button>
                </div>
              </details>
            </div>
          ))}
        </div>
        <div className="sidebar-footer">
          <div className={`connection-status ${error ? "is-warning" : ""}`}>
            <span className="status-dot" />
            <span>
              {error
                ? "Connection issue"
                : system
                  ? "API connected"
                  : "Connecting…"}
              <small>
                {system
                  ? `${system.ready_documents} documents indexed`
                  : "Checking workspace"}
              </small>
            </span>
          </div>
          <button
            className={`settings-nav ${page === "settings" ? "selected" : ""}`}
            onClick={() => go("settings")}
            title="Settings"
          >
            <span className="user-avatar">MR</span>
            <span>
              MRAG researcher<small>Workspace settings</small>
            </span>
            <Settings size={17} />
          </button>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="app-toolbar">
          <div className="toolbar-location">
            <IconButton
              label="Toggle navigation"
              className="mobile-menu"
              onClick={() => setMobile(!mobile)}
            >
              <Menu size={19} />
            </IconButton>
            <span>Workspace</span>
            <span className="slash">/</span>
            <strong>
              {navigation.find((item) => item.id === page)?.label || "Settings"}
            </strong>
          </div>
          <div className="toolbar-actions">
            <button
              className="command-trigger"
              aria-label="Open command menu"
              onClick={() => setCommand(true)}
            >
              <Search size={15} />
              <span>Search or jump to…</span>
              <kbd>
                <Command size={11} />K
              </kbd>
            </button>
            <span className="toolbar-status">
              <i className={`status-dot ${error ? "warning" : ""}`} />
              {error ? "Disconnected" : system ? "Connected" : "Connecting"}
            </span>
            <IconButton label="Open settings" onClick={() => go("settings")}>
              <Settings size={17} />
            </IconButton>
          </div>
        </header>
        <main className="workspace-content">{children}</main>
      </div>
      {command && (
        <Dialog
          initialFocus="input"
          title="Command menu"
          onClose={() => setCommand(false)}
        >
          <div className="command-search">
            <Search size={18} />
            <input
              aria-label="Search commands"
              placeholder="Search commands or recent research…"
              autoFocus
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && commands[0]) {
                  e.preventDefault();
                  commands[0].action();
                  setCommand(false);
                } else if (e.key === "ArrowDown") {
                  e.preventDefault();
                  document
                    .querySelector<HTMLButtonElement>(".command-results button")
                    ?.focus();
                }
              }}
            />
            <kbd>esc</kbd>
          </div>
          <div
            className="command-results"
            onKeyDown={(event) => {
              if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                const options = [
                  ...event.currentTarget.querySelectorAll<HTMLButtonElement>(
                    "button",
                  ),
                ];
                const current = options.indexOf(
                  document.activeElement as HTMLButtonElement,
                );
                options[
                  (current +
                    (event.key === "ArrowDown" ? 1 : -1) +
                    options.length) %
                    options.length
                ]?.focus();
              }
            }}
          >
            {commands.length ? (
              commands.map((item, i) => (
                <button
                  key={`${item.label}-${i}`}
                  onClick={() => {
                    item.action();
                    setCommand(false);
                    setMobile(false);
                  }}
                >
                  <item.icon size={17} />
                  <span>{item.label}</span>
                  <span>↵</span>
                </button>
              ))
            ) : (
              <p className="quiet-empty">No commands match your search.</p>
            )}
          </div>
          <p className="subtle-note">
            One workspace is configured. Additional workspace switching is
            unavailable.
          </p>
        </Dialog>
      )}
    </div>
  );
}
