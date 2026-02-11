import { useEffect, useState } from 'react';
import Header from '@/components/layout/Header';
import WorkflowCanvas from '@/components/canvas/WorkflowCanvas';
import ExecutionPanel from '@/components/canvas/ExecutionPanel';
import { useExecutionStream } from '@/hooks/useExecutionStream';
import { useCanvasMetadata } from '@/hooks/useCanvasMetadata';
import { fetchJson } from '@/lib/api';
import type { GraphDefinition, NodeDefinition, EdgeDefinition } from '@/types/graph';
import type { Workflow } from '@/types/workflows';

interface WorkflowListResponse {
  workflows: Workflow[];
  count: number;
}

interface AgentConfig {
  agent_id: string;
  model_id: string;
  channel_id: string;
}

/** Convert a Workflow definition into a GraphDefinition for the canvas. */
function workflowToGraphDef(
  workflow: Workflow,
  agentMap: Record<string, AgentConfig>,
): GraphDefinition {
  const nodes: NodeDefinition[] = [];
  const edges: EdgeDefinition[] = [];
  let hasEndTarget = false;

  for (const node of workflow.definition.nodes) {
    const agent = agentMap[node.agent_id];
    const modelId = agent?.model_id ?? '';
    let modelProvider = '';
    if (modelId.includes('gpt') || modelId.includes('o1')) modelProvider = 'openai';
    else if (
      modelId.includes('claude') ||
      modelId.includes('opus') ||
      modelId.includes('sonnet') ||
      modelId.includes('haiku')
    )
      modelProvider = 'anthropic';
    else if (modelId) modelProvider = 'ollama';

    nodes.push({
      id: node.node_id,
      label: node.agent_id
        .replace(/^af_/, '')
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase()),
      node_type: node.is_entry_point
        ? 'orchestrator'
        : node.is_error_handler
          ? 'error_handler'
          : 'agent',
      model_id: modelId || undefined,
      model_provider: modelProvider || undefined,
      position: node.position,
    });
  }

  for (const edge of workflow.definition.edges) {
    if (edge.target_node_id === '__end__') hasEndTarget = true;
    edges.push({
      id: edge.edge_id,
      source: edge.source_node_id,
      target: edge.target_node_id,
      conditional: edge.edge_type === 'conditional',
      label: edge.label || undefined,
    });
  }

  if (hasEndTarget) {
    nodes.push({ id: '__end__', label: 'END', node_type: 'terminal' });
  }

  return { nodes, edges, subgraphs: {} };
}

export default function WorkflowPage() {
  const [graphDef, setGraphDef] = useState<GraphDefinition | null>(null);
  const [defaultGraphDef, setDefaultGraphDef] = useState<GraphDefinition | null>(null);
  const [showSub, setShowSub] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [agentMap, setAgentMap] = useState<Record<string, AgentConfig>>({});
  const { activeNodes, events, connected, clearEvents } = useExecutionStream();
  const metadata = useCanvasMetadata();

  // Load workflows list + agents + default graph on mount
  useEffect(() => {
    fetchJson<WorkflowListResponse>('/api/workflows')
      .then((res) => {
        const wfs = res?.workflows ?? [];
        setWorkflows(wfs);
        const active = wfs.find((w) => w.is_active);
        if (active) setSelectedWorkflowId(active.workflow_id);
      })
      .catch(() => {});

    fetchJson<GraphDefinition>('/api/graph/definition')
      .then((g) => {
        setDefaultGraphDef(g);
        setGraphDef(g);
      })
      .catch(() => console.warn('Backend unreachable, using empty graph'));

    fetchJson<{ agents: AgentConfig[] }>('/api/agents')
      .then((res) => {
        const map: Record<string, AgentConfig> = {};
        for (const a of res?.agents ?? []) map[a.agent_id] = a;
        setAgentMap(map);
      })
      .catch(() => {});
  }, []);

  // Update graph when selected workflow changes
  useEffect(() => {
    if (!selectedWorkflowId) return;
    const wf = workflows.find((w) => w.workflow_id === selectedWorkflowId);
    if (!wf) return;

    if (wf.workflow_id === 'default') {
      setGraphDef(defaultGraphDef);
    } else {
      setGraphDef(workflowToGraphDef(wf, agentMap));
    }
  }, [selectedWorkflowId, workflows, defaultGraphDef, agentMap]);

  const selectedWorkflow = workflows.find((w) => w.workflow_id === selectedWorkflowId);

  return (
    <div className="flex flex-col h-full">
      <Header title="Canvas" subtitle="Agent orchestration graph" />
      <div className="flex items-center gap-3 px-4 py-2 bg-[var(--color-bg-card)] border-b border-[var(--color-border)]">
        {/* Workflow selector */}
        <select
          value={selectedWorkflowId ?? ''}
          onChange={(e) => {
            setSelectedWorkflowId(e.target.value);
            setEditMode(false);
          }}
          className="text-xs bg-[var(--color-bg)] text-[var(--color-text)] border border-[var(--color-border)] rounded px-2 py-1 outline-none"
        >
          {workflows.map((w) => (
            <option key={w.workflow_id} value={w.workflow_id}>
              {w.display_name} (v{w.version}){w.is_active ? ' \u2713' : ''}
            </option>
          ))}
        </select>

        {/* Edit/View toggle — only for non-builtin workflows */}
        {selectedWorkflow && !selectedWorkflow.is_builtin && (
          <button
            onClick={() => setEditMode(!editMode)}
            className={`text-xs px-2.5 py-1 rounded border transition-colors ${
              editMode
                ? 'border-[var(--color-accent)] text-[var(--color-accent)] bg-[var(--color-accent)]/10'
                : 'border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
            }`}
          >
            {editMode ? 'Editing' : 'Edit'}
          </button>
        )}

        <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] cursor-pointer">
          <input
            type="checkbox"
            checked={showSub}
            onChange={(e) => setShowSub(e.target.checked)}
            className="accent-[var(--color-accent)]"
          />
          Show sub-agents
        </label>

        <span
          className="ml-auto flex items-center gap-1.5 text-xs"
          style={{ color: connected ? '#22c55e' : 'var(--color-text-muted)' }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: connected ? '#22c55e' : '#ef4444',
              display: 'inline-block',
            }}
          />
          {connected ? 'Live' : 'Connecting...'}
        </span>
      </div>
      {/* Workflow description panel */}
      {selectedWorkflow?.description && (
        <div className="px-4 py-2 bg-[var(--color-bg)] border-b border-[var(--color-border)]">
          <div className="flex items-start gap-2 text-xs text-[var(--color-text-muted)]">
            <span className="shrink-0 mt-0.5 opacity-60">&#128196;</span>
            <span>{selectedWorkflow.description}</span>
          </div>
        </div>
      )}
      <div className="flex flex-1 min-h-0">
        <div className="flex-1">
          <WorkflowCanvas
            graphDef={graphDef}
            showSubGraph={showSub}
            activeNodes={activeNodes}
            metadata={metadata}
            editable={editMode}
          />
        </div>
        <ExecutionPanel
          events={events}
          activeNodes={activeNodes}
          connected={connected}
          onClearEvents={clearEvents}
        />
      </div>
    </div>
  );
}
