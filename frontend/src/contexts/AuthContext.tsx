"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import api, { setAccessToken } from '@/lib/api';

export type RoleEnum = 'Wildlife Researcher' | 'Conservation Officer' | 'Forest Department Officer' | 'Administrator';

export interface User {
  id: number;
  name: string;
  email: string;
  role: RoleEnum;
  organization?: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (access_token: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchUser = async () => {
    try {
      const response = await api.get('/users/me');
      setUser(response.data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Attempt to silently refresh token on initial load
    api.post('/auth/refresh')
      .then((res) => {
        setAccessToken(res.data.access_token);
        return fetchUser();
      })
      .catch(() => {
        setLoading(false);
      });
  }, []);

  const login = async (access_token: string) => {
    setAccessToken(access_token);
    await fetchUser();
  };

  const logout = async () => {
    await api.post('/auth/logout');
    setAccessToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
