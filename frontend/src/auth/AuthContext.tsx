import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, setUnauthorizedHandler } from "../lib/api";
import type { LoginResponse, Role, UserProfile } from "../types/api";

const TOKEN = "sopforge_token";
const USER = "sopforge_user";
export interface SessionUser {
  id: string;
  name: string;
  role: Role;
  employeeId: string;
  email?: string;
  departmentName?: string | null;
}
interface AuthValue {
  user: SessionUser | null;
  ready: boolean;
  login(email: string, password: string): Promise<void>;
  logout(): void;
  hasRole(role: Role): boolean;
}
const AuthContext = createContext<AuthValue | null>(null);
const levels: Record<Role, number> = {
  employee: 0,
  manager: 1,
  executive: 2,
  admin: 3,
};
function fromLogin(value: LoginResponse): SessionUser {
  return {
    id: value.user_id,
    name: value.name,
    role: value.role,
    employeeId: value.employee_id,
  };
}
function fromProfile(value: UserProfile): SessionUser {
  return {
    id: value.id,
    name: value.name,
    role: value.role,
    employeeId: value.employee_id,
    email: value.email,
    departmentName: value.department_name,
  };
}
function readUser(): SessionUser | null {
  try {
    return JSON.parse(
      localStorage.getItem(USER) ?? "null",
    ) as SessionUser | null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(() => readUser());
  const [ready, setReady] = useState(false);
  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN);
    localStorage.removeItem(USER);
    setUser(null);
  }, []);
  useEffect(() => {
    setUnauthorizedHandler(logout);
    if (!localStorage.getItem(TOKEN)) {
      setReady(true);
      return;
    }
    api
      .profile()
      .then((p) => {
        const next = fromProfile(p);
        localStorage.setItem(USER, JSON.stringify(next));
        setUser(next);
      })
      .catch(logout)
      .finally(() => setReady(true));
    return () => setUnauthorizedHandler(null);
  }, [logout]);
  const login = useCallback(async (email: string, password: string) => {
    const result = await api.login(email, password);
    const next = fromLogin(result);
    localStorage.setItem(TOKEN, result.access_token);
    localStorage.setItem(USER, JSON.stringify(next));
    setUser(next);
  }, []);
  const value = useMemo<AuthValue>(
    () => ({
      user,
      ready,
      login,
      logout,
      hasRole: (role) => !!user && levels[user.role] >= levels[role],
    }),
    [user, ready, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth requires AuthProvider");
  return value;
}
