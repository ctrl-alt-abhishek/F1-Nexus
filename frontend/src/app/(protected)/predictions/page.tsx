"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Spinner } from "@/components/ui/spinner";
import { Skeleton } from "@/components/ui/skeleton";
import { BarChart3, TrendingUp, HelpCircle, Zap, Timer, Activity } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const CURRENT_YEAR = new Date().getFullYear();

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

interface LiveStatus {
  active: boolean;
  session_type: string | null;
  current_lap: number;
}

interface RoundInfo {
  id: number;
  season_year: number;
  round_number: number;
  name: string | null;
  race_date: string | null;
  circuit: { name: string; country: string | null; city: string | null } | null;
}

export default function PredictionsPage() {
  const [data, setData] = useState<ChampionshipPrediction | null>(null);
  const [liveStatus, setLiveStatus] = useState<LiveStatus | null>(null);
  const [nextRace, setNextRace] = useState<RoundInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<"season" | "race">("season");

  useEffect(() => {
    async function loadAll() {
      try {
        const [predResult, liveResult, roundsResult] = await Promise.allSettled([
          fetchApi<ChampionshipPrediction>(`/predictions/championship/${CURRENT_YEAR}`),
          fetchApi<LiveStatus>("/live/status"),
          fetchApi<RoundInfo[]>(`/races/${CURRENT_YEAR}`),
        ]);

        if (predResult.status === "fulfilled") setData(predResult.value);

        let isRaceWeekend = false;
        if (liveResult.status === "fulfilled") {
          setLiveStatus(liveResult.value);
          isRaceWeekend = liveResult.value.active;
        }

        if (roundsResult.status === "fulfilled") {
          const rounds = roundsResult.value;
          const now = new Date();
          const upcoming = rounds.find(r => {
            if (!r.race_date) return false;
            const raceDate = new Date(r.race_date);
            const diffDays = (raceDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
            return diffDays >= -1 && diffDays <= 3;
          });
          if (upcoming) {
            setNextRace(upcoming);
            isRaceWeekend = true;
          } else {
            const next = rounds.find(r => r.race_date && new Date(r.race_date) > now);
            if (next) setNextRace(next);
          }
        }

        setMode(isRaceWeekend ? "race" : "season");
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadAll();
  }, []);

  if (loading) {
    return (
      <div className="space-y-12 max-w-7xl mx-auto animate-in fade-in duration-500">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div>
            <Skeleton className="h-12 w-64 mb-3" />
            <Skeleton className="h-6 w-96" />
          </div>
          <div className="flex gap-1.5">
            <Skeleton className="h-10 w-24" />
            <Skeleton className="h-10 w-32" />
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <Skeleton className="h-[400px] lg:col-span-8" />
          <div className="lg:col-span-4 space-y-6">
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return <div className="text-center py-20 text-primary font-mono uppercase">Failed to load championship predictions.</div>;
  }

  return (
    <div className="space-y-12 max-w-7xl mx-auto animate-in fade-in duration-500">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <h1 className="text-5xl font-bold text-on-surface tracking-tight font-space flex items-center gap-3">
            <BarChart3 className="text-primary w-10 h-10" />
            Predictions &amp; Insights
          </h1>
          <p className="text-on-surface-variant mt-3 text-lg font-space">
            {mode === "race" && nextRace
              ? `Race weekend forecast: ${nextRace.name || 'Grand Prix'} • Round ${nextRace.round_number}`
              : `${CURRENT_YEAR} Championship Monte Carlo Forecast`
            }
          </p>
        </div>

        <div className="flex gap-1.5">
          <button
            onClick={() => setMode("season")}
            className={`px-5 py-3 border text-[10px] font-bold rounded-xl transition-all font-mono uppercase tracking-widest ${
              mode === "season"
                ? "bg-primary border-primary text-white font-bold"
                : "bg-white/5 border-white/10 text-on-surface-variant hover:border-primary/50 hover:text-white"
            }`}
          >
            Season
          </button>
          <button
            onClick={() => setMode("race")}
            className={`px-5 py-3 border text-[10px] font-bold rounded-xl transition-all font-mono uppercase tracking-widest ${
              mode === "race"
                ? "bg-primary border-primary text-white font-bold"
                : "bg-white/5 border-white/10 text-on-surface-variant hover:border-primary/50 hover:text-white"
            }`}
          >
            Race Weekend
          </button>
        </div>
      </div>

      {mode === "race" ? (
        <RaceWeekendView nextRace={nextRace} liveStatus={liveStatus} drivers={data.drivers} />
      ) : (
        <SeasonView data={data} />
      )}
    </div>
  );
}

// ── Season Championship View ──────────────────────────────────────────────────
function SeasonView({ data }: { data: ChampionshipPrediction }) {
  const chartData = data.drivers.slice(0, 10).map((d) => ({
    name: d.driver_code,
    probability: d.championship_probability * 100,
    points: d.expected_final_points,
  }));

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="glass-card p-4 border border-white/10 shadow-2xl font-mono text-xs">
          <p className="font-bold text-white mb-2 font-space text-sm">{label}</p>
          <p className="text-primary font-bold">WIN PROBABILITY: {payload[0].value.toFixed(1)}%</p>
          <p className="text-on-surface-variant">EXPECTED POINTS: {payload[0].payload.points.toFixed(0)}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Chart Panel */}
      <div className="glass-card p-8 lg:col-span-8 flex flex-col justify-between">
        <div className="mb-6">
          <h2 className="text-2xl font-bold font-space text-white">Title Contenders</h2>
          <p className="text-sm text-on-surface-variant mt-1">Win probability for the top 10 grid drivers based on simulations</p>
        </div>
        <div className="h-[400px] w-full mt-4 font-mono text-xs">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 20, right: 10, left: -10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              <XAxis
                dataKey="name"
                stroke="#64748b"
                tick={{ fill: '#94a3b8', fontWeight: 600 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                stroke="#64748b"
                tickFormatter={(val) => `${val}%`}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
              <Bar dataKey="probability" radius={[8, 8, 0, 0]}>
                {chartData.map((_entry: any, index: number) => (
                  <Cell key={`cell-${index}`} fill={index === 0 ? '#b91a24' : index === 1 ? '#3b82f6' : '#64748b'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Side Standings & Info */}
      <div className="lg:col-span-4 space-y-6">
        <div className="glass-card p-8">
          <div className="flex items-center gap-3 mb-6">
            <TrendingUp className="w-5 h-5 text-primary" />
            <h3 className="text-lg font-bold font-space text-white">Forecast Standings</h3>
          </div>
          <div className="space-y-4">
            {data.drivers.slice(0, 6).map((d, i) => (
              <div key={d.driver_code} className="flex items-center justify-between pb-3 border-b border-white/5 last:border-0 last:pb-0">
                <div className="flex items-center gap-3">
                  <span className={`w-5 text-center font-mono font-bold text-xs ${i === 0 ? 'text-primary' : 'text-on-surface-variant'}`}>
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <div>
                    <span className="font-bold text-white font-mono">{d.driver_code}</span>
                    {d.team && <span className="text-xs text-on-surface-variant ml-2 font-space">{d.team}</span>}
                  </div>
                </div>
                <span className="font-mono text-sm text-primary font-bold">{d.expected_final_points.toFixed(0)} pts</span>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card p-8 bg-white/[0.01]">
          <div className="flex items-center gap-3 mb-4">
            <HelpCircle className="w-5 h-5 text-on-surface-variant/60" />
            <h3 className="text-sm font-bold font-space uppercase text-on-surface-variant/80 tracking-wider">Methodology</h3>
          </div>
          <p className="text-xs text-on-surface-variant leading-relaxed font-sans">
            Probabilities are generated using a Monte Carlo simulation ({data.simulations_run.toLocaleString()} iterations) across all remaining races. 
            Base performance is estimated using XGBoost models trained on lap telemetry, historical degradation gradients, and driver performance trends.
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Race Weekend View ─────────────────────────────────────────────────────────
function RaceWeekendView({
  nextRace,
  liveStatus,
  drivers,
}: {
  nextRace: RoundInfo | null;
  liveStatus: LiveStatus | null;
  drivers: DriverChampPred[];
}) {
  const topDrivers = [...drivers].sort((a, b) => b.current_points - a.current_points).slice(0, 8);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Race Hero Card */}
      <div className="glass-card p-8 lg:col-span-8 border-primary/20 flex flex-col justify-between">
        <div>
          <div className="flex justify-between items-start mb-6">
            <div>
              <span className="text-[10px] font-bold text-primary uppercase tracking-[0.2em] font-mono">Race Forecast</span>
              <h2 className="text-3xl font-bold leading-tight mt-1 font-space text-white">{nextRace?.name || "Grand Prix"}</h2>
              <p className="text-sm text-on-surface-variant mt-1 font-space">
                {nextRace?.circuit?.name && `${nextRace.circuit.name} — ${nextRace.circuit.city}, ${nextRace.circuit.country}`}
              </p>
            </div>
            {liveStatus?.active ? (
              <span className="px-3 py-1 bg-primary/20 text-primary border border-primary/30 rounded-full text-[10px] font-bold font-mono tracking-widest uppercase animate-pulse">LIVE</span>
            ) : (
              <span className="px-3 py-1 bg-white/5 text-on-surface-variant border border-white/10 rounded-full text-[10px] font-bold font-mono tracking-widest uppercase">UPCOMING</span>
            )}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
            <div className="p-4 rounded-xl bg-white/5 border border-white/5">
              <span className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-wider font-mono">Round</span>
              <span className="text-xl font-bold text-white mt-1 block font-space">{nextRace?.round_number || "—"}</span>
            </div>
            <div className="p-4 rounded-xl bg-white/5 border border-white/5">
              <span className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-wider font-mono">Race Date</span>
              <span className="text-xl font-bold text-white mt-1 block font-space">
                {nextRace?.race_date
                  ? (() => {
                      const parts = nextRace.race_date.split('-');
                      if (parts.length === 3) {
                        const dateObj = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
                        return dateObj.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
                      }
                      return nextRace.race_date;
                    })()
                  : "—"}
              </span>
            </div>
            <div className="p-4 rounded-xl bg-white/5 border border-white/5 col-span-2 md:col-span-1">
              <span className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-wider font-mono">Status</span>
              <span className="text-xl font-bold text-white mt-1 block font-space flex items-center gap-2">
                {liveStatus?.active ? (
                  <>
                    <Activity className="w-5 h-5 text-primary animate-pulse" /> Live Now
                  </>
                ) : (
                  "Waiting"
                )}
              </span>
            </div>
          </div>

          <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono mb-4">Grid Pace Index</h3>
          <div className="space-y-4">
            {topDrivers.map((d, i) => {
              const maxPts = topDrivers[0].current_points || 1;
              return (
                <div key={d.driver_code} className="flex items-center gap-4">
                  <span className="w-5 text-center font-mono font-bold text-xs text-on-surface-variant">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1.5">
                      <div>
                        <span className="font-bold font-mono text-sm text-white">{d.driver_code}</span>
                        {d.team && <span className="text-xs text-on-surface-variant ml-2 font-space">{d.team}</span>}
                      </div>
                      <span className="text-xs font-mono text-primary font-bold">{d.current_points} pts</span>
                    </div>
                    <div className="h-1.5 bg-white/5 border border-white/5 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${(d.current_points / maxPts) * 100}%`,
                          backgroundColor: i === 0 ? '#b91a24' : i === 1 ? '#3b82f6' : '#64748b',
                        }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Sidebar Insights */}
      <div className="lg:col-span-4 space-y-6">
        <div className="glass-card p-8">
          <div className="flex items-center gap-3 mb-6">
            <Timer className="w-5 h-5 text-primary" />
            <h3 className="text-lg font-bold font-space text-white">Grid Battles</h3>
          </div>
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-white/5 border border-white/5">
              <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider font-mono">Championship Leader</span>
              <span className="font-bold text-lg text-white mt-1 block font-mono">{topDrivers[0]?.driver_code || "—"}</span>
              <span className="text-[10px] text-on-surface-variant mt-0.5 block font-space">{topDrivers[0]?.full_name} • {topDrivers[0]?.current_points} pts</span>
            </div>
            <div className="p-4 rounded-xl bg-white/5 border border-white/5">
              <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider font-mono">Points Gap (P1 → P2)</span>
              <span className="font-bold text-lg text-primary mt-1 block font-mono">
                {topDrivers.length >= 2
                  ? `${(topDrivers[0].current_points - topDrivers[1].current_points).toFixed(0)} pts`
                  : "—"}
              </span>
            </div>
            <div className="p-4 rounded-xl bg-white/5 border border-white/5">
              <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider font-mono">Closest Rivalry</span>
              <span className="font-bold text-xs text-white mt-1 block font-sans">
                {topDrivers.length >= 2 ? (
                  (() => {
                    let minGap = Infinity;
                    let pair = ["", ""];
                    for (let i = 0; i < Math.min(topDrivers.length - 1, 5); i++) {
                      const gap = topDrivers[i].current_points - topDrivers[i + 1].current_points;
                      if (gap < minGap) {
                        minGap = gap;
                        pair = [topDrivers[i].driver_code, topDrivers[i + 1].driver_code];
                      }
                    }
                    return <span>{pair[0]} vs {pair[1]} <span className="text-primary font-mono font-bold">({minGap} pts)</span></span>;
                  })()
                ) : "—"}
              </span>
            </div>
          </div>
        </div>

        <div className="glass-card p-8 bg-primary/[0.02] border-primary/20">
          <div className="flex items-center gap-3 mb-4">
            <Zap className="w-5 h-5 text-primary" />
            <h3 className="text-sm font-bold font-space uppercase text-white tracking-wider">Strategy Preview</h3>
          </div>
          <p className="text-xs text-on-surface-variant leading-relaxed font-sans">
            {liveStatus?.active 
              ? "Live ML strategy models are currently evaluating telemetry streams for stint predictions."
              : "Strategy predictions are currently idle. Live predictions will execute once the next session begins."}
          </p>
          {nextRace && (
            <a
              href={`/races/${nextRace.season_year}/${nextRace.round_number}`}
              className="text-xs font-mono font-bold uppercase tracking-wider text-primary hover:underline mt-4 inline-block"
            >
              Race Analysis page &rarr;
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
