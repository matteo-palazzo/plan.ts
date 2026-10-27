import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

interface ToastAction {
  label: string;
  onClick: () => void;
}

interface Toast {
  id: number;
  message: string;
  tone: "info" | "success" | "error";
  actions: ToastAction[];
}

interface ToastOptions {
  tone?: Toast["tone"];
  actions?: ToastAction[];
  duration?: number;
}

const ToastContext = createContext<(message: string, options?: ToastOptions) => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback(
    (message: string, options: ToastOptions = {}) => {
      const id = nextId.current++;
      const toast: Toast = { id, message, tone: options.tone ?? "info", actions: options.actions ?? [] };
      setToasts((current) => [...current.slice(-2), toast]);
      window.setTimeout(() => dismiss(id), options.duration ?? (toast.actions.length ? 15000 : 3500));
    },
    [dismiss],
  );

  const value = useMemo(() => show, [show]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.tone}`} role={toast.tone === "error" ? "alert" : "status"}>
            <span className="toast-message">{toast.message}</span>
            {toast.actions.map((action) => (
              <button
                key={action.label}
                type="button"
                className="toast-action"
                onClick={() => {
                  dismiss(toast.id);
                  action.onClick();
                }}
              >
                {action.label}
              </button>
            ))}
            <button type="button" className="toast-close" aria-label="Chiudi notifica" onClick={() => dismiss(toast.id)}>
              ✕
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
