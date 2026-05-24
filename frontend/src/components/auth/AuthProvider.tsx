"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { User, onAuthStateChanged, signOut } from "firebase/auth";
import { auth } from "@/lib/firebase";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  logout: () => Promise<void>;
  getToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  logout: async () => {},
  getToken: async () => null,
});

// A dummy user object for local development when Firebase isn't configured
const DUMMY_USER = {
  uid: "local_dev_user",
  email: "dev@f1nexus.local",
  displayName: "Dev User",
  getIdToken: async () => "dummy_dev_token",
} as unknown as User;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // If auth is undefined (dummy config), we mock a logged in user for development
    if (!auth) {
      setUser(DUMMY_USER);
      setLoading(false);
      return;
    }

    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      setUser(firebaseUser);
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const logout = async () => {
    if (auth) {
      await signOut(auth);
    } else {
      setUser(null); // Just clear dummy user
    }
  };

  const getToken = async () => {
    if (!user) return null;
    try {
      return await user.getIdToken();
    } catch (e) {
      console.warn("Failed to get token", e);
      return null;
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, logout, getToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
