"use client";

import { useEffect, useState } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Navbar } from "@/components/layout/Navbar";
import { cn } from "@/lib/utils";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const x = (e.clientX / window.innerWidth - 0.5) * 40;
      const y = (e.clientY / window.innerHeight - 0.5) * 40;
      
      const glow1 = document.getElementById("glow-1");
      const glow2 = document.getElementById("glow-2");
      
      if (glow1) glow1.style.transform = `translate(${x}px, ${y}px)`;
      if (glow2) glow2.style.transform = `translate(${-x}px, ${-y}px)`;
    };
    
    document.addEventListener("mousemove", handleMouseMove);
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
    };
  }, []);

  return (
    <div className="min-h-screen relative">
      {/* Crimson Ambient Glows */}
      <div className="ambient-glow bg-[#b91a24] -top-1/4 -left-1/4" id="glow-1"></div>
      <div className="ambient-glow bg-[#b91a24] bottom-0 right-0" id="glow-2"></div>

      <Navbar />
      <div className="flex min-h-screen">
        <Sidebar isCollapsed={isCollapsed} onToggle={() => setIsCollapsed(!isCollapsed)} />
        <main className={cn(
          "flex-1 pt-24 pb-12 px-6 md:pr-margin-desktop overflow-y-auto transition-all duration-300",
          isCollapsed ? "md:pl-36" : "md:pl-80"
        )}>
          {children}
        </main>
      </div>
    </div>
  );
}
