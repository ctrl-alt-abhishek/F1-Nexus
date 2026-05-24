"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/components/auth/AuthProvider";
import { LayoutDashboard, Activity, Flag, Users, TrendingUp, Sparkles, Settings } from "lucide-react";

interface SidebarProps {
  isCollapsed?: boolean;
  onToggle?: () => void;
}

const NAV_ITEMS = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Live Timing", href: "/live", icon: Activity },
  { name: "Races & Analysis", href: "/races", icon: Flag },
  { name: "Drivers", href: "/drivers", icon: Users },
  { name: "Predictions", href: "/predictions", icon: TrendingUp },
  { name: "Nexus AI Chat", href: "/chat", icon: Sparkles },
];

export function Sidebar({ isCollapsed = false, onToggle }: SidebarProps) {
  const pathname = usePathname();
  const { user } = useAuth();

  const isActive = (href: string) => {
    if (href === "/dashboard") {
      return pathname === href;
    }
    return pathname.startsWith(href);
  };

  const getUserInitials = (name: string) => {
    return name
      .split(" ")
      .map((n) => n[0])
      .slice(0, 2)
      .join("")
      .toUpperCase();
  };

  return (
    <aside className={cn(
      "fixed left-6 top-24 bottom-6 z-40 hidden md:flex flex-col sidebar-glass py-6 transition-all duration-300 ease-in-out",
      isCollapsed ? "w-20 px-4" : "w-64 px-6"
    )}>
      <div className="flex flex-col h-full">
        {/* Toggle burger menu */}
        <div className={cn("mb-8 flex items-center", isCollapsed ? "justify-center" : "justify-between")}>
          <button 
            onClick={onToggle}
            className="text-on-surface-variant hover:text-white transition-colors p-1 hover:bg-white/5 rounded-lg"
            title={isCollapsed ? "Expand Menu" : "Collapse Menu"}
          >
            <svg fill="none" height="24" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" width="24">
              <line x1="3" x2="21" y1="12" y2="12"></line>
              <line x1="3" x2="21" y1="6" y2="6"></line>
              <line x1="3" x2="21" y1="18" y2="18"></line>
            </svg>
          </button>
          {!isCollapsed && (
            <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em] opacity-50 font-mono select-none">
              Menu
            </span>
          )}
        </div>

        {/* Main Navigation Links */}
        <nav className="flex-1 space-y-1 overflow-y-auto pr-1">
          {NAV_ITEMS.map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center rounded-xl transition-all font-mono uppercase tracking-widest font-bold",
                  isCollapsed 
                    ? "justify-center h-12 w-12 mx-auto text-[11px]" 
                    : "px-4 py-3 text-[11px] gap-3",
                  active
                    ? "bg-primary/10 text-primary border-l-2 border-primary"
                    : "text-on-surface-variant hover:text-white hover:bg-white/5"
                )}
                title={isCollapsed ? item.name : undefined}
              >
                <item.icon className="w-4.5 h-4.5 shrink-0" />
                {!isCollapsed && <span>{item.name}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Bottom Actions & User Profile Card */}
        <div className="mt-auto space-y-4 pt-6 border-t border-white/5">
          {!isCollapsed && (
            <div>
              <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em] opacity-50 font-mono select-none">
                Preferences
              </span>
            </div>
          )}
          
          <Link
            href="/settings"
            className={cn(
              "flex items-center rounded-xl transition-all font-mono uppercase tracking-widest font-bold mb-2",
              isCollapsed 
                ? "justify-center h-12 w-12 mx-auto text-[10px]" 
                : "px-4 py-2 text-[10px] gap-3",
              isActive("/settings")
                ? "bg-primary/10 text-primary border-l-2 border-primary"
                : "text-on-surface-variant hover:text-white hover:bg-white/5"
            )}
            title={isCollapsed ? "Settings" : undefined}
          >
            <Settings className="w-4 h-4 shrink-0" />
            {!isCollapsed && <span>Settings</span>}
          </Link>

          <div className={cn(
            "flex items-center bg-white/5 rounded-2xl border border-white/5",
            isCollapsed ? "justify-center p-3" : "justify-between px-4 py-4"
          )}>
            {isCollapsed ? (
              <div 
                className="w-8 h-8 rounded-full bg-primary/20 border border-primary/30 flex items-center justify-center text-primary font-bold font-space text-xs select-none cursor-help"
                title={`${user?.displayName || "Alex Mercer"} (${user ? "Pro Member" : "Guest Mode"})`}
              >
                {getUserInitials(user?.displayName || "Alex Mercer")}
              </div>
            ) : (
              <div className="flex flex-col">
                <p className="text-[13px] font-bold text-on-surface leading-none font-space">
                  {user?.displayName || "Alex Mercer"}
                </p>
                <p className="text-[9px] text-primary font-bold uppercase tracking-[0.15em] mt-1 font-mono">
                  {user ? "Pro Member" : "Guest Mode"}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}
