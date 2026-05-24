"use client";

import { useEffect, useState } from "react";
import { liveTimingClient } from "@/lib/websocket";
import { fetchApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, Radio, AlertCircle, Calendar, MapPin, Clock, Trophy } from "lucide-react";

interface DriverUpdate {
  code: string;
  position: number;
  gap_to_leader: number;
  compound: string | null;
  tyre_life: number;
  predicted_stint_end: number | null;
  last_lap_s: number | null;
  sector1_s: number | null;
  sector2_s: number | null;
  sector3_s: number | null;
  drs: boolean;
  pitting: boolean;
}

interface NextRace {
  name: string;
  location?: string;
  country?: string;
  date?: string;
  time?: string;
  session_type?: string;
  round?: number;
}

interface LiveState {
  active: boolean;
  session_type?: string;
  current_lap?: number;
  timestamp?: string;
  drivers?: DriverUpdate[];
  race_name?: string | null;
  location?: string | null;
  country?: string | null;
  next_race?: NextRace | null;
}

export default function LivePage() {
  const [state, setState] = useState<LiveState>({ active: false });
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    // 1. Fetch initial status from REST API
    async function loadStatus() {
      try {
        const data = await fetchApi<LiveState>("/live/status");
        setState(data);
      } catch (err) {
        console.error("Failed to load live status via REST API:", err);
      }
    }
    loadStatus();

    // 2. Connect to WebSocket
    liveTimingClient.connect();

    // Immediately set connection status if already connected
    if (liveTimingClient.getConnectedStatus()) {
      setIsConnected(true);
    }

    const unsubscribe = liveTimingClient.subscribe((data: any) => {
      if (data.type === "ws_status") {
        setIsConnected(data.connected);
      } else {
        setIsConnected(true);
        if (data.type === "connected") {
          setState(prev => ({ 
            ...prev, 
            active: data.active,
            session_type: data.session_type || prev.session_type,
            current_lap: data.current_lap || prev.current_lap,
            race_name: data.race_name || prev.race_name,
            location: data.location || prev.location,
            country: data.country || prev.country,
          }));
        } else if (data.type === "position_update") {
          setState(prev => ({
            ...prev,
            active: true,
            session_type: data.session_type,
            current_lap: data.lap,
            timestamp: data.timestamp,
            drivers: data.drivers,
          }));
        }
      }
    });

    return () => {
      unsubscribe();
    };
  }, []);

  const formatTime = (seconds: number | null) => {
    if (!seconds) return "--:--.---";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toFixed(3).padStart(6, '0')}`;
  };

  const getTyreColor = (compound: string | null) => {
    switch(compound?.toUpperCase()) {
      case 'SOFT': return 'bg-red-500';
      case 'MEDIUM': return 'bg-yellow-500';
      case 'HARD': return 'bg-slate-100';
      case 'INTERMEDIATE': return 'bg-green-500';
      case 'WET': return 'bg-blue-500';
      default: return 'bg-slate-600';
    }
  };

  const formatStartDateTime = (dateStr?: string | null, timeStr?: string | null) => {
    if (!dateStr || !timeStr) return { date: "---", time: "---" };
    try {
      const dateVal = new Date(`${dateStr} ${timeStr}`);
      const formatterDate = new Intl.DateTimeFormat("en-US", {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
        timeZone: 'Asia/Kolkata'
      });
      const formatterTime = new Intl.DateTimeFormat("en-US", {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
        timeZone: 'Asia/Kolkata'
      });
      return {
        date: formatterDate.format(dateVal),
        time: `${formatterTime.format(dateVal)} IST`
      };
    } catch (e) {
      console.error(e);
      return { date: dateStr, time: timeStr };
    }
  };

  if (!state.active) {
    const formattedStart = formatStartDateTime(state.next_race?.date, state.next_race?.time);

    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-8 max-w-lg mx-auto py-12 animate-in fade-in">
        <div className="text-center space-y-2">
          <Badge variant="outline" className="px-3 py-1 text-xs font-semibold tracking-wider text-red-400 border-red-500/30 bg-red-950/20 uppercase">
            Telemetry Offline
          </Badge>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-100 sm:text-4xl">
            Next Session
          </h1>
          <p className="text-sm text-slate-400">
            The live telemetry tower is waiting for the upcoming race session to start.
          </p>
        </div>

        {state.next_race ? (
          <Card className="w-full glass border-slate-800 overflow-hidden shadow-2xl relative">
            <div className="absolute top-0 right-0 p-4">
              <Badge variant="secondary" className="bg-slate-800 text-slate-300">
                Round {state.next_race.round || 5}
              </Badge>
            </div>
            <CardHeader className="pb-4 pt-6">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-lg bg-red-600/10 flex items-center justify-center border border-red-500/20">
                  <Trophy className="w-6 h-6 text-red-500" />
                </div>
                <div>
                  <CardTitle className="text-2xl font-bold text-slate-100">
                    {state.next_race.name}
                  </CardTitle>
                  <CardDescription className="flex items-center gap-1.5 mt-1 text-slate-400 font-medium">
                    <MapPin className="w-3.5 h-3.5 text-slate-500" />
                    {state.next_race.location}{state.next_race.country ? `, ${state.next_race.country}` : ''}
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 pb-6 pt-2 border-t border-slate-800/60 bg-slate-950/20">
              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-start gap-2.5 p-3 rounded-lg bg-slate-900/40 border border-slate-800/40">
                  <Calendar className="w-4 h-4 text-red-400 mt-0.5" />
                  <div>
                    <span className="block text-[11px] uppercase font-semibold text-slate-500 tracking-wider">Date</span>
                    <span className="text-sm font-medium text-slate-200 mt-0.5 block">{formattedStart.date}</span>
                  </div>
                </div>
                <div className="flex items-start gap-2.5 p-3 rounded-lg bg-slate-900/40 border border-slate-800/40">
                  <Clock className="w-4 h-4 text-red-400 mt-0.5" />
                  <div>
                    <span className="block text-[11px] uppercase font-semibold text-slate-500 tracking-wider">Race Start</span>
                    <span className="text-sm font-medium text-slate-200 mt-0.5 block">{formattedStart.time}</span>
                  </div>
                </div>
              </div>
              <p className="text-xs text-center text-slate-500 italic mt-2">
                * Live strategy & pit stop window ML models will execute automatically when telemetry goes live.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="w-full text-center p-6 border border-dashed border-slate-800 rounded-lg bg-slate-900/20">
            <p className="text-sm text-slate-500">Checking upcoming race schedule...</p>
          </div>
        )}

        <div className="flex items-center gap-2 text-xs text-slate-500 border border-slate-800/80 rounded-full px-4 py-2 bg-slate-900/40">
          <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-emerald-500" : "bg-red-500"}`}></span>
          {isConnected ? "Connected to Live Timing API" : "Connecting to API..."}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Activity className="text-red-500 w-8 h-8 animate-pulse" />
            {state.race_name || "Live Race Tower"}
          </h1>
          <p className="text-slate-400 mt-1">
            {state.location ? `${state.location}, ${state.country || ""}` : "Real-time telemetry and positional data"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline" className="text-sm">Lap {state.current_lap || 0}</Badge>
          <Badge variant="destructive" className="animate-pulse">LIVE</Badge>
        </div>
      </div>

      <Card className="glass border-slate-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs uppercase bg-slate-900/80 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="px-4 py-4 w-12 text-center">Pos</th>
                <th className="px-4 py-4 w-24">Driver</th>
                <th className="px-4 py-4">Gap</th>
                <th className="px-4 py-4">Last Lap</th>
                <th className="px-4 py-4 hidden md:table-cell">S1</th>
                <th className="px-4 py-4 hidden md:table-cell">S2</th>
                <th className="px-4 py-4 hidden md:table-cell">S3</th>
                <th className="px-4 py-4">Tyre</th>
                <th className="px-4 py-4 hidden lg:table-cell">Est Stop</th>
                <th className="px-4 py-4 hidden sm:table-cell text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {state.drivers?.map((driver, index) => (
                <tr 
                  key={driver.code} 
                  className={`border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors ${driver.pitting ? 'bg-amber-900/20' : ''}`}
                >
                  <td className="px-4 py-3 text-center font-bold text-slate-500">{driver.position || index + 1}</td>
                  <td className="px-4 py-3 font-bold text-slate-200">{driver.code}</td>
                  <td className="px-4 py-3 font-mono text-slate-300">
                    {driver.gap_to_leader === 0 ? "Leader" : `+${driver.gap_to_leader?.toFixed(3)}s`}
                  </td>
                  <td className="px-4 py-3 font-mono">{formatTime(driver.last_lap_s)}</td>
                  <td className="px-4 py-3 font-mono text-slate-400 hidden md:table-cell">{driver.sector1_s?.toFixed(3) || "---"}</td>
                  <td className="px-4 py-3 font-mono text-slate-400 hidden md:table-cell">{driver.sector2_s?.toFixed(3) || "---"}</td>
                  <td className="px-4 py-3 font-mono text-slate-400 hidden md:table-cell">{driver.sector3_s?.toFixed(3) || "---"}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className={`w-4 h-4 rounded-full border-2 border-slate-900 ${getTyreColor(driver.compound)}`} title={driver.compound || "Unknown"} />
                      <span className="text-xs text-slate-400">{driver.tyre_life}L</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden lg:table-cell font-mono text-slate-300">
                    {driver.predicted_stint_end ? `Lap ${driver.predicted_stint_end}` : "---"}
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell text-center">
                    {driver.pitting ? (
                      <Badge variant="warning" className="text-[10px]">PIT</Badge>
                    ) : driver.drs ? (
                      <Badge variant="success" className="text-[10px]">DRS</Badge>
                    ) : (
                      <span className="text-slate-600">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      
      {state.timestamp && (
        <div className="text-right text-xs text-slate-500">
          Last updated: {new Date(state.timestamp).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}
