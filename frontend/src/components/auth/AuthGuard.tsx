"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "./AuthProvider";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) {
      // Allow access to login/signup pages even when not authenticated
      if (!pathname.startsWith("/login") && !pathname.startsWith("/signup")) {
        router.push("/login");
      }
    }
  }, [user, loading, router, pathname]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-950 text-slate-200">
        <div className="animate-pulse flex flex-col items-center">
          <div className="h-12 w-12 border-4 border-red-600 border-t-transparent rounded-full animate-spin"></div>
          <p className="mt-4 text-sm font-medium tracking-widest uppercase">Loading Nexus</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
