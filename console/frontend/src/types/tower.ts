/** Tower (Control Tower) type definitions. */

export interface TowerRun {
  run_id: string;
  workflow_id: string;
  status: 'queued' | 'running' | 'waiting_approval' | 'completed' | 'failed' | 'cancelled';
  priority: number;
  run_name: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  last_checkpoint_id: string | null;
  last_ticket_id: number | null;
  last_error: string | null;
  metadata: Record<string, unknown> | null;
  created_by: string | null;
}

export interface TowerTicket {
  id: number;
  run_id: string;
  ticket_type: string;
  risk_level: 'low' | 'medium' | 'high';
  status: 'pending' | 'approved' | 'rejected' | 'expired';
  proposed_action: Record<string, unknown>;
  context_pack: TowerContextPack;
  decision_payload: Record<string, unknown> | null;
  checkpoint_id: string | null;
  interrupt_id: string | null;
  created_at: string;
  decided_at: string | null;
  decided_by: string | null;
  expires_at: string | null;
}

export interface TowerContextPack {
  tldr: string;
  why_stopped: string;
  proposed_action_preview?: string;
  impact?: string;
  risk_flags?: string[];
  options?: {
    approve?: boolean;
    approve_with_edits?: boolean;
    reject?: boolean;
  };
}

export interface TowerEvent {
  id: number;
  run_id: string;
  event_type: string;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface TowerSnapshot {
  values: Record<string, unknown>;
  next: string[];
  tasks: {
    id: string;
    name: string;
    interrupts: { id: string; value: unknown }[];
  }[];
}
