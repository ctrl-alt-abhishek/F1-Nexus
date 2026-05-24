"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import Link from "next/link";
import { Flag, MapPin, Calendar, ArrowRight } from "lucide-react";

// Matches backend RoundSchema (which includes nested CircuitSchema)
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
    <div className="space-y-6 max-w-6xl mx-auto animate-in fade-in">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Flag className="text-red-500 w-8 h-8" />
            Season Calendar
          </h1>
          <p className="text-slate-400 mt-1">Race results and telemetry analysis</p>
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
      ) : races.length === 0 ? (
        <div className="text-center py-20 text-slate-500">No races found for {year}.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {races.map((round) => (
            <Card key={round.round_number} className="glass hover:border-slate-600 transition-colors flex flex-col group">
              <CardHeader className="pb-3">
                <div className="flex justify-between items-start mb-2">
                  <Badge variant="secondary">Round {round.round_number}</Badge>
                </div>
                <CardTitle className="text-xl">{round.name || `Round ${round.round_number}`}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 flex-1">
                {round.race_date && (
                  <div className="flex items-center gap-2 text-sm text-slate-400">
                    <Calendar className="w-4 h-4" />
                    {new Date(round.race_date).toLocaleDateString(undefined, { weekday: 'short', year: 'numeric', month: 'long', day: 'numeric' })}
                  </div>
                )}
                {round.circuit && (
                  <div className="flex items-center gap-2 text-sm text-slate-400">
                    <MapPin className="w-4 h-4" />
                    {round.circuit.name}{round.circuit.city ? `, ${round.circuit.city}` : ''}{round.circuit.country ? ` · ${round.circuit.country}` : ''}
                  </div>
                )}
                {round.circuit?.track_length_km && (
                  <div className="text-xs text-slate-500 pt-2 border-t border-slate-800">
                    Track length: {round.circuit.track_length_km} km
                  </div>
                )}
              </CardContent>
              <CardFooter className="pt-0">
                <Link 
                  href={`/races/${year}/${round.round_number}`}
                  className="w-full flex items-center justify-center gap-2 bg-slate-800/50 hover:bg-slate-800 py-2 rounded-md text-sm font-medium transition-colors group-hover:text-red-400"
                >
                  View Telemetry <ArrowRight className="w-4 h-4" />
                </Link>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
