"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fetchApi } from "@/lib/api";
import { Trophy, Clock, Flag, TrendingUp, AlertCircle, Sparkles } from "lucide-react";
import { Spinner } from "@/components/ui/spinner";
import Link from "next/link";

// Matches backend ChampionshipPredictionSchema
interface DriverChampPred {
  driver_code: string;
  full_name: string | null;
  team: string | null;
  current_points: number;
  championship_probability: number;
  podium_probability: number;
  expected_final_points: number;
}

interface ChampionshipPrediction {
  year: number;
  drivers: DriverChampPred[];
  simulations_run: number;
  cached: boolean;
}

// Matches backend RoundSchema
interface RoundInfo {
  id: number;
  season_year: number;
  round_number: number;
  name: string | null;
  race_date: string | null;
  circuit: { name: string; country: string | null; city: string | null } | null;
}

interface LiveStatus {
  active: boolean;
  session_type?: string;
  current_lap?: number;
  race_name?: string | null;
  location?: string | null;
  country?: string | null;
  next_race?: {
    name: string;
    location?: string;
    country?: string;
    date?: string;
    time?: string;
    session_type?: string;
    round?: number;
  } | null;
}

const CURRENT_YEAR = new Date().getFullYear();

export default function DashboardPage() {
  const [predictions, setPredictions] = useState<ChampionshipPrediction | null>(null);
  const [rounds, setRounds] = useState<RoundInfo[]>([]);
  const [liveStatus, setLiveStatus] = useState<LiveStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const [predData, roundData, liveData] = await Promise.allSettled([
          fetchApi<ChampionshipPrediction>(`/predictions/championship/${CURRENT_YEAR}`),
          fetchApi<RoundInfo[]>(`/races/${CURRENT_YEAR}`),
          fetchApi<LiveStatus>("/live/status"),
        ]);

        if (predData.status === "fulfilled") setPredictions(predData.value);
        else setError((predData.reason as Error).message);

        if (roundData.status === "fulfilled") setRounds(roundData.value);

        if (liveData.status === "fulfilled") setLiveStatus(liveData.value);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  // Get the last 3 rounds for "Recent Races"
  const recentRounds = rounds.slice(-3).reverse();

  // Find the next upcoming race (future date) or fallback to the last round
  const now = new Date();
  const nextRace = rounds.find(r => r.race_date && new Date(r.race_date) > now) || rounds[rounds.length - 1];

  const displayRace = liveStatus?.active 
    ? {
        name: liveStatus.race_name || "Canadian Grand Prix",
        location: liveStatus.location || "Montréal",
        country: liveStatus.country || "Canada",
        round: liveStatus.current_lap ? `Lap ${liveStatus.current_lap}` : "Round 5",
        date: "LIVE NOW"
      }
    : liveStatus?.next_race 
      ? {
          name: liveStatus.next_race.name,
          location: liveStatus.next_race.location || "",
          country: liveStatus.next_race.country || "",
          round: `Round ${liveStatus.next_race.round || 5}`,
          date: (() => {
            try {
              const d = new Date(`${liveStatus.next_race.date} ${liveStatus.next_race.time}`);
              return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', timeZone: 'Asia/Kolkata' });
            } catch {
              return liveStatus.next_race.date || 'TBC';
            }
          })()
        }
      : nextRace 
        ? {
            name: nextRace.name || `Round ${nextRace.round_number}`,
            location: nextRace.circuit?.name || "TBC",
            country: nextRace.circuit?.country || "",
            round: `Round ${nextRace.round_number}`,
            date: nextRace.race_date 
              ? new Date(nextRace.race_date).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
              : "TBC"
          }
        : null;

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div>
        <h1 className="text-4xl font-bold tracking-tight text-on-surface font-space">Welcome to the Grid</h1>
        <p className="text-on-surface-variant mt-2 text-md">Here&apos;s your personal telemetry overview for the {CURRENT_YEAR} season.</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <Card className="glass-card hover-float">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold font-mono uppercase tracking-widest text-on-surface-variant">Next Race</CardTitle>
            <Clock className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            {displayRace ? (
              <>
                <div className="text-2xl font-bold font-space tracking-tight text-white">{displayRace.name}</div>
                <p className="text-xs text-on-surface-variant mt-1 font-mono uppercase tracking-wider">
                  {displayRace.location}{displayRace.country ? `, ${displayRace.country}` : ''}
                </p>
                <div className="mt-4 flex gap-2">
                  <Badge className="font-mono text-[9px] uppercase tracking-wider bg-primary/20 text-primary border border-primary/30">
                    {displayRace.date}
                  </Badge>
                  <Badge className="font-mono text-[9px] uppercase tracking-wider bg-white/5 text-on-surface-variant border border-white/10">
                    {displayRace.round}
                  </Badge>
                </div>
              </>
            ) : (
              <div className="text-on-surface-variant font-mono text-sm">Loading...</div>
            )}
          </CardContent>
        </Card>

        <Card className={`glass-card hover-float ${liveStatus?.active ? "border-primary/40 shadow-lg shadow-primary/10" : ""}`}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold font-mono uppercase tracking-widest text-on-surface-variant">Live Status</CardTitle>
            <ActivityIcon className={`h-4 w-4 ${liveStatus?.active ? "text-primary animate-pulse" : "text-on-surface-variant"}`} />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold font-space ${liveStatus?.active ? "text-primary" : "text-white"}`}>
              {liveStatus?.active ? "Active" : "Offline"}
            </div>
            <p className="text-xs text-on-surface-variant mt-1 font-mono uppercase tracking-wider">
              {liveStatus?.active 
                ? `${liveStatus.race_name || "Race"} - Lap ${liveStatus.current_lap || 0}`
                : "No active session"
              }
            </p>
            <Link 
              href="/live" 
              className={`text-xs mt-4 inline-block font-mono font-bold uppercase tracking-wider ${liveStatus?.active ? "text-primary hover:underline" : "text-on-surface-variant hover:text-white"}`}
            >
              Open Race Tower &rarr;
            </Link>
          </CardContent>
        </Card>

        <Card className="glass-card hover-float md:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold font-mono uppercase tracking-widest text-on-surface-variant flex items-center gap-2">
              <Trophy className="h-4 w-4 text-primary" />
              Championship Predictor {CURRENT_YEAR}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex justify-center py-4"><Spinner size="sm" /></div>
            ) : error && !predictions ? (
              <div className="text-xs font-mono uppercase tracking-wider text-primary flex items-center gap-2">
                <AlertCircle className="w-4 h-4"/> {error}
              </div>
            ) : predictions ? (
              <div className="space-y-4 mt-2">
                {predictions.drivers.slice(0, 3).map((d, i) => (
                  <div key={d.driver_code} className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className={`font-mono font-bold w-4 text-center ${i === 0 ? "text-primary" : "text-on-surface-variant"}`}>
                        {i + 1}
                      </span>
                      <div>
                        <span className="font-bold text-white font-mono">{d.driver_code}</span>
                        {d.full_name && <span className="text-xs text-on-surface-variant ml-2 font-space">{d.full_name}</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-xs font-mono text-on-surface-variant">{d.expected_final_points.toFixed(0)} pts</span>
                      <div className="w-24 h-1.5 bg-white/5 rounded-full overflow-hidden border border-white/5">
                        <div 
                          className="h-full bg-primary rounded-full" 
                          style={{ width: `${d.championship_probability * 100}%` }}
                        />
                      </div>
                      <span className="text-xs font-mono font-bold text-primary w-12 text-right">
                        {(d.championship_probability * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                ))}
                <div className="text-[10px] font-mono text-on-surface-variant/50 uppercase tracking-widest mt-2">
                  Based on {predictions.simulations_run.toLocaleString()} Monte Carlo simulations
                </div>
              </div>
            ) : null}
            <Link href="/predictions" className="text-xs text-on-surface-variant hover:text-white mt-6 inline-block font-mono font-bold uppercase tracking-wider">
              View full championship forecast &rarr;
            </Link>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="glass-card hover-float">
          <CardHeader>
            <CardTitle className="text-lg font-bold font-space flex items-center gap-2 text-white">
              <Sparkles className="h-5 w-5 text-primary" />
              Nexus AI
            </CardTitle>
            <CardDescription className="text-on-surface-variant text-xs font-mono uppercase tracking-wider">Ask F1 strategy, telemetry, and history questions</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-on-surface-variant leading-relaxed">
              Nexus AI uses RAG (Retrieval-Augmented Generation) to query the telemetry database directly. 
              Ask about tyre degradation, sector times, pit strategy, and more.
            </p>
            <Link href="/chat" className="inline-flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-widest text-primary hover:underline">
              <Sparkles className="w-4 h-4" />
              Start a conversation &rarr;
            </Link>
          </CardContent>
        </Card>

        <Card className="glass-card hover-float">
          <CardHeader>
            <CardTitle className="text-lg font-bold font-space flex items-center gap-2 text-white">
              <Flag className="h-5 w-5 text-primary" />
              Recent Races
            </CardTitle>
            <CardDescription className="text-on-surface-variant text-xs font-mono uppercase tracking-wider">Latest race results</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentRounds.length > 0 ? recentRounds.map(r => (
                <Link 
                  key={r.id} 
                  href={`/races/${r.season_year}/${r.round_number}`} 
                  className="flex items-center justify-between p-4 rounded-xl bg-white/5 border border-white/5 hover:border-primary/30 transition-all group"
                >
                  <div>
                    <div className="text-xs font-bold font-mono uppercase tracking-wider text-primary">Round {r.round_number}</div>
                    <div className="text-sm font-bold text-white font-space mt-1 group-hover:text-primary transition-colors">{r.name || 'TBC'}</div>
                  </div>
                  {r.race_date && (
                    <Badge className="font-mono text-[9px] uppercase tracking-wider bg-white/5 text-on-surface-variant border border-white/10">
                      {(() => {
                        try {
                          const parts = r.race_date.split('-');
                          if (parts.length === 3) {
                            const dateObj = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
                            return dateObj.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
                          }
                          return r.race_date;
                        } catch {
                          return r.race_date;
                        }
                      })()}
                    </Badge>
                  )}
                </Link>
              )) : (
                <div className="text-sm font-mono text-on-surface-variant">No race data loaded yet.</div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ActivityIcon(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  )
}
