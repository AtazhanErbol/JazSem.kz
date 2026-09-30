import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
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
  CircleHelp,
  X,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Logo, Language } from "../components/UI";
import { useUser } from "../app/Auth";
import { useAction } from "../hooks/useAction";

export function Shell() {
  const user = useUser();
  const logout = useAction();
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const location = useLocation();
  const cache = useQueryClient();
  const links: [string, string, LucideIcon][] = [
    ["", "home", LayoutDashboard],
    [
      "courses",
      user.role === "ADMIN" ? "workspace.courses" : "courses",
      BookOpen,
    ],
    ...(user.role !== "STUDENT"
      ? [
          ["users", user.role === "ADMIN" ? "users" : "students", Users],
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
  const groups =
    user.role === "ADMIN"
      ? [
          { title: "", paths: [""] },
          {
            title: "workspace.learning",
            paths: [
              "courses",
              "disciplines",
              "assignments",
              "tests",
              "submissions",
              "grades",
              "progress",
            ],
          },
          { title: "workspace.people", paths: ["users", "groups"] },
          {
            title: "workspace.management",
            paths: ["ai", "content", "audit", "ai-usage"],
          },
        ]
      : [{ title: "", paths: links.map(([path]) => path) }];
  const currentLabel =
    location.pathname === "/app/guide"
      ? "workspace.guide"
      : location.pathname === "/app/settings"
        ? "settings"
        : location.pathname === "/app/notifications"
          ? "notifications"
          : links.find(
              ([path]) => path && location.pathname.startsWith(`/app/${path}`),
            )?.[1] || (user.role === "ADMIN" ? "workspace.home" : "home");
  return (
    <div className="app-shell">
      {open && (
        <button
          className="sidebar-backdrop"
          aria-label={t("close")}
          onClick={() => setOpen(false)}
        />
      )}
      <aside
        id="workspace-navigation"
        className={open ? "sidebar open" : "sidebar"}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false);
        }}
      >
        <Logo />
        <div className="workspace-label">{t("app")}</div>
        <nav aria-label={t("app")}>
          {groups.map((group) => (
            <div className="nav-group" key={group.title}>
              {group.title && (
                <div className="nav-group-title">{t(group.title)}</div>
              )}
              {group.paths
                .map((path) => links.find((link) => link[0] === path)!)
                .map(([path, label, Icon]) => (
                  <NavLink
                    to={"/app" + (path ? "/" + path : "")}
                    end={!path}
                    key={path}
                    onClick={() => setOpen(false)}
                  >
                    <Icon size={19} />
                    {t(label)}
                  </NavLink>
                ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          {user.role !== "STUDENT" && (
            <NavLink to="/app/guide" onClick={() => setOpen(false)}>
              <CircleHelp size={18} />
              {t("workspace.guide")}
            </NavLink>
          )}
          <NavLink to="/app/settings" onClick={() => setOpen(false)}>
            <Settings size={18} />
            {t("settings")}
          </NavLink>
          <button
            disabled={logout.pending}
            onClick={async () => {
              const result = await logout.run("auth/logout/");
              if (result.ok) {
                cache.clear();
                nav("/login");
              }
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
            aria-label={t("workspace.menu")}
            aria-controls="workspace-navigation"
            aria-expanded={open}
          >
            {open ? <X /> : <Menu />}
          </button>
          <span className="breadcrumb">
            JazSem <span>/</span> {t(currentLabel)}
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
          {logout.feedback}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
