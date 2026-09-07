import { AlertCircle, CheckCircle2, FileQuestion, X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost";
}) {
  return (
    <button className={`button button-${variant} ${className}`} {...props} />
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "success" | "danger" | "warning" | "info" | "neutral" | "violet";
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}
export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="state-panel" role="status">
      <span className="spinner" />
      <p>{label}</p>
    </div>
  );
}
export function Empty({
  title = "Nothing here yet",
  message,
  action,
}: {
  title?: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div className="state-panel">
      <FileQuestion size={34} />
      <h2>{title}</h2>
      <p>{message}</p>
      {action}
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  return (
    <div className="state-panel state-error" role="alert">
      <AlertCircle size={34} />
      <h2>Something went wrong</h2>
      <p>
        {error instanceof Error
          ? error.message
          : "The request could not be completed."}
      </p>
      {retry && (
        <Button variant="secondary" onClick={retry}>
          Try again
        </Button>
      )}
    </div>
  );
}
export function Field({
  label,
  help,
  error,
  children,
}: {
  label: string;
  help?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {help && <small>{help}</small>}
      {error && <small className="field-error">{error}</small>}
    </label>
  );
}
export function KeyValue({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="key-value">
      <dt>{label}</dt>
      <dd>{value ?? "—"}</dd>
    </div>
  );
}
export function formatDate(value?: string | null) {
  return value
    ? new Intl.DateTimeFormat("en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "—";
}
export function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
export function statusTone(
  value: string,
): "success" | "danger" | "warning" | "info" | "neutral" | "violet" {
  if (value === "approved" || value === "resolved" || value === "reviewed")
    return "success";
  if (value === "rejected") return "danger";
  if (value === "routed" || value === "escalated" || value === "open")
    return "warning";
  if (value === "overridden") return "violet";
  if (value === "in_progress" || value === "pending") return "info";
  return "neutral";
}

export function Dialog({
  open,
  title,
  onClose,
  children,
  size = "md",
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  size?: "sm" | "md" | "lg";
}) {
  const ref = useRef<HTMLDivElement>(null);
  const previous = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!open) return;
    previous.current = document.activeElement as HTMLElement;
    const t = window.setTimeout(
      () =>
        ref.current
          ?.querySelector<HTMLElement>(
            'button,input,select,textarea,[tabindex]:not([tabindex="-1"])',
          )
          ?.focus(),
      0,
    );
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && ref.current) {
        const all = [
          ...ref.current.querySelectorAll<HTMLElement>(
            'button,input,select,textarea,[tabindex]:not([tabindex="-1"])',
          ),
        ].filter((x) => !x.hasAttribute("disabled"));
        if (!all.length) return;
        const first = all[0];
        const last = all.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      clearTimeout(t);
      document.removeEventListener("keydown", key);
      previous.current?.focus();
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div
      className="dialog-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={`dialog dialog-${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        ref={ref}
      >
        <header>
          <h2 id="dialog-title">{title}</h2>
          <Button variant="ghost" aria-label="Close dialog" onClick={onClose}>
            <X size={19} />
          </Button>
        </header>
        <div className="dialog-body">{children}</div>
      </div>
    </div>
  );
}

type Toast = { id: number; message: string; type: "success" | "error" };
const ToastContext = createContext<
  (message: string, type?: Toast["type"]) => void
>(() => {});
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const notify = useCallback(
    (message: string, type: Toast["type"] = "success") => {
      const id = Date.now();
      setToasts((v) => [...v, { id, message, type }]);
      window.setTimeout(
        () => setToasts((v) => v.filter((t) => t.id !== id)),
        4500,
      );
    },
    [],
  );
  return (
    <ToastContext.Provider value={notify}>
      {children}
      <div className="toast-region" aria-live="polite">
        {toasts.map((t) => (
          <div className={`toast toast-${t.type}`} key={t.id}>
            {t.type === "success" ? <CheckCircle2 /> : <AlertCircle />}
            <span>{t.message}</span>
            <button
              aria-label="Dismiss notification"
              onClick={() => setToasts((v) => v.filter((x) => x.id !== t.id))}
            >
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
export const useToast = () => useContext(ToastContext);
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  onConfirm,
  onClose,
  danger = false,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onClose: () => void;
  danger?: boolean;
}) {
  return (
    <Dialog open={open} title={title} onClose={onClose} size="sm">
      <p>{message}</p>
      <div className="dialog-actions">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button variant={danger ? "danger" : "primary"} onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </Dialog>
  );
}
export function SubmitForm({
  onSubmit,
  children,
  className = "",
}: {
  onSubmit: () => unknown | Promise<unknown>;
  children: ReactNode;
  className?: string;
}) {
  return (
    <form
      className={className}
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        void onSubmit();
      }}
    >
      {children}
    </form>
  );
}
