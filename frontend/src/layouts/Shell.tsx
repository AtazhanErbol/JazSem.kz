import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard,
  BookOpen,
  Users,
  Layers,
  GraduationCap,
  FileText,
  ClipboardCheck,
  ListChecks,
  ChartNoAxesColumn,
  Sparkles,
  Bell,
  Settings,
  LogOut,
  Menu,
  ShieldCheck,
  Globe,
  Activity,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Logo, Language } from "../components/UI";
import { useUser } from "../app/Auth";
import { api } from "../services/api";

export function Shell() {
  const user = useUser();
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const cache = useQueryClient();
  const links: [string, string, LucideIcon][] = [
    ["", "home", LayoutDashboard],
    ["courses", "courses", BookOpen],
    ...(user.role !== "STUDENT"
      ? [
          ["users", "students", Users],
          ["groups", "groups", Layers],
          ["disciplines", "disciplines", GraduationCap],
        ]
      : []),
    ["assignments", "assignments", FileText],
    ...(user.role !== "STUDENT"
      ? [["submissions", "submissions", ClipboardCheck]]
      : []),
    ["tests", "tests", ListChecks],
    ["grades", "grades", ChartNoAxesColumn],
    ["progress", "progress", Activity],
    ...(user.role !== "STUDENT" ? [["ai", "ai", Sparkles]] : []),
    ...(user.role === "ADMIN"
      ? [
          ["content", "content", Globe],
          ["audit", "audit", ShieldCheck],
          ["ai-usage", "usage", Activity],
        ]
      : []),
  ] as [string, string, LucideIcon][];
  return (
    <div className="app-shell">
      <aside className={open ? "sidebar open" : "sidebar"}>
        <Logo />
        <div className="workspace-label">{t("app")}</div>
        <nav aria-label={t("app")}>
          {links.map(([path, label, Icon]) => (
            <NavLink
              to={"/app/" + path}
              end
              key={path}
              onClick={() => setOpen(false)}
            >
              <Icon size={19} />
              {t(label)}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <NavLink to="/app/settings">
            <Settings size={18} />
            {t("settings")}
          </NavLink>
          <button
            onClick={async () => {
              await api("auth/logout/", "POST");
              cache.clear();
              nav("/login");
            }}
          >
            <LogOut size={18} />
            {t("logout")}
          </button>
        </div>
      </aside>
      <div className="app-main">
        <header className="app-header">
          <button
            className="icon-button mobile-menu"
            onClick={() => setOpen(!open)}
            aria-label="Menu"
          >
            <Menu />
          </button>
          <span className="breadcrumb">
            JazSem <span>/</span> {t("app")}
          </span>
          <div className="header-actions">
            <Language />
            <NavLink
              className="icon-button"
              to="/app/notifications"
              aria-label={t("notifications")}
            >
              <Bell size={20} />
            </NavLink>
            <span className="avatar">
              {user.first_name?.[0] || user.email[0]}
            </span>
            <div className="user-info">
              <strong>
                {user.first_name} {user.last_name}
              </strong>
              <small>{t(user.role)}</small>
            </div>
          </div>
        </header>
        <main className="page">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
