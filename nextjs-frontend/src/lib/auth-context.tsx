"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { auth } from "./api";

interface AuthState {
  token: string | null;
  userId: string | null;
  email: string | null;
  isLoading: boolean;
}

interface AuthContextType extends AuthState {
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, displayName: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: null,
    userId: null,
    email: null,
    isLoading: true,
  });

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    const userId = localStorage.getItem("user_id");
    const email = localStorage.getItem("user_email");
    if (token) {
      setState({ token, userId, email, isLoading: false });
    } else {
      setState((s) => ({ ...s, isLoading: false }));
    }
  }, []);

  const persist = (token: string, userId: string, email: string) => {
    localStorage.setItem("access_token", token);
    localStorage.setItem("user_id", userId);
    localStorage.setItem("user_email", email);
    setState({ token, userId, email, isLoading: false });
  };

  const signIn = async (email: string, password: string) => {
    const res = await auth.signIn(email, password);
    persist(res.access_token, res.user_id, res.email);
  };

  const signUp = async (email: string, password: string, displayName: string) => {
    const res = await auth.signUp(email, password, displayName);
    persist(res.access_token, res.user_id, res.email);
  };

  const signOut = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_id");
    localStorage.removeItem("user_email");
    setState({ token: null, userId: null, email: null, isLoading: false });
  };

  return (
    <AuthContext.Provider value={{ ...state, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
