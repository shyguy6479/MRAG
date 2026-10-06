import { createPortal } from "react-dom";
import {
  useEffect,
  useId,
  useRef,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import {
  AlertCircle,
  ChevronRight,
  Inbox,
  LoaderCircle,
  X,
} from "lucide-react";
export function Button({
  variant = "secondary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  return (
    <button
      type="button"
      {...props}
      className={`button ${variant} ${className}`}
    />
  );
}
export function IconButton({
  label,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <Button
      {...props}
      variant="ghost"
      className={`icon-button ${props.className || ""}`}
      aria-label={label}
      title={label}
    >
      {children}
    </Button>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning" | "error" | "accent";
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function StatusBadge({ status }: { status: string }) {
  const label: Record<string, string> = {
    ready: "Indexed",
    processing: "Processing",
    queued: "Queued",
    failed: "Failed",
    completed: "Completed",
  };
  const tone =
    status === "ready" || status === "completed"
      ? "success"
      : status === "failed"
        ? "error"
        : "warning";
  return (
    <Badge tone={tone}>
      <i className="status-dot" />
      {label[status] || status}
    </Badge>
  );
}
export function Metric({
  label,
  value,
  note,
}: {
  label: string;
  value: ReactNode;
  note?: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value ?? "Unavailable"}</strong>
      {note && <small>{note}</small>}
    </div>
  );
}
export function Tabs<T extends string>({
  items,
  value,
  onChange,
  label = "View",
}: {
  items: { id: T; label: string; count?: number }[];
  value: T;
  onChange: (value: T) => void;
  label?: string;
}) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {items.map((item) => (
        <button
          role="tab"
          aria-selected={value === item.id}
          key={item.id}
          onClick={() => onChange(item.id)}
          onKeyDown={(event) => {
            if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
              event.preventDefault();
              const index = items.findIndex((i) => i.id === item.id);
              const next =
                (index + (event.key === "ArrowRight" ? 1 : -1) + items.length) %
                items.length;
              onChange(items[next].id);
              (
                event.currentTarget.parentElement?.children[next] as HTMLElement
              )?.focus();
            }
          }}
        >
          {item.label}
          {item.count !== undefined && <span>{item.count}</span>}
        </button>
      ))}
    </div>
  );
}
export function Dialog({
  title,
  children,
  onClose,
  wide = false,
  sheet = false,
  initialFocus,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
  sheet?: boolean;
  initialFocus?: string;
}) {
  const id = useId(),
    ref = useRef<HTMLElement>(null),
    close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const dialog = ref.current,
      previous = document.activeElement as HTMLElement | null;
    if (!dialog) return;
    const query = () =>
      [
        ...dialog.querySelectorAll<HTMLElement>(
          'button:not([disabled]),input,textarea,select,a[href],[tabindex="0"]',
        ),
      ].filter((el) => el.getClientRects().length);
    (initialFocus
      ? dialog.querySelector<HTMLElement>(initialFocus)
      : query()[0]
    )?.focus({ preventScroll: true });
    const listener = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close.current();
      }
      if (event.key === "Tab") {
        const items = query(),
          first = items[0],
          last = items.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    dialog.addEventListener("keydown", listener);
    return () => {
      dialog.removeEventListener("keydown", listener);
      if (previous && document.contains(previous))
        previous.focus({ preventScroll: true });
    };
  }, []);
  return createPortal(
    <div
      className={`dialog-overlay ${sheet ? "sheet-overlay" : ""}`}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <section
        ref={ref}
        className={`dialog ${wide ? "wide" : ""} ${sheet ? "sheet" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={id}
      >
        <header>
          <h2 id={id}>{title}</h2>
          <IconButton label={`Close ${title}`} onClick={onClose}>
            <X size={18} />
          </IconButton>
        </header>
        <div className="dialog-content">{children}</div>
      </section>
    </div>,
    document.body,
  );
}
export function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="skeleton-group" aria-label="Loading content" role="status">
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          className="skeleton"
          style={{ width: `${100 - (i % 3) * 12}%` }}
        />
      ))}
    </div>
  );
}
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <Inbox size={24} />
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function ErrorState({
  message,
  retry,
  details,
}: {
  message: string;
  retry?: () => void;
  details?: string;
}) {
  return (
    <div className="error-state" role="alert">
      <AlertCircle size={18} />
      <div>
        <strong>{message}</strong>
        {details && (
          <details>
            <summary>Technical details</summary>
            <code>{details}</code>
          </details>
        )}
      </div>
      {retry && <Button onClick={retry}>Retry</Button>}
    </div>
  );
}
export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: string;
  description: string;
  actions?: ReactNode;
  eyebrow?: string;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}
export function SectionHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-header">
      <div>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}
export function LoadingButton({
  busy,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { busy: boolean }) {
  return (
    <Button {...props} variant="primary" disabled={busy || props.disabled}>
      {busy && <LoaderCircle size={16} className="spin" />}
      {children}
    </Button>
  );
}
export function Score({
  label,
  value,
}: {
  label: string;
  value: number | null | undefined;
}) {
  return (
    <div className="score">
      <span>{label}</span>
      <code>{value == null ? "Unavailable" : value.toFixed(4)}</code>
    </div>
  );
}
export function LinkButton({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button className="text-link" onClick={onClick}>
      {children}
      <ChevronRight size={14} />
    </button>
  );
}
export function Toast({
  message,
  onClose,
}: {
  message: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const id = setTimeout(onClose, 3500);
    return () => clearTimeout(id);
  }, [message, onClose]);
  return (
    <div className="toast" role="status">
      {message}
      <IconButton label="Dismiss notification" onClick={onClose}>
        <X size={14} />
      </IconButton>
    </div>
  );
}
