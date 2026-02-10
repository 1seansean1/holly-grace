export interface NodeDefinition {
  id: string;
  label: string;
  node_type: 'orchestrator' | 'agent' | 'sub_agent' | 'error_handler' | 'terminal';
  model_id?: string;
  model_provider?: string;
  position?: { x: number; y: number };
}

export interface EdgeDefinition {
  id: string;
  source: string;
  target: string;
  conditional: boolean;
  label?: string;
}

export interface GraphDefinition {
  nodes: NodeDefinition[];
  edges: EdgeDefinition[];
  subgraphs: Record<string, GraphDefinition>;
}

export interface HealthCheck {
  status: string;
  service: string;
  checks: Record<string, boolean>;
  forge_console?: string;
  error?: string;
}

export interface SchedulerJob {
  id: string;
  next_run: string;
  trigger: string;
}
