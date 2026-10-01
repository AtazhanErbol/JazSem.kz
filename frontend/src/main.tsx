import React from "react";
import ReactDOM from "react-dom/client";
import {
  createBrowserRouter,
  createRoutesFromElements,
  Navigate,
  Outlet,
  Route,
  RouterProvider,
} from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./i18n";
import "./styles/main.css";
import "./styles/workspace.css";
import { Protected, RoleGate } from "./app/Auth";
import { Loading } from "./components/UI";
import { RouteBoundary } from "./app/RouteBoundary";
import { Landing } from "./features/landing/Landing";
const WorkspaceGuide = React.lazy(() =>
  import("./features/dashboard/AdminDashboard").then((module) => ({
    default: module.WorkspaceGuide,
  })),
);
const Shell = React.lazy(() =>
  import("./layouts/Shell").then((module) => ({ default: module.Shell })),
);
const AuthPage = React.lazy(() =>
  import("./features/auth/AuthPage").then((module) => ({
    default: module.AuthPage,
  })),
);
const Dashboard = React.lazy(() =>
  import("./features/dashboard/Dashboard").then((module) => ({
    default: module.Dashboard,
  })),
);
const ResourcePage = React.lazy(() =>
  import("./features/manage/ResourcePage").then((module) => ({
    default: module.ResourcePage,
  })),
);
const Settings = React.lazy(() =>
  import("./features/manage/Settings").then((module) => ({
    default: module.Settings,
  })),
);
const CoursePage = React.lazy(() =>
  import("./features/courses/CoursePage").then((module) => ({
    default: module.CoursePage,
  })),
);
const AIWizard = React.lazy(() =>
  import("./features/ai/AIWizard").then((module) => ({
    default: module.AIWizard,
  })),
);
const MailDelivery = React.lazy(() =>
  import("./features/manage/MailDelivery").then((module) => ({
    default: module.MailDelivery,
  })),
);
const AssignmentPage = React.lazy(() =>
  import("./features/learning/AssignmentPage").then((module) => ({
    default: module.AssignmentPage,
  })),
);
const TestPage = React.lazy(() =>
  import("./features/learning/TestPage").then((module) => ({
    default: module.TestPage,
  })),
);
const GradePage = React.lazy(() =>
  import("./features/learning/GradePage").then((module) => ({
    default: module.GradePage,
  })),
);
const ResultsPage = React.lazy(() =>
  import("./features/learning/ResultsPage").then((module) => ({
    default: module.ResultsPage,
  })),
);
const GroupPage = React.lazy(() =>
  import("./features/learning/GroupPage").then((module) => ({
    default: module.GroupPage,
  })),
);

const client = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 20000, retry: 1, refetchOnWindowFocus: false },
  },
});
const router = createBrowserRouter(
  createRoutesFromElements(
    <Route
      element={
        <RouteBoundary>
          <React.Suspense fallback={<Loading />}>
            <Outlet />
          </React.Suspense>
        </RouteBoundary>
      }
    >
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<AuthPage />} />
      <Route path="/forgot-password" element={<AuthPage mode="forgot" />} />
      <Route path="/reset-password" element={<AuthPage mode="reset" />} />
      <Route
        path="/change-temporary-password"
        element={
          <Protected>
            <AuthPage mode="change" />
          </Protected>
        }
      />
      <Route
        path="/app"
        element={
          <Protected>
            <Shell />
          </Protected>
        }
      >
        <Route index element={<Dashboard />} />
        <Route
          path="guide"
          element={
            <RoleGate roles={["ADMIN", "TEACHER"]}>
              <WorkspaceGuide />
            </RoleGate>
          }
        />
        {[
          "courses",
          "users",
          "groups",
          "disciplines",
          "assignments",
          "submissions",
          "tests",
          "notifications",
          "content",
          "audit",
          "ai-usage",
        ].map((resource) => (
          <Route
            key={resource}
            path={resource}
            element={
              <RoleGate
                roles={
                  ["content", "audit", "ai-usage"].includes(resource)
                    ? ["ADMIN"]
                    : [
                          "users",
                          "groups",
                          "disciplines",
                          "submissions",
                        ].includes(resource)
                      ? ["ADMIN", "TEACHER"]
                      : ["ADMIN", "TEACHER", "STUDENT"]
                }
              >
                <ResourcePage key={resource} resource={resource} />
              </RoleGate>
            }
          />
        ))}
        <Route path="courses/:id" element={<CoursePage />} />
        <Route path="assignments/:id" element={<AssignmentPage />} />
        <Route path="tests/:id" element={<TestPage />} />
        <Route
          path="submissions/:id"
          element={
            <RoleGate roles={["ADMIN", "TEACHER"]}>
              <GradePage />
            </RoleGate>
          }
        />
        <Route
          path="groups/:id"
          element={
            <RoleGate roles={["ADMIN", "TEACHER"]}>
              <GroupPage />
            </RoleGate>
          }
        />
        <Route path="grades" element={<ResultsPage mode="grades" />} />
        <Route path="progress" element={<ResultsPage mode="progress" />} />
        <Route
          path="ai"
          element={
            <RoleGate roles={["ADMIN", "TEACHER"]}>
              <AIWizard />
            </RoleGate>
          }
        />
        <Route path="settings" element={<Settings />} />
        <Route
          path="mail-outbox"
          element={
            <RoleGate roles={["ADMIN"]}>
              <MailDelivery />
            </RoleGate>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Route>,
  ),
);
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
