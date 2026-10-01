import type { Progress } from "./types";

export interface AssignmentDetails {
  id: string;
  title: string;
  instructions: string;
  description: string;
  deadline: string | null;
  max_score: number;
  allow_late_submission: boolean;
  course_id: string;
  course_version_id: string;
}
export interface SubmissionDetails {
  id: string;
  assignment: string;
  assignment_title: string;
  student_name: string;
  attempt_number: number;
  text_answer: string;
  teacher_comment: string;
  max_score: number;
  score: string | null;
  submitted_at: string;
  graded_at: string | null;
  status:
    | "SUBMITTED"
    | "RESUBMITTED"
    | "UNDER_REVIEW"
    | "REVISION_REQUESTED"
    | "GRADED";
}
export interface TestInfo {
  id: string;
  title: string;
  description: string;
  course_id: string;
  max_attempts: number;
  time_limit_minutes: number;
  available_from: string | null;
  available_until: string | null;
}
export interface AttemptSummary {
  id: string;
  attempt_number: number;
  score: string | null;
  status: "IN_PROGRESS" | "GRADED" | "EXPIRED";
}
export interface EnrollmentSummary {
  id: string;
  course: string;
  course_version: string;
  course_title: string;
  student_name: string;
  status: string;
  progress: Progress;
  grades: {
    score: number;
    components: { kind: string; weight: number; score: number }[];
  };
}
export interface GroupDetails {
  id: string;
  name: string;
  teacher: string;
  status: string;
}
export interface GroupMember {
  id: string;
  student: string;
  student_name: string;
  student_email: string;
}
export interface PrivateFile {
  id: string;
  original_filename: string;
  size: number;
}
