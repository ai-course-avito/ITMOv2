"use client";

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { Icon } from "@/components/ui";

type Tone = "info" | "error" | "success";
type ToastItem = { id: number; message: string; tone: Tone };

const ToastContext = createContext<(message: string, tone?: Tone) => void>(() => {});

export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => setItems((list) => list.filter((t) => t.id !== id)), []);

  const toast = useCallback(
    (message: string, tone: Tone = "info") => {
      const id = nextId.current++;
      setItems((list) => [...list.slice(-2), { id, message, tone }]);
      setTimeout(() => dismiss(id), tone === "error" ? 6000 : 3800);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="snackbar-host" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`snackbar ${t.tone}`}>
            <Icon name={t.tone === "error" ? "error" : t.tone === "success" ? "check_circle" : "info"} fill />
            <span className="t-body-m">{t.message}</span>
            <button type="button" onClick={() => dismiss(t.id)}>
              OK
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
