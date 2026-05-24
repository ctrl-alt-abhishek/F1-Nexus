"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { ChevronLeft, Trophy, Target, AlertCircle, Users } from "lucide-react";
import Link from "next/link";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip } from 'recharts';

// Matches backend DriverProfileSchema
interface DriverProfile {
  driver: {
    code: string;
    full_name: string | null;
    nationality: string | null;
    dob: string | null;
    team: string | null;
    car_number: number | null;
  };
  career_stats: {
    races: number;
    wins: number;
    podiums: number;
    poles: number;
    points_total: number;
    seasons: number[];
  };
}

export default function DriverDetailPage({ params }: { params: { code: string } }) {
  const [data, setData] = useState<DriverProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadDriver() {
      try {
        const result = await fetchApi<DriverProfile>(`/drivers/${params.code}`);
        setData(result);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadDriver();
  }, [params.code]);

  if (loading) {
    return <div className="flex justify-center py-20"><Spinner size="lg" /></div>;
  }

  if (!data) {
    return <div className="text-center py-20 text-red-400">Failed to load driver profile.</div>;
  }

  // Try to fetch style features (may 404 if not trained)
  // For now we won't block the page on it — radar will show empty state

  return (
    <div className="space-y-6 max-w-5xl mx-auto animate-in fade-in">
      <div>
        <Link href="/drivers" className="text-slate-400 hover:text-slate-200 inline-flex items-center gap-2 mb-4 text-sm transition-colors">
          <ChevronLeft className="w-4 h-4" /> Back to Grid
        </Link>
        <div className="flex items-end gap-6">
          <div className="text-8xl font-black italic text-slate-800 leading-none">
            {data.driver.car_number || "00"}
          </div>
          <div className="pb-2">
            <h1 className="text-4xl font-bold tracking-tight">{data.driver.full_name}</h1>
            <p className="text-xl text-red-500 font-medium mt-1">{data.driver.team || "Free Agent"}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="glass">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
              <Trophy className="w-4 h-4" /> Career Wins
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold">{data.career_stats.wins}</div>
          </CardContent>
        </Card>
        <Card className="glass">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
              <Target className="w-4 h-4" /> Career Points
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold">{data.career_stats.points_total.toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card className="glass">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
              <Users className="w-4 h-4" /> Races Started
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold">{data.career_stats.races}</div>
          </CardContent>
        </Card>
        <Card className="glass border-red-900/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">Podiums</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold text-red-500">{data.career_stats.podiums}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="glass">
          <CardHeader>
            <CardTitle>Career Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 rounded-md bg-slate-800/30 border border-slate-800">
                <span className="text-sm text-slate-400">Pole Positions</span>
                <span className="font-bold text-slate-200">{data.career_stats.poles}</span>
              </div>
              <div className="flex items-center justify-between p-3 rounded-md bg-slate-800/30 border border-slate-800">
                <span className="text-sm text-slate-400">Win Rate</span>
                <span className="font-bold text-slate-200">
                  {data.career_stats.races > 0
                    ? `${((data.career_stats.wins / data.career_stats.races) * 100).toFixed(1)}%`
                    : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between p-3 rounded-md bg-slate-800/30 border border-slate-800">
                <span className="text-sm text-slate-400">Podium Rate</span>
                <span className="font-bold text-slate-200">
                  {data.career_stats.races > 0
                    ? `${((data.career_stats.podiums / data.career_stats.races) * 100).toFixed(1)}%`
                    : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between p-3 rounded-md bg-slate-800/30 border border-slate-800">
                <span className="text-sm text-slate-400">Seasons Active</span>
                <span className="font-bold text-slate-200">{data.career_stats.seasons.length}</span>
              </div>
              <div className="flex items-center justify-between p-3 rounded-md bg-slate-800/30 border border-slate-800">
                <span className="text-sm text-slate-400">Nationality</span>
                <span className="font-bold text-slate-200">{data.driver.nationality || '—'}</span>
              </div>
              {data.driver.dob && (
                <div className="flex items-center justify-between p-3 rounded-md bg-slate-800/30 border border-slate-800">
                  <span className="text-sm text-slate-400">Date of Birth</span>
                  <span className="font-bold text-slate-200">
                    {new Date(data.driver.dob).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="glass">
          <CardHeader>
            <CardTitle>Season History</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {data.career_stats.seasons.map(season => (
                <Link
                  key={season}
                  href={`/races/${season}`}
                  className="px-3 py-1.5 bg-slate-800 text-slate-300 rounded-md border border-slate-700 text-sm font-mono hover:bg-slate-700 hover:text-red-400 transition-colors"
                >
                  {season}
                </Link>
              ))}
            </div>
            {data.career_stats.seasons.length === 0 && (
              <div className="text-slate-500 text-center py-10">No season data available.</div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
