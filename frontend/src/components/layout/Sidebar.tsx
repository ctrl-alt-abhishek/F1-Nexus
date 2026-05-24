"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { LayoutDashboard, Activity, Flag, Users, BarChart3, MessageSquare, Settings } from "lucide-react";

const NAV_ITEMS = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Live Timing", href: "/live", icon: Activity },
  { name: "Races", href: "/races", icon: Flag },
  { name: "Drivers", href: "/drivers", icon: Users },
  { name: "Predictions", href: "/predictions", icon: BarChart3 },
  { name: "Nexus AI", href: "/chat", icon: MessageSquare },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-950/80 backdrop-blur-xl flex flex-col hidden md:flex h-full fixed left-0 top-0 pt-16">
      <div className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
        <div className="mb-8 px-4">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Platform</h2>
          {NAV_ITEMS.map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors mb-1",
                  isActive 
                    ? "bg-red-600/10 text-red-500 border-r-2 border-red-500" 
                    : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-100"
                )}
              >
                <item.icon className={cn("w-5 h-5", isActive ? "text-red-500" : "text-slate-500")} />
                {item.name}
              </Link>
            );
          })}
        </div>
      </div>
      
      <div className="p-4 border-t border-slate-800">
        <Link 
          href="/settings"
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
            pathname.startsWith("/settings")
              ? "bg-red-600/10 text-red-500 border-r-2 border-red-500"
              : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-100"
          )}
        >
          <Settings className="w-5 h-5 text-slate-500" />
          Settings
        </Link>
      </div>
    </aside>
  );
}
