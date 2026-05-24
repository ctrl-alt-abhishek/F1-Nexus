"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Settings, Bell, Car } from "lucide-react";
import { subscribeToPushNotifications } from "@/lib/webpush";
import { useAuth } from "@/components/auth/AuthProvider";

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
  const { user } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pushStatus, setPushStatus] = useState<"idle" | "loading" | "success" | "error">("idle");

  useEffect(() => {
    async function loadProfile() {
      try {
        const data = await fetchApi<UserProfile>("/users/profile", { requireAuth: true });
        setProfile(data);
      } catch (err) {
        console.error(err);
        // Fallback for dummy mode or missing profile
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

  if (loading) {
    return <div className="flex justify-center py-20"><Spinner size="lg" /></div>;
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto animate-in fade-in">
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-3">
          <Settings className="text-red-500 w-8 h-8" />
          Settings
        </h1>
        <p className="text-slate-400 mt-1">Manage your telemetry alerts and driver preferences.</p>
      </div>

      <div className="grid gap-6">
        <Card className="glass">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Bell className="w-5 h-5 text-amber-500" /> Notifications</CardTitle>
            <CardDescription>Configure which live race events trigger alerts.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-slate-800/30 rounded-md border border-slate-800">
              <div>
                <h4 className="font-medium text-slate-200">Push Notifications</h4>
                <p className="text-sm text-slate-400">Receive alerts on your device even when the app is closed.</p>
              </div>
              <Button 
                variant={pushStatus === "success" ? "outline" : "default"} 
                onClick={handleEnablePush}
                disabled={pushStatus === "loading" || pushStatus === "success"}
              >
                {pushStatus === "loading" ? "Enabling..." : pushStatus === "success" ? "Enabled" : "Enable Push"}
              </Button>
            </div>

            <div className="pt-4 space-y-3 border-t border-slate-800">
              <h4 className="font-medium text-slate-300">Event Alerts</h4>
              {[
                { key: "race_start", label: "Race Start / Resumes", desc: "Get notified when the lights go out." },
                { key: "safety_car", label: "Safety Car & VSC", desc: "Alerts for track condition changes." },
                { key: "pit_alerts", label: "Pit Stops", desc: "When followed drivers enter the pits." },
                { key: "fastest_lap", label: "Fastest Laps", desc: "Purple sectors and new fastest laps." },
              ].map(pref => (
                <div key={pref.key} className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-slate-200">{pref.label}</div>
                    <div className="text-xs text-slate-500">{pref.desc}</div>
                  </div>
                  <button
                    onClick={() => handleTogglePref(pref.key as any)}
                    className={`w-11 h-6 rounded-full transition-colors relative ${
                      profile?.notification_prefs[pref.key as keyof UserProfile["notification_prefs"]] 
                        ? "bg-red-600" 
                        : "bg-slate-700"
                    }`}
                  >
                    <div className={`w-4 h-4 bg-white rounded-full absolute top-1 transition-transform ${
                      profile?.notification_prefs[pref.key as keyof UserProfile["notification_prefs"]] 
                        ? "translate-x-6" 
                        : "translate-x-1"
                    }`} />
                  </button>
                </div>
              ))}
            </div>
          </CardContent>
          <CardFooter className="bg-slate-900/50 border-t border-slate-800 py-3">
            <Button onClick={handleSave} disabled={saving} className="ml-auto">
              {saving ? "Saving..." : "Save Preferences"}
            </Button>
          </CardFooter>
        </Card>

        <Card className="glass">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Car className="w-5 h-5 text-blue-500" /> Followed Drivers</CardTitle>
            <CardDescription>You will receive personalized pit alerts for these drivers.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {profile?.followed_drivers.map(driver => (
                <div key={driver} className="px-3 py-1 bg-slate-800 text-slate-200 rounded-full border border-slate-700 flex items-center gap-2">
                  <span className="font-mono text-sm">{driver}</span>
                  <button className="w-4 h-4 rounded-full bg-slate-700 hover:bg-red-500 flex items-center justify-center text-xs">×</button>
                </div>
              ))}
              <Button variant="outline" size="sm" className="h-7 text-xs rounded-full border-dashed">
                + Add Driver
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
