"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Spinner } from "@/components/ui/spinner";
import { Skeleton } from "@/components/ui/skeleton";
import Link from "next/link";
import { Flag, MapPin, Calendar, ArrowRight } from "lucide-react";

interface CircuitInfo {
  id: number;
  name: string;
  country: string | null;
  city: string | null;
  track_length_km: number | null;
  lap_record_s: number | null;
}

interface RoundInfo {
  id: number;
  season_year: number;
  round_number: number;
  name: string | null;
  race_date: string | null;
  circuit: CircuitInfo | null;
}

export default function RacesPage() {
  const [races, setRaces] = useState<RoundInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [year, setYear] = useState(new Date().getFullYear());

  useEffect(() => {
    async function loadRaces() {
      setLoading(true);
      try {
        const data = await fetchApi<RoundInfo[]>(`/races/${year}`);
        setRaces(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadRaces();
  }, [year]);

  return (
    <div className="space-y-12 max-w-7xl mx-auto animate-in fade-in duration-500">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <h1 className="text-5xl font-bold text-on-surface tracking-tight font-space flex items-center gap-3">
            <Flag className="text-primary w-10 h-10" />
            Season Calendar
          </h1>
          <p className="text-on-surface-variant mt-3 text-lg font-space">
            Race results and tyre degradation telemetry logs for the {year} season rounds.
          </p>
        </div>
        
        <div className="flex gap-1.5">
          {[2026, 2025, 2024, 2023, 2022].map(y => (
            <button
              key={y}
              onClick={() => setYear(y)}
              className={`px-4 py-3 border text-[10px] font-bold rounded-xl transition-all font-mono uppercase tracking-widest ${
                year === y
                  ? "bg-primary border-primary text-white font-bold"
                  : "bg-white/5 border-white/10 text-on-surface-variant hover:border-primary/50 hover:text-white"
              }`}
            >
              {y}
            </button>
          ))}
        </div>
      </div>

      {/* Grid List */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-[250px] w-full" />
          ))}
        </div>
      ) : races.length === 0 ? (
        <div className="text-center py-20 text-on-surface-variant/50 font-mono uppercase text-sm border border-dashed border-white/5 rounded-2xl bg-white/[0.01]">
          No races found for {year} season.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {races.map((round) => (
            <div 
              key={round.round_number} 
              className="glass-card hover-float group flex flex-col justify-between p-6 border border-white/5 min-h-[250px]"
            >
              <div>
                <div className="flex justify-between items-start mb-4">
                  <span className="font-mono text-[10px] font-bold uppercase tracking-wider bg-white/5 text-on-surface-variant border border-white/10 px-3 py-1 rounded-full">
                    Round {String(round.round_number).padStart(2, '0')}
                  </span>
                </div>
                <h3 className="text-xl font-bold font-space text-white leading-snug group-hover:text-primary transition-colors">
                  {round.name || `Round ${round.round_number}`}
                </h3>
                
                <div className="space-y-2.5 mt-6 border-t border-white/5 pt-4">
                  {round.race_date && (
                    <div className="flex items-center gap-2.5 text-xs text-on-surface-variant">
                      <Calendar className="w-4 h-4 text-primary shrink-0" />
                      <span className="font-space">
                        {new Date(round.race_date).toLocaleDateString(undefined, { weekday: 'short', year: 'numeric', month: 'long', day: 'numeric' })}
                      </span>
                    </div>
                  )}
                  {round.circuit && (
                    <div className="flex items-center gap-2.5 text-xs text-on-surface-variant">
                      <MapPin className="w-4 h-4 text-primary shrink-0" />
                      <span className="font-space">
                        {round.circuit.name}{round.circuit.city ? `, ${round.circuit.city}` : ''}{round.circuit.country ? ` • ${round.circuit.country}` : ''}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-white/5 flex items-center justify-between">
                <span className="font-mono text-[9px] text-on-surface-variant/50 uppercase">
                  {round.circuit?.track_length_km ? `${round.circuit.track_length_km} km length` : "Pending config"}
                </span>
                <Link 
                  href={`/races/${year}/${round.round_number}`}
                  className="font-mono text-[10px] font-bold uppercase tracking-widest py-2.5 px-4 bg-primary/10 border border-primary/20 text-primary rounded-xl transition-all hover:bg-primary/20 flex items-center gap-2"
                >
                  Analysis <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
