import { useEffect, useState } from 'react';
import Header from '@/components/layout/Header';
import WorkflowCanvas from '@/components/canvas/WorkflowCanvas';
import ExecutionPanel from '@/components/canvas/ExecutionPanel';
import { useExecutionStream } from '@/hooks/useExecutionStream';
import { useCanvasMetadata } from '@/hooks/useCanvasMetadata';
import { fetchJson } from '@/lib/api';
import type { GraphDefinition } from '@/types/graph';
import type { Workflow } from '@/types/workflows';

interface WorkflowListResponse {
  workflows: Workflow[];
  count: number;
}

export default function WorkflowPage() {
  const [graphDef, setGraphDef] = useState<GraphDefinition | null>(null);
  const [showSub, setShowSub] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const { activeNodes, events, connected, clearEvents } = useExecutionStream();
  const metadata = useCanvasMetadata();

  // Load workflows list
  useEffect(() => {
    fetchJson<WorkflowListResponse>('/api/workflows')
      .then((res) => {
        setWorkflows(res.workflows);
        const active = res.workflows.find((w) => w.is_active);
        if (active) setSelectedWorkflowId(active.workflow_id);
      })
      .catch(() => {});
  }, []);

  // Load graph definition
  useEffect(() => {
    fetchJson<GraphDefinition>('/api/graph/definition')
      .then(setGraphDef)
      .catch(() => {
        console.warn('Backend unreachable, using empty graph');
      });
  }, []);

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
