interface Filter {
  key: string;
  label: string;
  values?: string[];
  source?: string;
  adminOnly?: boolean;
  authorOnly?: boolean;
}
interface Capability {
  search: boolean;
  filters: Filter[];
  order?: string[];
}
const teacher: Filter = {
  key: "teacher",
  label: "teacher",
  source: "users/?role=TEACHER&is_active=true",
  adminOnly: true,
};
const course: Filter = { key: "course", label: "course", source: "courses/" };
const group: Filter = {
  key: "group",
  label: "groups",
  source: "groups/?status=ACTIVE",
  authorOnly: true,
};
export const capabilities: Record<string, Capability> = {
  courses: {
    search: true,
    filters: [
      {
        key: "status",
        label: "status",
        values: ["DRAFT", "PUBLISHED", "ARCHIVED"],
      },
      teacher,
      { key: "discipline", label: "discipline", source: "disciplines/" },
      group,
    ],
    order: ["-created_at", "title"],
  },
  users: {
    search: true,
    filters: [
      { ...teacher, key: "owner_teacher", label: "owner_teacher" },
      group,
      { key: "is_active", label: "is_active", values: ["true", "false"] },
    ],
    order: ["-created_at", "last_name", "email"],
  },
  groups: {
    search: true,
    filters: [
      teacher,
      { key: "status", label: "status", values: ["ACTIVE", "ARCHIVED"] },
    ],
  },
  disciplines: {
    search: true,
    filters: [
      { key: "status", label: "status", values: ["ACTIVE", "ARCHIVED"] },
    ],
  },
  assignments: {
    search: true,
    filters: [
      course,
      teacher,
      { key: "due", label: "ux.due", values: ["overdue", "future", "none"] },
      {
        key: "status",
        label: "status",
        values: ["DRAFT", "PUBLISHED"],
        authorOnly: true,
      },
    ],
    order: ["deadline", "-created_at", "title"],
  },
  tests: {
    search: true,
    filters: [
      course,
      teacher,
      {
        key: "status",
        label: "status",
        values: ["DRAFT", "PUBLISHED"],
        authorOnly: true,
      },
    ],
  },
  submissions: {
    search: true,
    filters: [
      course,
      group,
      {
        key: "status",
        label: "status",
        values: [
          "SUBMITTED",
          "RESUBMITTED",
          "UNDER_REVIEW",
          "REVISION_REQUESTED",
          "GRADED",
        ],
      },
      { key: "pending", label: "ux.reviewQueue", values: ["true"] },
    ],
  },
  enrollments: {
    search: false,
    filters: [
      course,
      group,
      teacher,
      {
        key: "status",
        label: "status",
        values: ["ASSIGNED", "IN_PROGRESS", "COMPLETED", "ARCHIVED"],
      },
    ],
  },
  notifications: {
    search: true,
    filters: [{ key: "is_read", label: "read", values: ["true", "false"] }],
  },
  content: {
    search: true,
    filters: [
      { key: "language", label: "language", values: ["ru", "kk"] },
      { key: "is_published", label: "is_published", values: ["true", "false"] },
    ],
  },
  audit: { search: true, filters: [] },
  "ai-usage": { search: false, filters: [] },
};
