"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Spinner } from "@/components/ui/spinner";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { ChevronLeft, TrendingDown, Timer, Layers } from "lucide-react";
import Link from "next/link";

interface RaceAnalysis {
  round: {
    id: number;
    season_year: number;
    round_number: number;
    name: string | null;
    race_date: string | null;
    circuit: {
      id: number;
      name: string;
      country: string | null;
      city: string | null;
      track_length_km: number | null;
      lap_record_s: number | null;
    } | null;
  };
  winner_code: string | null;
  total_laps: number;
  tire_stints: Array<{
    driver_code: string;
    stint: number;
    compound: string;
    start_lap: number;
    end_lap: number;
    lap_count: number;
  }>;
  degradation_curves: Record<string, Array<{
    tire_age: number;
    predicted_lap_time_s: number;
    actual_lap_time_s: number | null;
  }>>;
}

export default function RaceDetailPage({ params }: { params: { year: string, round: string } }) {
  const [data, setData] = useState<RaceAnalysis | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadAnalysis() {
      try {
        const result = await fetchApi<RaceAnalysis>(`/races/${params.year}/${params.round}`);
        setData(result);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadAnalysis();
  }, [params.year, params.round]);

  if (loading) {
    return <div className="flex justify-center py-20"><Spinner size="lg" /></div>;
  }

  if (!data) {
    return <div className="text-center py-20 text-primary font-mono uppercase">Failed to load race analysis.</div>;
  }

  const curveDrivers = Object.keys(data.degradation_curves || {});
  const curveData: any[] = [];

  if (curveDrivers.length > 0) {
    const maxAge = Math.max(
      ...curveDrivers.map(d => data.degradation_curves[d]?.length || 0)
    );

    if (maxAge > 0 && maxAge !== -Infinity) {
      for (let age = 1; age <= maxAge; age++) {
        const point: any = { age };
        for (const driver of curveDrivers) {
          const curve = data.degradation_curves[driver];
          const lapData = curve.find(c => c.tire_age === age);
          if (lapData) {
            const baseTime = curve[0]?.predicted_lap_time_s || 0;
            if (baseTime > 0) {
              point[driver] = +(lapData.predicted_lap_time_s - baseTime).toFixed(3);
            }
          }
        }
        curveData.push(point);
      }
    }
  }

  const compoundCounts: Record<string, number> = {};
  for (const stint of data.tire_stints || []) {
    compoundCounts[stint.compound] = (compoundCounts[stint.compound] || 0) + stint.lap_count;
  }
  const mostUsedCompound = Object.entries(compoundCounts)
    .sort((a, b) => b[1] - a[1])[0]?.[0] || "N/A";

  const driverColors = ['#b91a24', '#3b82f6', '#eab308', '#10b981', '#8b5cf6', '#ec4899', '#f97316'];

  const getTyreColorClass = (compound: string) => {
    switch (compound.toUpperCase()) {
      case 'SOFT': return 'text-primary';
      case 'MEDIUM': return 'text-yellow-500';
      case 'HARD': return 'text-white';
      case 'INTERMEDIATE': return 'text-green-500';
      case 'WET': return 'text-blue-500';
      default: return 'text-slate-400';
    }
  };

  const getStintBgColor = (compound: string) => {
    switch (compound.toUpperCase()) {
      case 'SOFT': return 'bg-primary';
      case 'MEDIUM': return 'bg-yellow-500';
      case 'HARD': return 'bg-white';
      case 'INTERMEDIATE': return 'bg-green-500';
      case 'WET': return 'bg-blue-500';
      default: return 'bg-slate-600';
    }
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="glass-card p-4 border border-white/10 shadow-2xl font-mono text-xs">
          <p className="font-bold text-white mb-2 font-space text-sm">TYRE AGE: {label} LAPS</p>
          <div className="space-y-1">
            {payload.map((p: any, i: number) => (
              <p key={i} style={{ color: p.color }} className="font-bold uppercase tracking-wider">
                {p.name}: +{p.value.toFixed(3)}s
              </p>
            ))}
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-12 max-w-7xl mx-auto animate-in fade-in duration-500">
      {/* Navigation and Title */}
      <div>
        <Link href="/races" className="text-on-surface-variant/40 hover:text-primary inline-flex items-center gap-3 transition-colors group cursor-pointer mb-6">
          <div className="w-4 h-[1px] bg-current transition-all group-hover:w-6 group-hover:bg-primary"></div>
          <span className="font-mono text-[10px] uppercase tracking-[0.2em]">Back to Calendar</span>
        </Link>
        
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div>
            <h1 className="text-5xl font-bold tracking-tight text-white font-space">
              {data.round.name || `Round ${data.round.round_number}`}
            </h1>
            <p className="text-on-surface-variant mt-3 text-lg font-space">
              Round {data.round.round_number} • {data.round.season_year}
              {data.round.circuit && ` • ${data.round.circuit.name}`}
            </p>
          </div>
          {data.winner_code && (
            <div className="px-5 py-3.5 bg-primary/10 border border-primary/20 text-primary font-mono text-xs uppercase font-bold tracking-widest rounded-xl">
              WINNER: {data.winner_code}
            </div>
          )}
        </div>
      </div>

      {/* Highlights Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-card p-8 flex flex-col justify-between h-40">
          <span className="text-[10px] font-bold text-on-surface-variant/60 uppercase font-mono tracking-widest flex items-center gap-2">
            <Timer className="w-4.5 h-4.5 text-primary" /> Total Laps
          </span>
          <span className="text-5xl font-bold font-space leading-none text-white">{(data.total_laps || 0).toLocaleString()}</span>
        </div>
        <div className="glass-card p-8 flex flex-col justify-between h-40">
          <span className="text-[10px] font-bold text-on-surface-variant/60 uppercase font-mono tracking-widest flex items-center gap-2">
            <Layers className="w-4.5 h-4.5 text-primary" /> Tyre Stints
          </span>
          <span className="text-5xl font-bold font-space leading-none text-white">{data.tire_stints?.length || 0}</span>
        </div>
        <div className="glass-card p-8 flex flex-col justify-between h-40 border-primary/20">
          <span className="text-[10px] font-bold text-on-surface-variant/60 uppercase font-mono tracking-widest">Most Used Compound</span>
          <span className={`text-4xl font-extrabold font-space leading-none ${getTyreColorClass(mostUsedCompound)}`}>
            {mostUsedCompound}
          </span>
        </div>
      </div>

      {/* Tyre Strategy Timeline */}
      {data.tire_stints.length > 0 && (
        <div className="glass-card p-8 border border-white/5">
          <div className="mb-6">
            <h3 className="text-2xl font-bold text-white font-space">Strategy Timeline</h3>
            <p className="text-sm text-on-surface-variant mt-1">Horizontal layout of stints mapped across the round duration.</p>
          </div>

          <div className="space-y-3 max-h-[350px] overflow-y-auto pr-2 custom-scrollbar">
            {(() => {
              const byDriver: Record<string, typeof data.tire_stints> = {};
              for (const stint of data.tire_stints) {
                if (!byDriver[stint.driver_code]) byDriver[stint.driver_code] = [];
                byDriver[stint.driver_code].push(stint);
              }
              const totalLaps = data.total_laps || 1;

              return Object.entries(byDriver).map(([driver, stints]) => (
                <div key={driver} className="flex items-center gap-4">
                  <span className="font-mono text-xs font-bold text-white w-10 shrink-0 select-none">{driver}</span>
                  <div className="flex-1 flex h-7 rounded-lg overflow-hidden border border-white/5 bg-white/[0.02]">
                    {stints.sort((a, b) => a.start_lap - b.start_lap).map((stint, i) => {
                      const widthPct = (stint.lap_count / totalLaps) * 100;
                      return (
                        <div
                          key={i}
                          className={`${getStintBgColor(stint.compound)} flex items-center justify-center text-[10px] font-bold text-black border-r border-black/10 select-none cursor-help`}
                          style={{ width: `${widthPct}%`, minWidth: '3px' }}
                          title={`${stint.compound} (Laps ${stint.start_lap}-${stint.end_lap}) • ${stint.lap_count}L`}
                        >
                          {widthPct > 8 ? stint.compound[0] : ''}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ));
            })()}
          </div>
          
          <div className="flex flex-wrap gap-4 mt-6 pt-4 border-t border-white/5 text-[10px] font-mono font-bold uppercase tracking-wider text-on-surface-variant/80">
            <span className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-primary"></span> Soft</span>
            <span className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-yellow-500"></span> Medium</span>
            <span className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-white"></span> Hard</span>
            <span className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-green-500"></span> Inter</span>
            <span className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-blue-500"></span> Wet</span>
          </div>
        </div>
      )}

      {/* Degradation Curves Chart */}
      <div className="glass-card p-8 border border-white/5">
        <div className="mb-6">
          <h3 className="text-2xl font-bold text-white font-space flex items-center gap-3">
            <TrendingDown className="w-6 h-6 text-primary" />
            Tyre Degradation Curves
          </h3>
          <p className="text-sm text-on-surface-variant mt-1 font-space">
            {curveDrivers.length > 0
              ? `Estimated lap time offset (+seconds) relative to tire age for ${curveDrivers.join(', ')}.`
              : 'No degradation model curves computed for this round.'}
          </p>
        </div>

        {curveData.length > 0 ? (
          <div className="h-[400px] w-full font-mono text-xs mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={curveData} margin={{ top: 10, right: 10, left: -20, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis 
                  dataKey="age" 
                  stroke="#64748b" 
                  tickLine={false}
                  tick={{ fill: '#94a3b8' }}
                />
                <YAxis 
                  stroke="#64748b" 
                  tickFormatter={(v) => `+${v.toFixed(1)}s`}
                  tickLine={false}
                  tick={{ fill: '#94a3b8' }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ paddingTop: '20px', fontFamily: 'Space Grotesk', fontSize: '12px' }} />
                {curveDrivers.map((driver, i) => (
                  <Line 
                    key={driver}
                    type="monotone" 
                    dataKey={driver} 
                    name={driver}
                    stroke={driverColors[i % driverColors.length]} 
                    strokeWidth={3}
                    dot={false}
                    activeDot={{ r: 5, stroke: '#000000', strokeWidth: 2 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-[200px] flex items-center justify-center font-mono text-xs uppercase tracking-wider text-on-surface-variant/50">
            No degradation curves mapped for this round.
          </div>
        )}
      </div>
    </div>
  );
}
