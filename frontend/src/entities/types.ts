export type Role = "ADMIN" | "TEACHER" | "STUDENT";
export interface User {
  id: string;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  role: Role;
  must_change_password: boolean;
  preferred_language: "ru" | "kk";
}
export interface Row {
  id: string;
  [key: string]: unknown;
}
export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
export interface Option extends Row {
  text: string;
  is_correct?: boolean;
}
export interface Question extends Row {
  text: string;
  type: string;
  options: Option[];
}
export interface Activity extends Row {
  title: string;
  content?: string;
  instructions?: string;
  file?: boolean;
  external_url?: string;
  questions?: Question[];
}
export interface Topic extends Row {
  title: string;
  content: string;
  materials: Activity[];
  assignments: Activity[];
  tests: Activity[];
}
export interface Week extends Row {
  title: string;
  number: number;
  topics: Topic[];
}
export interface Tree {
  course: Row;
  version: Row;
  weeks: Week[];
  scheme: Row | null;
  components: Row[];
}
export interface Attempt extends Row {
  questions: Question[];
  answers: Record<string, string[]>;
  expires_at: string;
  server_time: string;
  status: string;
  score: string | null;
}
export interface Progress {
  percent: number;
  completed: number;
  total: number;
  materials: string[];
  completed_topics: string[];
  read_topics: string[];
}
