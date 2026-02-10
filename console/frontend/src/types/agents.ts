export interface AgentConfig {
  agent_id: string;
  channel_id: string;
  display_name: string;
  description: string;
  model_id: string;
  system_prompt: string;
  tool_ids: string[];
  is_builtin: boolean;
  version: number;
}

export interface AgentUpdatePayload {
  display_name?: string;
  description?: string;
  model_id?: string;
  system_prompt?: string;
  tool_ids?: string[];
  expected_version: number;
}

export interface AgentCreatePayload {
  agent_id: string;
  channel_id: string;
  display_name: string;
  description: string;
  model_id: string;
  system_prompt: string;
  tool_ids: string[];
}

export interface AgentVersion {
  agent_id: string;
  version: number;
  channel_id: string;
  display_name: string;
  description: string;
  model_id: string;
  system_prompt: string;
  tool_ids: string[];
  change_summary: string;
  created_at: string;
}

export interface ToolDefinition {
  tool_id: string;
  display_name: string;
  description: string;
  module_path: string;
  function_name: string;
  category: string;
}
