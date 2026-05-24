"use client";

import { useAuth } from "@/components/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { LogOut, User as UserIcon, Bell } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

export function Navbar() {
  const { user, logout } = useAuth();
  const [liveStatus, setLiveStatus] = useState(false);

  useEffect(() => {
    // Poll the backend health/status to see if a session is active
    const checkLiveStatus = async () => {
      try {
        const data = await fetchApi<{active: boolean}>("/live/status");
        setLiveStatus(data.active);
      } catch {
        setLiveStatus(false);
      }
    };
    checkLiveStatus();
    const interval = setInterval(checkLiveStatus, 30000); // Check every 30s
    return () => clearInterval(interval);
  }, []);

  return (
    <nav className="fixed top-0 left-0 right-0 h-16 border-b border-slate-800 bg-slate-950/80 backdrop-blur-xl z-50 flex items-center justify-between px-4 md:px-6">
      <div className="flex items-center gap-4">
        <Link href="/dashboard" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded bg-red-600 flex items-center justify-center font-bold text-white italic tracking-tighter">
            F1
          </div>
          <span className="text-xl font-bold tracking-tight hidden md:inline-block">
            NEXUS
          </span>
        </Link>
        
        {liveStatus && (
          <Badge variant="destructive" className="animate-pulse ml-4">
            LIVE SESSION
          </Badge>
        )}
      </div>

      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="w-5 h-5" />
          <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full"></span>
        </Button>
        
        <div className="hidden md:flex items-center gap-3 border-l border-slate-800 pl-4">
          <div className="flex flex-col items-end">
            <span className="text-sm font-medium leading-none">{user?.displayName || "Driver"}</span>
            <span className="text-xs text-slate-500 mt-1">{user?.email || "Offline Mode"}</span>
          </div>
          <div className="w-9 h-9 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center">
            <UserIcon className="w-5 h-5 text-slate-400" />
          </div>
        </div>

        <Button variant="ghost" size="icon" onClick={logout} title="Sign Out">
          <LogOut className="w-5 h-5 text-slate-400 hover:text-red-400" />
        </Button>
      </div>
    </nav>
  );
}
