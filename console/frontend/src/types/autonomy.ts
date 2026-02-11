export interface AutonomyStatus {
  status: string;
  detail?: string;
  updated_at?: string;
  running?: boolean;
  paused?: boolean;
  tasks_completed?: number;
  consecutive_errors?: number;
  idle_sweeps?: number;
  monitor_interval?: number;
  queue_depth?: number;
}

export interface QueuedTask {
  id: string;
  objective: string;
  priority: string;
  type: string;
  metadata: Record<string, unknown>;
  submitted_at: string;
}

export interface AuditLog {
  id: number;
  task_id: string;
  task_type: string;
  objective: string;
  priority: string;
  outcome: string;
  error_message: string;
  started_at: string;
  finished_at: string;
  duration_sec: number;
  metadata: Record<string, unknown>;
}
