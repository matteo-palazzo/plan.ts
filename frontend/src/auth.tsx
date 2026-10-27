import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, onUnauthorized, setCsrfToken } from "./api/client";
import { auth } from "./api/endpoints";

interface AuthState {
  username: string | null;
  checking: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    onUnauthorized(() => {
      setCsrfToken(null);
      setUsername(null);
    });
    auth
      .me()
      .then((session) => {
        setCsrfToken(session.csrf_token);
        setUsername(session.username);
      })
      .catch((error: unknown) => {
        if (!(error instanceof ApiError && error.status === 401)) console.error(error);
      })
      .finally(() => setChecking(false));
    return () => onUnauthorized(null);
  }, []);

  const login = useCallback(async (name: string, password: string) => {
    const session = await auth.login(name, password);
    setCsrfToken(session.csrf_token);
    setUsername(session.username);
  }, []);

  const logout = useCallback(async () => {
    try {
      await auth.logout();
    } finally {
      setCsrfToken(null);
      setUsername(null);
    }
  }, []);

  const value = useMemo(() => ({ username, checking, login, logout }), [username, checking, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth deve essere usato dentro AuthProvider");
  return context;
}
