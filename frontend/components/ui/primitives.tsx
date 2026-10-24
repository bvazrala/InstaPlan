import type { ReactNode } from "react";

export const Card = ({ children, className = "" }: { children: ReactNode; className?: string }) => (
  <div className={`rounded-2xl border border-line bg-white p-3.5 ${className}`}>{children}</div>
);

export const PrimaryButton = ({ children, onClick, className = "" }: { children: ReactNode; onClick?: () => void; className?: string }) => (
  <button onClick={onClick} className={`brand-gradient w-full rounded-xl py-2.5 text-sm font-semibold text-white transition active:scale-[.98] ${className}`}>{children}</button>
);

export const GhostButton = ({ children, onClick, className = "" }: { children: ReactNode; onClick?: () => void; className?: string }) => (
  <button onClick={onClick} className={`w-full rounded-xl bg-surface py-2.5 text-sm font-semibold text-foreground transition hover:bg-neutral-100 active:scale-[.98] ${className}`}>{children}</button>
);

export const Label = ({ children }: { children: ReactNode }) => (
  <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">{children}</p>
);

export const Chip = ({ children, on, onClick }: { children: ReactNode; on?: boolean; onClick?: () => void }) => (
  <button onClick={onClick} className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${on ? "brand-gradient text-white" : "bg-surface text-foreground hover:bg-neutral-100"}`}>{children}</button>
);
