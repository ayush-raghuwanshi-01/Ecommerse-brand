import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, login as apiLogin, logout as apiLogout, register as apiRegister, tokens } from '../lib/api';
import type { User } from '../lib/types';

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (p: { email: string; password: string; full_name: string; phone?: string }) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthCtx = createContext<AuthState>(null as unknown as AuthState);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    if (!tokens.access) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api.get<User>('/auth/me'));
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value: AuthState = {
    user,
    loading,
    refresh,
    login: async (email, password) => {
      const u = await apiLogin(email, password);
      setUser(u);
      return u;
    },
    register: async (p) => {
      const u = await apiRegister(p);
      setUser(u);
      return u;
    },
    logout: async () => {
      await apiLogout();
      setUser(null);
    },
  };

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}
