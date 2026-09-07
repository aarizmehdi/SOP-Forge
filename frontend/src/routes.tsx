import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { AppShell } from "./components/AppShell";
import { Loading } from "./components/ui";
import type { Role } from "./types/api";
import { AdminPage } from "./pages/AdminPage";
import { AuditPage } from "./pages/AuditPage";
import { ChatPage } from "./pages/ChatPage";
import { DashboardPage } from "./pages/DashboardPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { LoginPage } from "./pages/LoginPage";
import { RequestFormPage } from "./pages/RequestFormPage";
import { RequestsPage } from "./pages/RequestsPage";
import { ReviewPage } from "./pages/ReviewPage";
const levels: Record<Role, number> = {
  employee: 0,
  manager: 1,
  executive: 2,
  admin: 3,
};
function Guard() {
  const { user, ready } = useAuth();
  if (!ready) return <Loading label="Restoring your secure session" />;
  if (!user) return <Navigate to="/login" replace />;
  return <AppShell />;
}
function RoleGuard({
  role,
  children,
}: {
  role: Role;
  children: React.ReactNode;
}) {
  const { user } = useAuth();
  return user && levels[user.role] >= levels[role] ? (
    children
  ) : (
    <Navigate to={user?.role === "employee" ? "/chat" : "/dashboard"} replace />
  );
}
function Home() {
  const { user } = useAuth();
  return (
    <Navigate to={user?.role === "employee" ? "/chat" : "/dashboard"} replace />
  );
}
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Guard />}>
        <Route index element={<Home />} />
        <Route
          path="/chat"
          element={
            <RoleGuard role="employee">
              <ChatPage />
            </RoleGuard>
          }
        />
        <Route
          path="/requests"
          element={
            <RoleGuard role="employee">
              <RequestsPage />
            </RoleGuard>
          }
        />
        <Route
          path="/request/new"
          element={
            <RoleGuard role="employee">
              <RequestFormPage />
            </RoleGuard>
          }
        />
        <Route
          path="/dashboard"
          element={
            <RoleGuard role="manager">
              <DashboardPage />
            </RoleGuard>
          }
        />
        <Route
          path="/review"
          element={
            <RoleGuard role="manager">
              <ReviewPage />
            </RoleGuard>
          }
        />
        <Route
          path="/audit"
          element={
            <RoleGuard role="manager">
              <AuditPage />
            </RoleGuard>
          }
        />
        <Route
          path="/incidents"
          element={
            <RoleGuard role="manager">
              <IncidentsPage />
            </RoleGuard>
          }
        />
        <Route
          path="/admin"
          element={
            <RoleGuard role="admin">
              <AdminPage />
            </RoleGuard>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
