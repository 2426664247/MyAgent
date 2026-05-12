import * as React from "react";
import { cn } from "../../lib/utils";

type ButtonVariant = "default" | "secondary" | "ghost" | "destructive" | "outline";
type ButtonSize = "sm" | "default" | "icon";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const variants: Record<ButtonVariant, string> = {
  default: "bg-zinc-950 text-zinc-50 hover:bg-zinc-800",
  secondary: "bg-zinc-100 text-zinc-900 hover:bg-zinc-200",
  ghost: "bg-transparent text-zinc-700 hover:bg-zinc-100",
  destructive: "bg-red-600 text-white hover:bg-red-700",
  outline: "border border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-50",
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs",
  default: "h-9 px-4 text-sm",
  icon: "h-8 w-8 p-0",
};

export function Button({ className, variant = "default", size = "default", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex shrink-0 items-center justify-center gap-2 rounded-md font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}
