"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Spinner } from "@/components/ui/spinner";
import { Settings as SettingsIcon, Bell, Car, Trash2, Plus } from "lucide-react";
import { subscribeToPushNotifications } from "@/lib/webpush";

interface UserProfile {
  followed_drivers: string[];
  notification_prefs: {
    pit_alerts: boolean;
    safety_car: boolean;
    fastest_lap: boolean;
    race_start: boolean;
  };
}

export default function SettingsPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pushStatus, setPushStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [newDriver, setNewDriver] = useState("");
  const [isAdding, setIsAdding] = useState(false);

  useEffect(() => {
    async function loadProfile() {
      try {
        const data = await fetchApi<UserProfile>("/users/profile", { requireAuth: true });
        setProfile(data);
      } catch (err) {
        console.error(err);
        setProfile({
          followed_drivers: ["VER", "LEC", "HAM"],
          notification_prefs: { pit_alerts: true, safety_car: true, fastest_lap: false, race_start: true }
        });
      } finally {
        setLoading(false);
      }
    }
    loadProfile();
  }, []);

  const handleTogglePref = (key: keyof UserProfile["notification_prefs"]) => {
    if (!profile) return;
    setProfile({
      ...profile,
      notification_prefs: {
        ...profile.notification_prefs,
        [key]: !profile.notification_prefs[key]
      }
    });
  };

  const handleSave = async () => {
    if (!profile) return;
    setSaving(true);
    try {
      await fetchApi("/users/profile", {
        method: "PUT",
        requireAuth: true,
        body: JSON.stringify(profile)
      });
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const handleEnablePush = async () => {
    setPushStatus("loading");
    const success = await subscribeToPushNotifications();
    setPushStatus(success ? "success" : "error");
  };

  const handleRemoveDriver = (driver: string) => {
    if (!profile) return;
    setProfile({
      ...profile,
      followed_drivers: profile.followed_drivers.filter(d => d !== driver)
    });
  };

  const handleAddDriver = () => {
    if (!profile || !newDriver.trim()) return;
    const formatted = newDriver.trim().toUpperCase();
    if (profile.followed_drivers.includes(formatted)) return;
    setProfile({
      ...profile,
      followed_drivers: [...profile.followed_drivers, formatted]
    });
    setNewDriver("");
    setIsAdding(false);
  };

  if (loading) {
    return <div className="flex justify-center py-20"><Spinner size="lg" /></div>;
  }

  return (
    <div className="space-y-12 max-w-5xl mx-auto animate-in fade-in duration-500">
      {/* Header */}
      <div>
        <h1 className="text-5xl font-bold tracking-tight text-white font-space flex items-center gap-3">
          <SettingsIcon className="text-primary w-10 h-10" />
          Preferences &amp; Alerts
        </h1>
        <p className="text-on-surface-variant mt-3 text-lg font-space">
          Configure telemetry pushes and active alerts for your favorite grid drivers.
        </p>
      </div>

      <div className="grid gap-6">
        {/* Alerts Settings Card */}
        <div className="glass-card p-8 flex flex-col justify-between border border-white/5">
          <div>
            <div className="flex items-center gap-3 mb-8 border-b border-white/5 pb-4">
              <Bell className="w-5 h-5 text-primary" />
              <div>
                <h3 className="text-lg font-bold font-space text-white">Live Event Alerts</h3>
                <p className="text-xs text-on-surface-variant font-space">Configure triggers for push notifications</p>
              </div>
            </div>

            <div className="space-y-6">
              {/* Push registration button */}
              <div className="flex items-center justify-between p-4 rounded-xl bg-white/5 border border-white/5">
                <div>
                  <h4 className="font-bold text-white text-sm font-space">Push Alerts Registration</h4>
                  <p className="text-xs text-on-surface-variant mt-0.5 font-sans">Receive session and flag notifications directly to your desktop or device</p>
                </div>
                <button 
                  onClick={handleEnablePush}
                  disabled={pushStatus === "loading" || pushStatus === "success"}
                  className={`font-mono text-[10px] font-bold uppercase tracking-widest py-3 px-5 border rounded-xl transition-all ${
                    pushStatus === "success"
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                      : "border-primary/20 bg-primary/10 hover:bg-primary/20 text-primary"
                  }`}
                >
                  {pushStatus === "loading" ? "Enabling..." : pushStatus === "success" ? "Enabled" : "Enable Push"}
                </button>
              </div>

              {/* Toggles list */}
              <div className="pt-4 space-y-4 border-t border-white/5">
                <h4 className="text-[10px] font-mono font-bold text-on-surface-variant/60 uppercase tracking-widest mb-4">Event Triggers</h4>
                {[
                  { key: "race_start", label: "Race Start / Resumes", desc: "Get alerts when the lights go out or safety car ends." },
                  { key: "safety_car", label: "Safety Car & VSC", desc: "Instant alert when yellow conditions or safety car starts." },
                  { key: "pit_alerts", label: "Driver Pit Stops", desc: "Alerts when followed drivers enter or exit pit boxes." },
                  { key: "fastest_lap", label: "Fastest Sector / Laps", desc: "Alert when a driver goes purple or sets fastest lap." },
                ].map(pref => (
                  <div key={pref.key} className="flex items-center justify-between pb-3 border-b border-white/5 last:border-0 last:pb-0">
                    <div>
                      <div className="text-sm font-bold text-white font-space">{pref.label}</div>
                      <div className="text-xs text-on-surface-variant font-sans mt-0.5">{pref.desc}</div>
                    </div>
                    <button
                      onClick={() => handleTogglePref(pref.key as any)}
                      className={`w-11 h-6 rounded-full transition-colors relative border border-white/5 ${
                        profile?.notification_prefs[pref.key as keyof UserProfile["notification_prefs"]] 
                          ? "bg-primary" 
                          : "bg-white/10"
                      }`}
                    >
                      <div className={`w-4 h-4 bg-white rounded-full absolute top-0.5 transition-transform ${
                        profile?.notification_prefs[pref.key as keyof UserProfile["notification_prefs"]] 
                          ? "translate-x-6" 
                          : "translate-x-1"
                      }`} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-white/5 flex">
            <button 
              onClick={handleSave} 
              disabled={saving} 
              className="ml-auto font-mono text-[10px] font-bold uppercase tracking-widest py-3.5 px-6 border border-primary/20 bg-primary/10 hover:bg-primary/20 text-primary rounded-xl transition-all"
            >
              {saving ? "Saving..." : "Save Preferences"}
            </button>
          </div>
        </div>

        {/* Followed Drivers Card */}
        <div className="glass-card p-8 border border-white/5">
          <div className="flex items-center gap-3 mb-8 border-b border-white/5 pb-4">
            <Car className="w-5 h-5 text-primary" />
            <div>
              <h3 className="text-lg font-bold font-space text-white">Grid Tracking</h3>
              <p className="text-xs text-on-surface-variant font-space">Receive personalized stint telemetry updates for these specific driver codes</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2.5">
            {profile?.followed_drivers.map(driver => (
              <div 
                key={driver} 
                className="px-4 py-2 bg-white/5 border border-white/15 hover:border-primary/30 rounded-xl flex items-center gap-2.5 transition-all font-mono group"
              >
                <span className="text-sm font-bold text-white tracking-wider">{driver}</span>
                <button 
                  onClick={() => handleRemoveDriver(driver)}
                  className="w-4 h-4 rounded-full bg-white/5 hover:bg-primary text-on-surface-variant hover:text-white flex items-center justify-center text-[10px] transition-colors"
                >
                  ×
                </button>
              </div>
            ))}
            
            {isAdding ? (
              <div className="flex items-center gap-1.5 font-mono">
                <input 
                  type="text" 
                  value={newDriver} 
                  onChange={(e) => setNewDriver(e.target.value)} 
                  maxLength={3}
                  placeholder="CODE"
                  className="w-20 px-3 py-1.5 text-xs bg-black/40 border border-white/10 rounded-xl outline-none text-white focus:ring-1 focus:ring-primary focus:border-primary uppercase font-bold"
                  onKeyDown={(e) => e.key === "Enter" && handleAddDriver()}
                />
                <button onClick={handleAddDriver} className="px-3 py-1.5 bg-primary/20 border border-primary/30 text-primary rounded-xl text-[10px] font-bold uppercase transition-all">Add</button>
                <button onClick={() => setIsAdding(false)} className="px-3 py-1.5 bg-white/5 border border-white/10 text-on-surface-variant rounded-xl text-[10px] font-bold uppercase transition-all">Cancel</button>
              </div>
            ) : (
              <button 
                onClick={() => setIsAdding(true)} 
                className="px-4 py-2 border border-dashed border-white/15 bg-white/[0.01] hover:border-primary/50 text-[10px] font-bold uppercase tracking-wider text-on-surface-variant hover:text-white rounded-xl transition-all font-mono"
              >
                + Track Driver
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
