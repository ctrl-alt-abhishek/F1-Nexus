import * as React from "react"
import { cn } from "@/lib/utils"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "success" | "warning"
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        {
          "border-transparent bg-red-600 text-white hover:bg-red-700": variant === "default",
          "border-transparent bg-slate-800 text-slate-100 hover:bg-slate-700": variant === "secondary",
          "border-transparent bg-red-900/50 text-red-200 hover:bg-red-900/80": variant === "destructive",
          "text-slate-300 border-slate-700": variant === "outline",
          "border-transparent bg-emerald-500/20 text-emerald-400": variant === "success",
          "border-transparent bg-amber-500/20 text-amber-400": variant === "warning",
        },
        className
      )}
      {...props}
    />
  )
}

export { Badge }
