"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { ChevronLeft, TrendingDown, Timer, Layers } from "lucide-react";
import Link from "next/link";

// Matches backend RaceAnalysisSchema
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
    return <div className="text-center py-20 text-red-400">Failed to load race analysis.</div>;
  }

  // Format degradation curves for Recharts
  const curveData: any[] = [];
  const curveDrivers = Object.keys(data.degradation_curves || {});

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

  // Compute most-used compound from tire stints
  const compoundCounts: Record<string, number> = {};
  for (const stint of data.tire_stints || []) {
    compoundCounts[stint.compound] = (compoundCounts[stint.compound] || 0) + stint.lap_count;
  }
  const mostUsedCompound = Object.entries(compoundCounts)
    .sort((a, b) => b[1] - a[1])[0]?.[0] || "N/A";

  const driverColors = ['#dc2626', '#3b82f6', '#f59e0b', '#10b981', '#8b5cf6'];

  // Tyre color helper
  const getTyreColor = (compound: string) => {
    switch (compound.toUpperCase()) {
      case 'SOFT': return 'text-red-400';
      case 'MEDIUM': return 'text-yellow-400';
      case 'HARD': return 'text-slate-200';
      case 'INTERMEDIATE': return 'text-green-400';
      case 'WET': return 'text-blue-400';
      default: return 'text-slate-400';
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto animate-in fade-in">
      <div>
        <Link href="/races" className="text-slate-400 hover:text-slate-200 inline-flex items-center gap-2 mb-4 text-sm transition-colors">
          <ChevronLeft className="w-4 h-4" /> Back to Calendar
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{data.round.name || `Round ${data.round.round_number}`}</h1>
            <p className="text-slate-400 mt-1">
              Round {data.round.round_number} • {data.round.season_year}
              {data.round.circuit && ` • ${data.round.circuit.name}`}
            </p>
          </div>
          {data.winner_code && (
            <Badge className="text-lg py-1 px-4">Winner: {data.winner_code}</Badge>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="glass">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
              <Timer className="w-4 h-4" /> Total Laps Recorded
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{(data.total_laps || 0).toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card className="glass">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
              <Layers className="w-4 h-4" /> Tyre Stints
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{data.tire_stints?.length || 0}</div>
          </CardContent>
        </Card>
        <Card className="glass border-red-900/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">Most Used Compound</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-3xl font-bold ${getTyreColor(mostUsedCompound)}`}>
              {mostUsedCompound}
            </div>
            <div className="text-xs text-slate-500 mt-1">
              {compoundCounts[mostUsedCompound] || 0} total laps on this compound
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tyre Strategy Timeline */}
      {data.tire_stints.length > 0 && (
        <Card className="glass">
          <CardHeader>
            <CardTitle>Tyre Strategy Timeline</CardTitle>
            <p className="text-sm text-slate-400">Each driver's tyre compound choices across the race.</p>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-[400px] overflow-y-auto pr-2">
              {(() => {
                // Group stints by driver
                const byDriver: Record<string, typeof data.tire_stints> = {};
                for (const stint of data.tire_stints) {
                  if (!byDriver[stint.driver_code]) byDriver[stint.driver_code] = [];
                  byDriver[stint.driver_code].push(stint);
                }
                const totalLaps = data.total_laps || 1;

                return Object.entries(byDriver).map(([driver, stints]) => (
                  <div key={driver} className="flex items-center gap-3">
                    <span className="font-mono text-xs text-slate-300 w-10 shrink-0">{driver}</span>
                    <div className="flex-1 flex h-6 rounded overflow-hidden border border-slate-700">
                      {stints.sort((a, b) => a.start_lap - b.start_lap).map((stint, i) => {
                        const widthPct = (stint.lap_count / totalLaps) * 100;
                        const bgColor = stint.compound.toUpperCase() === 'SOFT' ? 'bg-red-600'
                          : stint.compound.toUpperCase() === 'MEDIUM' ? 'bg-yellow-500'
                          : stint.compound.toUpperCase() === 'HARD' ? 'bg-slate-300'
                          : stint.compound.toUpperCase() === 'INTERMEDIATE' ? 'bg-green-500'
                          : stint.compound.toUpperCase() === 'WET' ? 'bg-blue-500'
                          : 'bg-slate-600';
                        return (
                          <div
                            key={i}
                            className={`${bgColor} flex items-center justify-center text-[10px] font-bold text-slate-950 border-r border-slate-900/30`}
                            style={{ width: `${widthPct}%`, minWidth: '2px' }}
                            title={`${stint.compound} (Laps ${stint.start_lap}-${stint.end_lap})`}
                          >
                            {widthPct > 10 ? stint.compound[0] : ''}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ));
              })()}
            </div>
            <div className="flex gap-4 mt-4 pt-3 border-t border-slate-800 text-xs text-slate-500">
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-600"></span> Soft</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-yellow-500"></span> Medium</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-slate-300"></span> Hard</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-green-500"></span> Inter</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-blue-500"></span> Wet</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Degradation Curves */}
      <Card className="glass">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingDown className="w-5 h-5 text-red-500" />
            Tyre Degradation Curves
          </CardTitle>
          <p className="text-sm text-slate-400">
            {curveDrivers.length > 0
              ? `Expected lap time dropoff (+seconds) vs tyre age for ${curveDrivers.join(', ')}.`
              : 'No degradation model data available for this race.'}
          </p>
        </CardHeader>
        <CardContent>
          {curveData.length > 0 ? (
            <div className="h-[400px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={curveData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis 
                    dataKey="age" 
                    stroke="#64748b" 
                    label={{ value: 'Tyre Age (Laps)', position: 'insideBottom', offset: -10, fill: '#64748b' }} 
                  />
                  <YAxis 
                    stroke="#64748b" 
                    label={{ value: '+ Seconds', angle: -90, position: 'insideLeft', fill: '#64748b' }} 
                  />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#020617', borderColor: '#1e293b', color: '#f8fafc' }}
                    itemStyle={{ color: '#f8fafc' }}
                    formatter={(value: any) => [typeof value === 'number' ? `+${value.toFixed(3)}s` : value, 'Degradation']}
                    labelFormatter={(label) => `Lap ${label}`}
                  />
                  <Legend wrapperStyle={{ paddingTop: '20px' }} />
                  {curveDrivers.map((driver, i) => (
                    <Line 
                      key={driver}
                      type="monotone" 
                      dataKey={driver} 
                      name={driver}
                      stroke={driverColors[i % driverColors.length]} 
                      strokeWidth={3}
                      dot={false}
                      activeDot={{ r: 6 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-slate-500">
              <p>Degradation model data not available for this race.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
