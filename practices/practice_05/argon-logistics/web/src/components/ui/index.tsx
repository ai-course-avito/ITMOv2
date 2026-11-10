"use client";

import { useEffect, useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";

export function Icon({ name, fill, size, className = "" }: { name: string; fill?: boolean; size?: 18 | 20 | 32 | 48; className?: string }) {
  return (
    <span className={`ms ${fill ? "fill" : ""} ${size ? `s${size}` : ""} ${className}`} aria-hidden="true">
      {name}
    </span>
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "filled" | "tonal" | "outlined" | "text" | "danger" | "danger-filled";
  icon?: string;
  small?: boolean;
};

export function Button({ variant = "filled", icon, small, className = "", children, ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      {...rest}
      className={`btn stateful ${variant} ${icon ? "with-icon" : ""} ${small ? "small" : ""} ${className}`}
    >
      {icon && <Icon name={icon} size={18} />}
      {children}
    </button>
  );
}

type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  icon: string;
  label: string;
  variant?: "standard" | "tonal" | "filled" | "danger";
  small?: boolean;
  fill?: boolean;
};

export function IconButton({ icon, label, variant = "standard", small, fill, className = "", ...rest }: IconButtonProps) {
  const v = variant === "standard" ? "" : variant;
  return (
    <button type="button" aria-label={label} title={label} {...rest} className={`icon-btn stateful ${v} ${small ? "small" : ""} ${className}`}>
      <Icon name={icon} fill={fill} />
    </button>
  );
}

export function Chip({
  children,
  icon,
  selected,
  tone,
  compact,
  onClick,
  title,
}: {
  children: ReactNode;
  icon?: string;
  selected?: boolean;
  tone?: "planned" | "transit" | "ready" | "done" | "cancelled" | "returned" | "warning";
  compact?: boolean;
  onClick?: () => void;
  title?: string;
}) {
  const classes = `chip ${selected ? "selected" : ""} ${tone ? `tone-${tone}` : ""} ${compact ? "compact" : ""} ${onClick ? "stateful" : "static"}`;
  const content = (
    <>
      {icon && <Icon name={icon} size={18} />}
      {children}
    </>
  );
  return onClick ? (
    <button type="button" className={classes} onClick={onClick} title={title}>
      {content}
    </button>
  ) : (
    <span className={classes} title={title}>
      {content}
    </span>
  );
}

type FieldProps = {
  label: string;
  error?: string;
  hint?: string;
  dense?: boolean;
};

export function TextField({ label, error, hint, dense, className = "", ...rest }: FieldProps & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <div className={className}>
      <div className={`field ${dense ? "dense" : ""} ${error ? "invalid" : ""}`}>
        <input id={id} {...rest} aria-invalid={!!error} />
        <label htmlFor={id}>{label}</label>
      </div>
      {(error || hint) && <div className="field-hint">{error ?? hint}</div>}
    </div>
  );
}

export function SelectField({
  label,
  dense,
  error,
  children,
  className = "",
  ...rest
}: FieldProps & SelectHTMLAttributes<HTMLSelectElement>) {
  const id = useId();
  return (
    <div className={className}>
      <div className={`field ${dense ? "dense" : ""} ${error ? "invalid" : ""}`}>
        <select id={id} {...rest}>
          {children}
        </select>
        <label htmlFor={id}>{label}</label>
        <Icon name="arrow_drop_down" className="caret" />
      </div>
      {error && <div className="field-hint">{error}</div>}
    </div>
  );
}

export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="switch">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="track">
        <span className="thumb" />
      </span>
      <span className="t-body-l">{label}</span>
    </label>
  );
}

export function Dialog({
  title,
  onClose,
  children,
  actions,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  actions: ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="scrim" onPointerDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog" role="dialog" aria-modal="true" aria-label={title}>
        <h2 className="t-headline-s">{title}</h2>
        {children}
        <div className="actions">{actions}</div>
      </div>
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon: string; title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <Icon name={icon} size={48} />
      <div className="t-title-m" style={{ color: "var(--md-on-surface)" }}>
        {title}
      </div>
      {children && <div className="t-body-m">{children}</div>}
    </div>
  );
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel,
  danger,
  onConfirm,
  onClose,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  danger?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Dialog
      title={title}
      onClose={onClose}
      actions={
        <>
          <Button variant="text" onClick={onClose}>
            Отмена
          </Button>
          <Button variant={danger ? "danger-filled" : "filled"} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="t-body-m muted" style={{ margin: 0 }}>
        {message}
      </p>
    </Dialog>
  );
}
