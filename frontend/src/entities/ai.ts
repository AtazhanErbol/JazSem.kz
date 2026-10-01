export interface SourceDocument {
  id: string;
  course: string;
  filename: string;
  file: boolean;
  processing_status: "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";
  error: string;
  excluded: boolean;
}
export interface AIJob {
  id: string;
  course: string;
  status: "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED" | "CANCELLED";
  progress: number;
  current_step: string;
  error: string;
  created_at: string;
  estimated_cost: string | null;
}
export interface AIDraft<T> {
  id: string;
  job: string;
  data: T;
  imported_version: string | null;
}
