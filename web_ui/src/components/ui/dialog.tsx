import * as React from "react";
import { X } from "lucide-react";
import { cn } from "../../lib/utils";

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: React.ReactNode;
}

export function Dialog({ open, onOpenChange, title, description, children }: DialogProps) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-zinc-950/40 px-4">
      <div className="absolute inset-0" onClick={() => onOpenChange(false)} />
      <section
        className={cn(
          "relative z-10 w-full max-w-lg rounded-xl border border-zinc-200 bg-white p-5 shadow-2xl",
          "animate-in fade-in zoom-in-95",
        )}
      >
        <button
          className="absolute right-4 top-4 rounded-md p-1 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
          onClick={() => onOpenChange(false)}
          aria-label="关闭"
        >
          <X size={16} />
        </button>
        <div className="pr-8">
          <h2 className="text-base font-semibold text-zinc-950">{title}</h2>
          {description ? <p className="mt-1 text-sm text-zinc-500">{description}</p> : null}
        </div>
        <div className="mt-4">{children}</div>
      </section>
    </div>
  );
}
