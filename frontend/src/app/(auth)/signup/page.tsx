"use client";

import { useState } from "react";
import { createUserWithEmailAndPassword, updateProfile } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { AlertCircle } from "lucide-react";
import Link from "next/link";
import { fetchApi } from "@/lib/api";

export default function SignupPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!auth) {
      router.push("/dashboard");
      return;
    }

    setLoading(true);
    try {
      const userCredential = await createUserWithEmailAndPassword(auth, email, password);
      await updateProfile(userCredential.user, { displayName: name });
      
      // Initialize the user profile in the backend Firestore
      await fetchApi("/users/profile", {
        method: "PUT",
        requireAuth: true,
        body: JSON.stringify({
          followed_drivers: [],
          notification_prefs: {
            pit_alerts: true,
            safety_car: true,
            fastest_lap: true,
            race_start: true,
          }
        })
      });

      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Failed to create account");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 p-4">
      <Card className="w-full max-w-md glass">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl text-center font-bold tracking-tight text-glow text-red-500">
            JOIN NEXUS
          </CardTitle>
          <CardDescription className="text-center">
            Create an account to track telemetry and get live alerts
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSignup}>
          <CardContent className="space-y-4">
            {error && (
              <div className="p-3 bg-red-900/50 border border-red-500/50 rounded flex items-center gap-2 text-sm text-red-200">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300">Name</label>
              <Input
                type="text"
                placeholder="Ayrton Senna"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300">Email</label>
              <Input
                type="email"
                placeholder="driver@f1nexus.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300">Password</label>
              <Input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Registering..." : "Create Account"}
            </Button>
            <div className="text-center text-sm text-slate-400">
              Already have an account?{" "}
              <Link href="/login" className="text-red-500 hover:text-red-400 font-medium">
                Log in
              </Link>
            </div>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
