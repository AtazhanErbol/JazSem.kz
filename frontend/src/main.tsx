import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./i18n";
import "./styles/main.css";
import { Protected } from "./app/Auth";
import { Shell } from "./layouts/Shell";
import { Landing } from "./features/landing/Landing";
import { AuthPage } from "./features/auth/AuthPage";
import { Dashboard } from "./features/dashboard/Dashboard";
import { ResourcePage } from "./features/manage/ResourcePage";
import { Settings } from "./features/manage/Settings";
import { CoursePage } from "./features/courses/CoursePage";
import {
  AssignmentPage,
  GradePage,
  GroupPage,
  ResultsPage,
  TestPage,
} from "./features/learning/Activities";
import { AIWizard } from "./features/ai/AIWizard";

const client = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 20000, retry: 1, refetchOnWindowFocus: false },
  },
});
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <Routes>
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
                element={<ResourcePage key={resource} resource={resource} />}
              />
            ))}
            <Route path="courses/:id" element={<CoursePage />} />
            <Route path="assignments/:id" element={<AssignmentPage />} />
            <Route path="tests/:id" element={<TestPage />} />
            <Route path="submissions/:id" element={<GradePage />} />
            <Route path="groups/:id" element={<GroupPage />} />
            <Route path="grades" element={<ResultsPage mode="grades" />} />
            <Route path="progress" element={<ResultsPage mode="progress" />} />
            <Route path="ai" element={<AIWizard />} />
            <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
