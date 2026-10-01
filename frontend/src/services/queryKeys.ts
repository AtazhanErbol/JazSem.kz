export const queryKeys = {
  list: (resource: string, params = "") => [resource, "list", params] as const,
  detail: (resource: string, id: string) => [resource, "detail", id] as const,
  tree: (id: string, version = "") => ["tree", id, version] as const,
  options: (source: string, search: string, page: number) =>
    ["options", source, search, page] as const,
};

// Roots intentionally include dependent learning summaries, but answering one
// question never refetches the dashboard, navigation, course tree or history.
export function affectedQueries(path: string): string[] {
  const [resource, , action] = path.split("/");
  if (resource === "auth")
    return path === "auth/me/" || path === "auth/change-password/"
      ? ["me"]
      : [];
  if (resource === "attempts" && action === "answer") return [];
  const graph: Record<string, string[]> = {
    attempts: [
      "attempts",
      "attempt",
      "progress",
      "grades",
      "enrollments",
      "dashboard",
    ],
    submissions: [
      "submissions",
      "submission",
      "progress",
      "grades",
      "enrollments",
      "dashboard",
    ],
    enrollments: [
      "course-recipients",
      "enrollments",
      "courses",
      "tree",
      "progress",
      "grades",
      "dashboard",
    ],
    users: ["users", "options", "dashboard", "members", "course-teachers"],
    groups: [
      "course-recipients",
      "groups",
      "members",
      "options",
      "enrollments",
      "dashboard",
    ],
    courses: [
      "grades",
      "progress",
      "submissions",
      "attempts",
      "attempt",
      "course-recipients",
      "courses",
      "tree",
      "versions",
      "enrollments",
      "options",
      "dashboard",
    ],
    disciplines: ["disciplines", "options", "dashboard"],
    "ai-jobs": ["ai-jobs", "jobs", "job", "draft"],
    "ai-drafts": [
      "ai-jobs",
      "jobs",
      "job",
      "draft",
      "ai-drafts",
      "courses",
      "tree",
      "versions",
    ],
    sources: ["sources", "chunks"],
    "mail-outbox": ["mail-outbox"],
  };
  if (resource === "assignments" && action === "submit")
    return graph.submissions;
  if (resource === "tests" && action === "start") return graph.attempts;
  if (["topics", "materials"].includes(resource) && action === "complete")
    return ["progress", "enrollments", "dashboard"];
  if (
    [
      "weeks",
      "topics",
      "materials",
      "assignments",
      "tests",
      "questions",
      "options",
      "grading-schemes",
      "grading-components",
    ].includes(resource)
  )
    return [resource, "tree", "options", "dashboard"];
  return graph[resource] || [resource];
}
