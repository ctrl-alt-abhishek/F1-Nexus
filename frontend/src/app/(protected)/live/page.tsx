"use client";

import { useEffect, useState } from "react";
import { liveTimingClient } from "@/lib/websocket";
import { fetchApi } from "@/lib/api";
import { Spinner } from "@/components/ui/spinner";
import { Trophy, Clock, MapPin, Calendar, Activity, Radio, AlertCircle, PlayCircle } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from 'recharts';

interface DriverUpdate {
  code: string;
  name: string;
  color: string;
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
  rc_messages?: any[];
}

export default function LivePage() {
  const [state, setState] = useState<LiveState>({ active: false });
  const [isConnected, setIsConnected] = useState(false);
  const [isApiConnected, setIsApiConnected] = useState(false);

  useEffect(() => {
    // 1. Fetch initial status from REST API
    async function loadStatus() {
      try {
        const data = await fetchApi<LiveState>("/live/status");
        setState(data);
        setIsApiConnected(true);
      } catch (err) {
        console.error("Failed to load live status via REST API:", err);
        setIsApiConnected(false);
      }
    }
    loadStatus();

    // 2. Connect to WebSocket
    liveTimingClient.connect();

    if (liveTimingClient.getConnectedStatus()) {
      setIsConnected(true);
    }

    const unsubscribe = liveTimingClient.subscribe((data: any) => {
      if (data.type === "ws_status") {
        setIsConnected(data.connected);
      } else {
        setIsConnected(true);
        setIsApiConnected(true);
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
            rc_messages: data.rc_messages,
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

  const getTyreStyle = (compound: string | null) => {
    switch(compound?.toUpperCase()) {
      case 'SOFT': return 'bg-primary/20 text-primary border-primary/30';
      case 'MEDIUM': return 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30';
      case 'HARD': return 'bg-white/20 text-white border-white/30';
      case 'INTERMEDIATE': return 'bg-green-500/20 text-green-500 border-green-500/30';
      case 'WET': return 'bg-blue-500/20 text-blue-500 border-blue-500/30';
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
    }
  };

  const getTyreIndicatorColor = (compound: string | null) => {
    switch(compound?.toUpperCase()) {
      case 'SOFT': return '#b91a24';
      case 'MEDIUM': return '#eab308';
      case 'HARD': return '#ffffff';
      case 'INTERMEDIATE': return '#22c55e';
      case 'WET': return '#3b82f6';
      default: return '#64748b';
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

  // Render Offline State
  if (!state.active) {
    const formattedStart = formatStartDateTime(state.next_race?.date, state.next_race?.time);

    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-8 max-w-lg mx-auto py-12 animate-in fade-in duration-500">
        <div className="text-center space-y-3">
          <span className="px-3 py-1 bg-primary/20 text-primary border border-primary/30 rounded-full text-[10px] font-bold font-mono tracking-widest uppercase animate-pulse">
            Telemetry Offline
          </span>
          <h1 className="text-4xl font-bold tracking-tight text-white font-space mt-2">
            Next Session
          </h1>
          <p className="text-sm text-on-surface-variant font-space">
            The live timing tower is waiting for the upcoming race session to start.
          </p>
        </div>

        {state.next_race ? (
          <div className="w-full glass-card overflow-hidden shadow-2xl relative border border-white/5 flex flex-col">
            <div className="absolute top-6 right-6 z-20">
              <span className="font-mono text-[10px] uppercase tracking-wider bg-white/5 text-on-surface-variant border border-white/10 px-3 py-1 rounded-full">
                Round {state.next_race.round || 1}
              </span>
            </div>
            
            <div className="p-8 pt-10">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20 shrink-0">
                  <Trophy className="w-7 h-7 text-primary" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-white font-space">
                    {state.next_race.name}
                  </h2>
                  <div className="flex items-center gap-1.5 mt-1 text-on-surface-variant text-sm font-space">
                    <MapPin className="w-4 h-4 text-on-surface-variant/60" />
                    {state.next_race.location}{state.next_race.country ? `, ${state.next_race.country}` : ''}
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-4 px-8 pb-8 pt-4 border-t border-white/5 bg-white/[0.01]">
              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-start gap-3 p-4 rounded-xl bg-white/5 border border-white/5">
                  <Calendar className="w-5 h-5 text-primary shrink-0 mt-0.5" />
                  <div>
                    <span className="block text-[10px] uppercase font-bold text-on-surface-variant tracking-wider font-mono">Date</span>
                    <span className="text-sm font-bold text-white mt-1 block font-space">{formattedStart.date}</span>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-4 rounded-xl bg-white/5 border border-white/5">
                  <Clock className="w-5 h-5 text-primary shrink-0 mt-0.5" />
                  <div>
                    <span className="block text-[10px] uppercase font-bold text-on-surface-variant tracking-wider font-mono">Race Start</span>
                    <span className="text-sm font-bold text-white mt-1 block font-space">{formattedStart.time}</span>
                  </div>
                </div>
              </div>
              <p className="text-[10px] text-center text-on-surface-variant/50 italic mt-4 font-space">
                * Live strategy & pit stop window ML models execute automatically when session starts.
              </p>
            </div>
          </div>
        ) : (
          <div className="w-full text-center p-8 border border-dashed border-white/10 rounded-2xl bg-white/[0.01] font-mono text-xs uppercase tracking-wider text-on-surface-variant/60">
            Checking upcoming race schedule...
          </div>
        )}

        <div className="flex items-center gap-2 text-[10px] font-mono font-bold uppercase tracking-wider text-on-surface-variant border border-white/5 rounded-full px-5 py-2.5 bg-white/5">
          <span className={`w-2.5 h-2.5 rounded-full ${isConnected ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse" : "bg-primary animate-pulse"}`}></span>
          {isConnected 
            ? "Live timing WS connected" 
            : isApiConnected 
              ? "API connected • Wait for WS..." 
              : "Connecting to API..."}
        </div>
      </div>
    );
  }

  // Delta chart calculations
  const deltaChartData = (state.drivers || []).slice(0, 8).map(d => ({
    name: d.code,
    gap: d.gap_to_leader === 0 ? 0.1 : d.gap_to_leader,
  }));

  return (
    <div className="h-[calc(100vh-8rem)] grid grid-cols-1 lg:grid-cols-12 gap-6 overflow-hidden relative z-10 animate-in fade-in duration-500">
      {/* Left/Center Content: Live Leaderboard */}
      <section className="col-span-12 lg:col-span-8 flex flex-col h-full overflow-hidden">
        <div className="glass-card p-6 flex flex-col h-full overflow-hidden">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <div className="flex items-center gap-3">
                <span className="px-2.5 py-0.5 bg-primary/20 text-primary border border-primary/30 rounded text-[9px] font-bold font-mono tracking-widest uppercase animate-pulse">LIVE</span>
                <span className="font-mono text-xs text-on-surface-variant font-bold uppercase tracking-wider">
                  {state.session_type || "RACE"} • LAP {state.current_lap || 0}
                </span>
              </div>
              <h2 className="text-2xl font-bold font-space text-white mt-1">
                {state.race_name || "Live Timing Tower"}
              </h2>
            </div>
            
            <div className="flex gap-2">
              <div className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-[10px] font-mono font-bold text-on-surface-variant uppercase tracking-wider">
                WS STATUS: CONNECTED
              </div>
            </div>
          </div>

          {/* Table Container */}
          <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
            <table className="w-full text-left border-separate border-spacing-y-2">
              <thead className="sticky top-0 bg-black/80 backdrop-blur-md z-10">
                <tr className="text-[10px] font-bold font-mono text-on-surface-variant uppercase tracking-widest">
                  <th className="pb-3 pl-4">Pos</th>
                  <th className="pb-3 pl-2">Driver</th>
                  <th className="pb-3">Gap to Ldr</th>
                  <th className="pb-3">Last Lap</th>
                  <th className="pb-3 hidden md:table-cell">S1</th>
                  <th className="pb-3 hidden md:table-cell">S2</th>
                  <th className="pb-3 hidden md:table-cell">S3</th>
                  <th className="pb-3">Compound</th>
                  <th className="pb-3 pr-4 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="font-mono text-sm">
                {state.drivers?.map((driver, index) => (
                  <tr 
                    key={driver.code} 
                    className="glass-card hover:bg-glass-hover border border-white/5 hover:border-primary/30 transition-all duration-300 group cursor-pointer"
                  >
                    <td className="py-4 pl-4 font-bold text-primary">{String(driver.position || index + 1).padStart(2, '0')}</td>
                    <td className="py-4 pl-2 font-space font-bold flex items-center gap-3">
                      <div className="w-1 h-8 rounded-full" style={{ backgroundColor: driver.color || getTyreIndicatorColor(driver.compound) }}></div>
                      <div>
                        <p className="text-white font-bold font-mono text-sm">{driver.name || driver.code}</p>
                        <p className="text-[9px] text-on-surface-variant uppercase tracking-tighter">
                          {driver.pitting ? "PIT LANE" : "ON TRACK"}
                        </p>
                      </div>
                    </td>
                    <td className="py-4 text-white text-xs font-semibold">
                      {driver.gap_to_leader === 0 ? "INTERVAL" : `+${driver.gap_to_leader.toFixed(3)}s`}
                    </td>
                    <td className="py-4 text-white font-bold">{formatTime(driver.last_lap_s)}</td>
                    <td className="py-4 text-on-surface-variant hidden md:table-cell">{driver.sector1_s?.toFixed(3) || "---"}</td>
                    <td className="py-4 text-on-surface-variant hidden md:table-cell">{driver.sector2_s?.toFixed(3) || "---"}</td>
                    <td className="py-4 text-on-surface-variant hidden md:table-cell">{driver.sector3_s?.toFixed(3) || "---"}</td>
                    <td className="py-4">
                      <div className="flex items-center gap-2">
                        <span className={`px-2.5 py-1 border rounded-full text-[9px] font-bold uppercase tracking-wider ${getTyreStyle(driver.compound)}`}>
                          {driver.compound || "UNKNOWN"}
                        </span>
                        <span className="text-[10px] text-on-surface-variant">{driver.tyre_life}L</span>
                      </div>
                    </td>
                    <td className="py-4 pr-4 text-center">
                      {driver.pitting ? (
                        <span className="px-2 py-0.5 bg-primary/20 text-primary border border-primary/30 rounded text-[9px] font-bold uppercase animate-pulse">PIT</span>
                      ) : driver.drs ? (
                        <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-500 border border-yellow-500/30 rounded text-[9px] font-bold uppercase animate-pulse">DRS</span>
                      ) : (
                        <span className="text-on-surface-variant/40">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Right Side: Strategy and Alerts */}
      <aside className="col-span-12 lg:col-span-4 flex flex-col gap-6 h-full overflow-hidden">
        {/* Race Control Alerts */}
        <div className="glass-card p-5 flex flex-col shrink-0 h-72">
          <div className="flex justify-between items-center mb-4 border-b border-white/5 pb-2 shrink-0">
            <h3 className="font-bold text-white font-space text-sm">Race Control</h3>
            <span className="text-[10px] font-mono font-bold text-on-surface-variant uppercase tracking-wider">Feed</span>
          </div>
          <div className="space-y-3 overflow-y-auto custom-scrollbar flex-1 pr-2">
            {(!state.rc_messages || state.rc_messages.length === 0) ? (
              <div className="p-3 bg-white/5 border-l-2 border-white/20 rounded-r-xl">
                <p className="text-[9px] font-mono font-bold text-on-surface-variant tracking-widest uppercase">SYSTEM</p>
                <p className="text-xs text-white leading-tight font-sans mt-0.5">No recent race control messages.</p>
              </div>
            ) : (
              state.rc_messages.map((msg: any, idx: number) => {
                const isIncident = msg.category?.toUpperCase() === "FLAG" || msg.category?.toUpperCase() === "SAFETYCAR";
                return (
                  <div key={idx} className={`p-3 border-l-2 rounded-r-xl ${isIncident ? 'bg-primary/10 border-primary' : 'bg-emerald-500/10 border-emerald-500'}`}>
                    <p className={`text-[9px] font-mono font-bold tracking-widest uppercase ${isIncident ? 'text-primary' : 'text-emerald-400'}`}>
                      {msg.category || "INFO"}
                    </p>
                    <p className="text-xs text-white leading-tight font-sans mt-0.5">{msg.message}</p>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Delta Trends Chart */}
        <div className="glass-card p-5 flex-1 flex flex-col overflow-hidden">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-bold text-white font-space text-sm">Delta Trends</h3>
            <span className="text-[10px] font-mono font-bold text-on-surface-variant uppercase">TOP DRIVERS</span>
          </div>
          <div className="flex-1 w-full mt-2 font-mono text-[10px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={deltaChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="name" stroke="#64748b" tickLine={false} axisLine={false} />
                <YAxis stroke="#64748b" tickFormatter={(v) => `+${v}s`} tickLine={false} axisLine={false} />
                <Bar dataKey="gap" fill="#b91a24" radius={[4, 4, 0, 0]}>
                  {deltaChartData.map((d, index) => (
                    <Cell key={`cell-${index}`} fill={index === 0 ? '#b91a24' : '#64748b'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Strategy window */}
        {(() => {
          const leader = state.drivers?.find(d => d.position === 1 && d.predicted_stint_end) || state.drivers?.find(d => d.predicted_stint_end);
          const compound = leader?.compound || "UNKNOWN";
          const stintEnd = leader?.predicted_stint_end || 0;
          const currentLap = state.current_lap || 0;
          const lapsToPit = Math.max(0, stintEnd - currentLap);
          const isWindowOpen = lapsToPit <= 3 && lapsToPit > 0;
          const isPastWindow = lapsToPit === 0 && currentLap > 0;
          
          return (
            <div className="glass-card p-5 mb-2 shrink-0">
              <h3 className="font-bold text-white font-space text-sm mb-4">ML Strategy (Race Leader)</h3>
              <div className="relative h-12 bg-white/5 rounded-2xl flex items-center px-4 border border-white/10 overflow-hidden">
                <div className={`absolute top-0 left-0 h-full transition-all duration-1000 ${getTyreStyle(compound)} opacity-20`} style={{ width: `${Math.min(100, (currentLap / (stintEnd || 1)) * 100)}%` }}></div>
                <div className="relative z-10 w-full flex justify-between items-center text-[10px] font-mono font-bold">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full shadow-[0_0_8px_currentColor] animate-pulse ${getTyreStyle(compound).split(' ')[1]}`} style={{ backgroundColor: getTyreIndicatorColor(compound) }}></span>
                    <span className="uppercase">{leader?.name || "LEADER"} • {compound} STINT</span>
                  </div>
                  <div className="bg-black/40 px-2.5 py-1 rounded-full border border-white/5">
                    <span>PIT WINDOW LAP {Math.max(1, stintEnd - 2)}-{stintEnd + 2}</span>
                  </div>
                </div>
              </div>
              <p className="mt-3 text-[10px] text-on-surface-variant italic text-center font-space">
                {stintEnd === 0 
                  ? "Waiting for ML strategy engine predictions..." 
                  : isPastWindow 
                    ? `Tyres have exceeded optimal ML stint life. Pit stop expected.`
                    : `Optimal pit stop window opens in ${lapsToPit} laps.`}
              </p>
            </div>
          );
        })()}
      </aside>
    </div>
  );
}
