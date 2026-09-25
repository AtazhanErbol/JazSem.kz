export interface Field {
  name: string;
  type?:
    | "text"
    | "textarea"
    | "number"
    | "email"
    | "checkbox"
    | "datetime-local"
    | "file"
    | "select";
  options?: string[];
  source?: string;
  required?: boolean;
  default?: unknown;
}
const text = (name: string, required = true): Field => ({ name, required });
const select = (name: string, source: string): Field => ({
  name,
  type: "select",
  source,
  required: true,
});
export const fields: Record<string, Field[]> = {
  users: [
    { name: "email", type: "email", required: true },
    text("first_name"),
    text("last_name"),
    {
      name: "role",
      type: "select",
      options: ["STUDENT", "TEACHER", "ADMIN"],
      default: "STUDENT",
    },
    {
      name: "preferred_language",
      type: "select",
      options: ["ru", "kk"],
      default: "ru",
    },
  ],
  disciplines: [
    text("name"),
    text("code"),
    { name: "description", type: "textarea" },
    select("teachers", "users/?role=TEACHER"),
  ],
  groups: [
    text("name"),
    { name: "description", type: "textarea" },
    select("teacher", "users/?role=TEACHER"),
  ],
  courses: [
    text("title"),
    { name: "description", type: "textarea" },
    select("discipline", "disciplines/"),
    select("teacher", "users/?role=TEACHER"),
    {
      name: "default_language",
      type: "select",
      options: ["ru", "kk"],
      default: "ru",
    },
  ],
  weeks: [
    text("title"),
    { name: "number", type: "number", default: 1, required: true },
    { name: "order", type: "number", default: 0 },
  ],
  topics: [
    text("title"),
    { name: "content", type: "textarea" },
    { name: "order", type: "number", default: 0 },
    { name: "is_required", type: "checkbox", default: true },
  ],
  materials: [
    text("title"),
    {
      name: "type",
      type: "select",
      options: [
        "TEXT",
        "PDF",
        "DOCUMENT",
        "PRESENTATION",
        "IMAGE",
        "VIDEO_LINK",
        "FILE",
      ],
      default: "TEXT",
    },
    { name: "content", type: "textarea" },
    { name: "external_url" },
    { name: "file", type: "file" },
    { name: "order", type: "number", default: 0 },
    { name: "is_required", type: "checkbox", default: true },
  ],
  assignments: [
    text("title"),
    { name: "instructions", type: "textarea", required: true },
    { name: "max_score", type: "number", default: 100 },
    { name: "deadline", type: "datetime-local" },
    { name: "allow_late_submission", type: "checkbox", default: false },
    { name: "is_required", type: "checkbox", default: true },
  ],
  tests: [
    text("title"),
    { name: "description", type: "textarea" },
    { name: "time_limit_minutes", type: "number", default: 30 },
    { name: "max_attempts", type: "number", default: 2 },
    { name: "passing_score", type: "number", default: 50 },
    { name: "available_from", type: "datetime-local" },
    { name: "available_until", type: "datetime-local" },
    { name: "shuffle_questions", type: "checkbox", default: true },
    { name: "shuffle_answers", type: "checkbox", default: true },
    { name: "is_required", type: "checkbox", default: true },
    { name: "is_final", type: "checkbox", default: false },
  ],
  questions: [
    { name: "text", type: "textarea", required: true },
    {
      name: "type",
      type: "select",
      options: ["SINGLE_CHOICE", "MULTIPLE_CHOICE"],
      default: "SINGLE_CHOICE",
    },
    { name: "score", type: "number", default: 1 },
    { name: "explanation", type: "textarea" },
    { name: "order", type: "number", default: 0 },
  ],
  options: [
    text("text"),
    { name: "is_correct", type: "checkbox", default: false },
    { name: "order", type: "number", default: 0 },
  ],
  "grading-schemes": [text("title")],
  "grading-components": [
    {
      name: "kind",
      type: "select",
      options: ["ASSIGNMENTS", "TESTS", "FINAL"],
      default: "ASSIGNMENTS",
    },
    { name: "weight", type: "number", required: true, default: 100 },
  ],
  content: [
    text("key"),
    text("title"),
    { name: "body", type: "textarea" },
    { name: "language", type: "select", options: ["ru", "kk"], default: "ru" },
    { name: "is_published", type: "checkbox", default: false },
  ],
};
