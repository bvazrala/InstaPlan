import type { ButtonHTMLAttributes, ReactNode } from "react";

// Small component set modelled on shadcn/ui (new-york, neutral): dark primary, outlined inputs, muted tab list, compact badges.

type Variant = "default" | "secondary" | "outline" | "ghost" | "destructive";
type Size = "default" | "sm" | "lg" | "icon";

const VARIANTS: Record<Variant, string> = {
  default: "bg-neutral-900 text-white hover:bg-neutral-800",
  secondary: "bg-neutral-100 text-neutral-900 hover:bg-neutral-200",
  outline: "border border-line bg-white text-neutral-900 shadow-xs hover:bg-neutral-50",
  ghost: "text-neutral-900 hover:bg-neutral-100",
  destructive: "bg-red-600 text-white hover:bg-red-700",
};
const SIZES: Record<Size, string> = {
  default: "h-9 px-4",
  sm: "h-8 px-3 text-[13px]",
  lg: "h-10 px-6",
  icon: "size-9",
};

export function Button({ variant = "default", size = "default", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button
      {...props}
      className={`inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-md text-sm font-medium outline-none transition-all focus-visible:ring-[3px] focus-visible:ring-neutral-300 active:scale-[.98] disabled:pointer-events-none disabled:opacity-50 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
    />
  );
}

export const inputCls =
  "h-9 w-full rounded-md border border-line bg-white px-3 text-sm shadow-xs outline-none transition placeholder:text-muted focus-visible:border-neutral-400 focus-visible:ring-[3px] focus-visible:ring-neutral-200";
export const textareaCls =
  "w-full resize-none rounded-md border border-line bg-white px-3 py-2 text-sm shadow-xs outline-none transition placeholder:text-muted focus-visible:border-neutral-400 focus-visible:ring-[3px] focus-visible:ring-neutral-200";

export const Card = ({ children, className = "" }: { children: ReactNode; className?: string }) => (
  <div className={`rounded-xl border border-line bg-white p-4 shadow-xs ${className}`}>{children}</div>
);

export const PrimaryButton = ({ children, onClick, className = "", disabled = false }: { children: ReactNode; onClick?: () => void; className?: string; disabled?: boolean }) => (
  <Button onClick={onClick} disabled={disabled} className={`w-full ${className}`}>{children}</Button>
);

export const GhostButton = ({ children, onClick, className = "" }: { children: ReactNode; onClick?: () => void; className?: string }) => (
  <Button variant="secondary" onClick={onClick} className={`w-full ${className}`}>{children}</Button>
);

export const Label = ({ children }: { children: ReactNode }) => (
  <p className="mb-2 text-[13px] font-medium text-muted">{children}</p>
);

const BADGES = {
  default: "border-transparent bg-neutral-900 text-white",
  secondary: "border-transparent bg-neutral-100 text-neutral-700",
  outline: "border-line text-neutral-700",
  success: "border-transparent bg-emerald-50 text-emerald-700",
  warning: "border-transparent bg-amber-50 text-amber-700",
};
export const Badge = ({ children, variant = "secondary" }: { children: ReactNode; variant?: keyof typeof BADGES }) => (
  <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium ${BADGES[variant]}`}>{children}</span>
);

/** Toggle button for picking one or more options. */
export const Chip = ({ children, on, onClick }: { children: ReactNode; on?: boolean; onClick?: () => void }) => (
  <button
    onClick={onClick}
    aria-pressed={on}
    className={`h-8 rounded-md border px-3 text-[13px] font-medium transition ${on ? "border-neutral-900 bg-neutral-900 text-white" : "border-line bg-white text-neutral-900 shadow-xs hover:bg-neutral-50"}`}
  >
    {children}
  </button>
);

/** Tabs list: muted track with a raised active trigger. */
export function Segmented<T extends string>({ value, options, onChange }: { value: T | null; options: { id: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <div role="tablist" className="flex h-9 w-full items-center rounded-lg bg-neutral-100 p-[3px]">
      {options.map((o) => (
        <button
          key={o.id}
          role="tab"
          aria-selected={value === o.id}
          onClick={() => onChange(o.id)}
          className={`h-full flex-1 rounded-md text-[13px] font-medium transition ${value === o.id ? "bg-white text-neutral-900 shadow-sm" : "text-neutral-500 hover:text-neutral-900"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export const Progress = ({ value }: { value: number }) => (
  <div className="h-2 w-full overflow-hidden rounded-full bg-neutral-100" role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}>
    <div className="h-full rounded-full bg-neutral-900 transition-all" style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
  </div>
);

export const Switch = ({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) => (
  <button role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)} className={`relative h-[18px] w-8 shrink-0 rounded-full transition ${on ? "bg-neutral-900" : "bg-neutral-300"}`}>
    <span className={`absolute left-0.5 top-0.5 size-3.5 rounded-full bg-white shadow transition ${on ? "translate-x-3.5" : ""}`} />
  </button>
);
