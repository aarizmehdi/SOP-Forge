import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  ClipboardCheck,
  FilePlus2,
  Files,
  LogOut,
  Menu,
  MessageSquareText,
  ScrollText,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import type { Role } from "../types/api";

const navigation: {
  to: string;
  label: string;
  icon: typeof Files;
  min: Role;
  adminOnly?: boolean;
  employeeOnly?: boolean;
}[] = [
  {
    to: "/chat",
    label: "Assistant",
    icon: MessageSquareText,
    min: "employee",
    employeeOnly: true,
  },
  {
    to: "/requests",
    label: "My requests",
    icon: Files,
    min: "employee",
    employeeOnly: true,
  },
  {
    to: "/request/new",
    label: "New request",
    icon: FilePlus2,
    min: "employee",
    employeeOnly: true,
  },
  { to: "/dashboard", label: "Overview", icon: BarChart3, min: "manager" },
  {
    to: "/review",
    label: "Review queue",
    icon: ClipboardCheck,
    min: "manager",
  },
  { to: "/audit", label: "Audit trail", icon: ScrollText, min: "manager" },
  { to: "/incidents", label: "Incidents", icon: AlertTriangle, min: "manager" },
  {
    to: "/admin",
    label: "Policy library",
    icon: BookOpen,
    min: "admin",
    adminOnly: true,
  },
];
export function AppShell() {
  const { user, logout, hasRole } = useAuth();
  const [open, setOpen] = useState(false);
  const items = navigation.filter((x) =>
    x.employeeOnly
      ? user?.role === "employee"
      : x.adminOnly
        ? user?.role === "admin"
        : hasRole(x.min),
  );
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className={`sidebar ${open ? "is-open" : ""}`}>
        <div className="brand">
          <img src="/assets/branding/mark.svg" alt="" />
          <div>
            <strong>SOP Forge</strong>
            <span>Decision workspace</span>
          </div>
          <button
            className="mobile-close"
            aria-label="Close menu"
            onClick={() => setOpen(false)}
          >
            <X />
          </button>
        </div>
        <nav aria-label="Primary navigation">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setOpen(false)}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-user">
          <div className="avatar">
            {user?.name
              .split(" ")
              .map((v) => v[0])
              .join("")
              .slice(0, 2)
              .toUpperCase()}
          </div>
          <div>
            <strong>{user?.name}</strong>
            <span>{user?.role}</span>
          </div>
          <button aria-label="Sign out" onClick={logout}>
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="mobile-bar">
          <button aria-label="Open menu" onClick={() => setOpen(true)}>
            <Menu />
          </button>
          <img src="/assets/branding/lockup.svg" alt="SOP Forge" />
        </header>
        <main id="main">
          <Outlet />
        </main>
      </div>
      {open && (
        <button
          className="nav-scrim"
          aria-label="Close menu"
          onClick={() => setOpen(false)}
        />
      )}
    </div>
  );
}
