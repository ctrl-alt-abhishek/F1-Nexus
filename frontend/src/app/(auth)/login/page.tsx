"use client";

import { useState } from "react";
import { signInWithEmailAndPassword } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { AlertCircle } from "lucide-react";
import Link from "next/link";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    
    // In dummy mode, auth is undefined
    if (!auth) {
      router.push("/dashboard");
      return;
    }

    setLoading(true);
    try {
      await signInWithEmailAndPassword(auth, email, password);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Failed to log in");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 p-4">
      <Card className="w-full max-w-md glass">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl text-center font-bold tracking-tight text-glow text-red-500">
            F1 NEXUS
          </CardTitle>
          <CardDescription className="text-center">
            Enter your credentials to access the grid
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleLogin}>
          <CardContent className="space-y-4">
            {error && (
              <div className="p-3 bg-red-900/50 border border-red-500/50 rounded flex items-center gap-2 text-sm text-red-200">
                <AlertCircle className="w-4 h-4" />
                <span>{error}</span>
              </div>
            )}
            {!auth && (
              <div className="p-3 bg-amber-900/50 border border-amber-500/50 rounded flex items-center gap-2 text-sm text-amber-200">
                <AlertCircle className="w-4 h-4" />
                <span>Dummy mode active. Click Login to proceed.</span>
              </div>
            )}
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
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-slate-300">Password</label>
              </div>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Connecting..." : "Lights Out"}
            </Button>
            <div className="text-center text-sm text-slate-400">
              Don't have an account?{" "}
              <Link href="/signup" className="text-red-500 hover:text-red-400 font-medium">
                Sign up
              </Link>
            </div>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
