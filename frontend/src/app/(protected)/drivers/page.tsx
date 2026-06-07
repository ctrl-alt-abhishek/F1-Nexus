"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Spinner } from "@/components/ui/spinner";
import { Skeleton } from "@/components/ui/skeleton";
import Link from "next/link";

interface DriverInfo {
  code: string;
  full_name: string;
  nationality: string;
  team: string | null;
  car_number: number | null;
}

export default function DriversPage() {
  const [drivers, setDrivers] = useState<DriverInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [year, setYear] = useState(new Date().getFullYear());
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    async function loadDrivers() {
      setLoading(true);
      try {
        const data = await fetchApi<DriverInfo[]>(`/drivers?year=${year}`);
        setDrivers(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadDrivers();
  }, [year]);

  const filteredDrivers = drivers.filter(driver =>
    driver.full_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    driver.code.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (driver.team && driver.team.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div className="space-y-12 max-w-7xl mx-auto animate-in fade-in duration-500">
      {/* Header Section */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <h1 className="text-5xl font-bold text-on-surface tracking-tight font-space">Driver Registry</h1>
          <p className="text-on-surface-variant max-w-2xl mt-3 text-lg">
            Real-time telemetry and performance analysis for the {year} grid. Filter by team or search the grid.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="SEARCH GRID..."
              className="bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none w-64 text-white placeholder-on-surface-variant font-mono uppercase transition-all"
            />
          </div>
          <div className="flex gap-1.5">
            {[2026, 2025, 2024, 2023, 2022].map(y => (
              <button
                key={y}
                onClick={() => setYear(y)}
                className={`px-4 py-3 border text-[10px] font-bold rounded-xl transition-all font-mono uppercase tracking-widest ${
                  year === y
                    ? "bg-primary border-primary text-white"
                    : "bg-white/5 border-white/10 text-on-surface-variant hover:border-primary/50 hover:text-white"
                }`}
              >
                {y}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* Driver Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-panel-gap">
          {[...Array(8)].map((_, i) => (
            <Skeleton key={i} className="h-[250px] w-full" />
          ))}
        </div>
      ) : filteredDrivers.length === 0 ? (
        <div className="text-center py-20 text-on-surface-variant/50 font-mono uppercase text-sm border border-dashed border-white/5 rounded-2xl bg-white/[0.01]">
          No drivers found matching your search.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-panel-gap">
          {filteredDrivers.map((driver) => (
            <Link key={driver.code} href={`/drivers/${driver.code}`} className="flex">
              <div className="glass-card hover-float group relative overflow-hidden flex flex-col p-6 w-full">
                <div className="flex justify-between items-start mb-6">
                  <div className="flex-1">
                    <span className="text-[10px] font-bold text-primary uppercase tracking-[0.2em] font-mono">
                      {driver.car_number ? `Car ${driver.car_number}` : "Driver Profile"}
                    </span>
                    <h2 className="text-2xl font-bold leading-tight mt-1 font-space text-white">{driver.full_name}</h2>
                  </div>
                  <span className="text-2xl font-bold font-mono opacity-10 text-white select-none">{driver.code}</span>
                </div>
                
                <div className="flex items-center gap-3 mb-8 p-4 bg-white/5 rounded-2xl border border-white/5">
                  <div>
                    <p className="text-[11px] font-bold text-white font-space">{driver.team || "Free Agent"}</p>
                    <p className="text-[9px] text-on-surface-variant font-bold uppercase tracking-widest mt-0.5 font-mono">
                      {driver.nationality || "—"}
                    </p>
                  </div>
                </div>

                <button className="mt-auto w-full py-4 bg-primary/10 group-hover:bg-primary/20 border border-primary/20 rounded-xl text-[10px] font-bold transition-all flex items-center justify-center gap-2 text-primary uppercase tracking-[0.2em] font-mono">
                  View Telemetry
                </button>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
