"use client";

import { useAuth } from "@/components/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { LogOut, Bell } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

export function Navbar() {
  const { logout } = useAuth();
  const [liveStatus, setLiveStatus] = useState(false);

  useEffect(() => {
    const checkLiveStatus = async () => {
      try {
        const data = await fetchApi<{active: boolean}>("/live/status");
        setLiveStatus(data.active);
      } catch {
        setLiveStatus(false);
      }
    };
    checkLiveStatus();
    const interval = setInterval(checkLiveStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <nav className="fixed top-0 w-full z-50 backdrop-blur-xl bg-black/40 border-b border-white/5 flex justify-between items-center px-margin-desktop h-16">
      <div className="flex items-center gap-4">
        <Link href="/dashboard" className="flex items-center gap-2">
          <span className="text-2xl font-bold text-primary tracking-tighter font-space">
            F1 Nexus
          </span>
        </Link>
        
        {liveStatus && (
          <Badge variant="destructive" className="animate-pulse ml-4 font-mono text-[9px] uppercase tracking-wider bg-primary/20 text-primary border border-primary/30">
            Live Session Active
          </Badge>
        )}
      </div>

      <div className="flex items-center gap-4">
        <button className="text-[11px] font-bold text-primary hover:bg-glass-hover px-4 py-2 rounded-lg transition-all duration-300 uppercase tracking-widest font-mono hidden md:inline-block">
          Live Sensors
        </button>

        <Button variant="ghost" size="icon" className="relative text-on-surface-variant hover:text-white hover:bg-white/5 transition-all">
          <Bell className="w-5 h-5" />
          <span className="absolute top-2 right-2 w-2 h-2 bg-primary rounded-full"></span>
        </Button>

        <Button variant="ghost" size="icon" onClick={logout} title="Sign Out" className="text-on-surface-variant hover:text-primary hover:bg-white/5 transition-all">
          <LogOut className="w-5 h-5" />
        </Button>
      </div>
    </nav>
  );
}
