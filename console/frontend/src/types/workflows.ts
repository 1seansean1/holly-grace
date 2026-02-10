export interface WorkflowNodeDef {
  node_id: string;
  agent_id: string;
  position: { x: number; y: number };
  is_entry_point: boolean;
  is_error_handler: boolean;
}

export interface RoutingCondition {
  target: string;
  type: string;
  field: string;
  value: string;
}

export interface WorkflowEdgeDef {
  edge_id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: 'direct' | 'conditional';
  conditions: RoutingCondition[] | null;
  label: string;
}

export interface WorkflowDefinitionBody {
  nodes: WorkflowNodeDef[];
  edges: WorkflowEdgeDef[];
  error_config: Record<string, unknown>;
}

export interface Workflow {
  workflow_id: string;
  display_name: string;
  description: string;
  version: number;
  is_active: boolean;
  is_builtin: boolean;
  definition: WorkflowDefinitionBody;
  created_at: string;
  updated_at: string;
}

export interface WorkflowCreatePayload {
  workflow_id: string;
  display_name: string;
  description?: string;
  definition: WorkflowDefinitionBody;
}

export interface WorkflowVersion {
  workflow_id: string;
  version: number;
  definition: WorkflowDefinitionBody;
  change_summary: string;
  created_at: string;
}
