"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
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

        // Find the next or current race from the schedule
        if (roundsResult.status === "fulfilled") {
          const rounds = roundsResult.value;
          const now = new Date();
          // Find the closest upcoming race or one that is within 3 days
          const upcoming = rounds.find(r => {
            if (!r.race_date) return false;
            const raceDate = new Date(r.race_date);
            const diffDays = (raceDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
            return diffDays >= -1 && diffDays <= 3;
          });
          if (upcoming) {
            setNextRace(upcoming);
            isRaceWeekend = true; // It's a race weekend even if live timing isn't active yet
          } else {
            // No race this weekend, pick the true next one
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
    return <div className="flex justify-center py-20"><Spinner size="lg" /></div>;
  }

  if (!data) {
    return <div className="text-center py-20 text-red-400">Failed to load championship predictions.</div>;
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto animate-in fade-in">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <BarChart3 className="text-red-500 w-8 h-8" />
            Predictions &amp; Insights
          </h1>
          <p className="text-slate-400 mt-1">
            {mode === "race" && nextRace
              ? `Race weekend: ${nextRace.name || 'Grand Prix'} — Round ${nextRace.round_number}`
              : `${CURRENT_YEAR} Championship Forecast`
            }
          </p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => setMode("season")}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              mode === "season" ? "bg-red-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            }`}
          >
            Season
          </button>
          <button
            onClick={() => setMode("race")}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              mode === "race" ? "bg-red-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
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
        <div className="bg-slate-950 border border-slate-800 p-3 rounded-md shadow-xl">
          <p className="font-bold text-slate-100">{label}</p>
          <p className="text-red-400 font-medium">Win Probability: {payload[0].value.toFixed(1)}%</p>
          <p className="text-slate-400">Expected Points: {payload[0].payload.points.toFixed(0)}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Card className="glass lg:col-span-2">
        <CardHeader>
          <CardTitle>Title Contenders</CardTitle>
          <CardDescription>Win probability for the top 10 drivers</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[400px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
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
                <Tooltip content={<CustomTooltip />} cursor={{ fill: '#1e293b', opacity: 0.4 }} />
                <Bar dataKey="probability" radius={[4, 4, 0, 0]}>
                  {chartData.map((_entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={index === 0 ? '#ef4444' : index === 1 ? '#3b82f6' : '#64748b'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-6">
        <Card className="glass">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
              <TrendingUp className="w-4 h-4" /> Standings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {data.drivers.slice(0, 5).map((d, i) => (
                <div key={d.driver_code} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`w-5 text-center font-bold ${i === 0 ? 'text-amber-500' : 'text-slate-500'}`}>{i + 1}</span>
                    <div>
                      <span className="font-semibold">{d.driver_code}</span>
                      {d.team && <span className="text-xs text-slate-500 ml-2">{d.team}</span>}
                    </div>
                  </div>
                  <span className="font-mono text-slate-300">{d.expected_final_points.toFixed(0)} pts</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="glass bg-slate-900/40">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <HelpCircle className="w-4 h-4 text-slate-400" /> Methodology
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-slate-400 leading-relaxed">
              Probabilities are generated using a Monte Carlo simulation ({data.simulations_run.toLocaleString()} iterations) across all remaining races.
              Base performance is estimated using XGBoost on historical lap times, tyre degradation curves, and driver
              consistency metrics.
            </p>
          </CardContent>
        </Card>
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
  // Sort by current points (best indicator for race form)
  const topDrivers = [...drivers].sort((a, b) => b.current_points - a.current_points).slice(0, 10);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Race weekend hero card */}
      <Card className="glass lg:col-span-2 border-red-900/30">
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            <Zap className="w-6 h-6 text-amber-500" />
            {nextRace?.name || "Race Weekend"}
          </CardTitle>
          <CardDescription className="flex items-center gap-3 mt-2">
            {nextRace?.circuit?.name && (
              <span>{nextRace.circuit.name} — {nextRace.circuit.city}, {nextRace.circuit.country}</span>
            )}
            {liveStatus?.active && (
              <Badge variant="destructive" className="animate-pulse">LIVE</Badge>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
                <div className="text-xs text-slate-400 mb-1">Round</div>
                <div className="text-2xl font-bold">{nextRace?.round_number || "—"}</div>
              </div>
              <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
                <div className="text-xs text-slate-400 mb-1">Race Date</div>
                <div className="text-2xl font-bold">
                  {nextRace?.race_date
                    ? new Date(nextRace.race_date).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
                    : "—"}
                </div>
              </div>
              <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
                <div className="text-xs text-slate-400 mb-1">Status</div>
                <div className="text-2xl font-bold">
                  {liveStatus?.active ? (
                    <span className="text-red-500 flex items-center gap-2">
                      <Activity className="w-5 h-5 animate-pulse" /> Live
                    </span>
                  ) : (
                    <span className="text-amber-400">Practice</span>
                  )}
                </div>
              </div>
            </div>

            <h3 className="text-sm font-semibold text-slate-300 mt-6">Race Form — Top Contenders</h3>
            <div className="space-y-3">
              {topDrivers.map((d, i) => {
                const maxPts = topDrivers[0].current_points || 1;
                return (
                  <div key={d.driver_code} className="flex items-center gap-4">
                    <span className={`w-5 text-center font-bold text-sm ${
                      i === 0 ? 'text-amber-500' : i === 1 ? 'text-slate-300' : i === 2 ? 'text-amber-700' : 'text-slate-600'
                    }`}>{i + 1}</span>
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <div>
                          <span className="font-semibold text-sm">{d.driver_code}</span>
                          {d.team && <span className="text-xs text-slate-500 ml-2">{d.team}</span>}
                        </div>
                        <span className="text-xs font-mono text-slate-400">{d.current_points} pts</span>
                      </div>
                      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${(d.current_points / maxPts) * 100}%`,
                            backgroundColor: i === 0 ? '#ef4444' : i === 1 ? '#3b82f6' : '#64748b',
                          }}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Sidebar insights */}
      <div className="space-y-6">
        <Card className="glass">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
              <Timer className="w-4 h-4" /> Race Weekend Insights
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="p-3 rounded-md bg-slate-800/30 border border-slate-800">
                <div className="text-xs text-slate-500 mb-1">Championship Leader</div>
                <div className="font-bold text-lg">{topDrivers[0]?.driver_code || "—"}</div>
                <div className="text-xs text-slate-400">{topDrivers[0]?.full_name} • {topDrivers[0]?.current_points} pts</div>
              </div>
              <div className="p-3 rounded-md bg-slate-800/30 border border-slate-800">
                <div className="text-xs text-slate-500 mb-1">Points Gap (P1 → P2)</div>
                <div className="font-bold text-lg text-red-400">
                  {topDrivers.length >= 2
                    ? `${(topDrivers[0].current_points - topDrivers[1].current_points).toFixed(0)} pts`
                    : "—"}
                </div>
              </div>
              <div className="p-3 rounded-md bg-slate-800/30 border border-slate-800">
                <div className="text-xs text-slate-500 mb-1">Closest Battle</div>
                <div className="font-bold text-sm">
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
                      return <span>{pair[0]} vs {pair[1]} <span className="text-slate-500">({minGap} pts)</span></span>;
                    })()
                  ) : "—"}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glass bg-amber-950/10 border-amber-900/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2 text-amber-400">
              <Zap className="w-4 h-4" /> Strategy Preview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-slate-400 leading-relaxed">
              Strategy predictions will be available once practice session data is processed.
              Check the race detail page after FP1/FP2 for tyre degradation analysis and optimal pit windows.
            </p>
            {nextRace && (
              <a
                href={`/races/${nextRace.season_year}/${nextRace.round_number}`}
                className="text-xs text-red-500 hover:text-red-400 mt-3 inline-block font-medium"
              >
                View race analysis &rarr;
              </a>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
