"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import Link from "next/link";
import { Users, Flag } from "lucide-react";

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

  return (
    <div className="space-y-6 max-w-6xl mx-auto animate-in fade-in">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Users className="text-red-500 w-8 h-8" />
            Drivers
          </h1>
          <p className="text-slate-400 mt-1">Grid lineup and telemetry profiles</p>
        </div>
        
        <div className="flex gap-2">
          {[2026, 2025, 2024, 2023, 2022].map(y => (
            <button
              key={y}
              onClick={() => setYear(y)}
              className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                year === y ? "bg-red-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              {y}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Spinner size="lg" /></div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {drivers.map((driver) => (
            <Link key={driver.code} href={`/drivers/${driver.code}`}>
              <Card className="glass hover:border-red-900/50 hover:bg-slate-800/80 transition-all cursor-pointer h-full group">
                <CardHeader className="pb-2 flex flex-row items-center justify-between">
                  <div className="text-3xl font-bold italic text-slate-700 group-hover:text-red-500/20 transition-colors">
                    {driver.car_number || "00"}
                  </div>
                  <Badge variant="outline" className="font-mono text-lg">{driver.code}</Badge>
                </CardHeader>
                <CardContent className="space-y-1">
                  <CardTitle className="text-xl">{driver.full_name}</CardTitle>
                  <p className="text-sm text-slate-400 font-medium">{driver.team || "Free Agent"}</p>
                </CardContent>
                <CardFooter className="pt-2">
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <Flag className="w-3 h-3" /> {driver.nationality || "—"}
                  </div>
                </CardFooter>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
