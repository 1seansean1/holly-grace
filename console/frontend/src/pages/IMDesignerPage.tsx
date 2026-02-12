import { useEffect, useState, useCallback } from 'react';
import Header from '@/components/layout/Header';
import { fetchJson, postJson, deleteJson } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface IMWorkspaceSummary {
  workspace_id: string;
  raw_intent: string;
  stage: string;
  version: number;
  created_at: string;
  updated_at: string;
}

interface IMWorkspaceDetail {
  workspace_id: string;
  stage: string;
  version: number;
  raw_intent: string;
  created_at: string | null;
  updated_at: string | null;
  goal_tuple: Record<string, unknown>;
  predicate_count: number;
  block_count: number;
  coupling_locked: boolean;
  codimension: number | null;
  regime: string | null;
  verdict: string | null;
  audit_trail: AuditEntry[];
}

interface AuditEntry {
  stage: string;
  tool_name: string;
  input_summary: string;
  output_summary: string;
  created_at: string;
}

interface PipelineResult {
  workspace_id: string;
  verdict?: string;
  stage?: string;
  error?: string;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STAGES = [
  { key: 'created', label: 'Created', step: 0 },
  { key: 'goal_parsed', label: 'Goal Parsed', step: 1 },
  { key: 'predicates_generated', label: 'Predicates', step: 2 },
  { key: 'coupling_built', label: 'Coupling', step: 3 },
  { key: 'codimension_estimated', label: 'Codimension', step: 4 },
  { key: 'rank_budgeted', label: 'Rank Budget', step: 5 },
  { key: 'memory_designed', label: 'Memory', step: 6 },
  { key: 'agents_synthesized', label: 'Agents', step: 7 },
  { key: 'workflow_synthesized', label: 'Workflow', step: 8 },
  { key: 'feasibility_validated', label: 'Feasibility', step: 9 },
];

const STAGE_INDEX: Record<string, number> = {};
STAGES.forEach((s) => { STAGE_INDEX[s.key] = s.step; });

const REGIME_COLORS: Record<string, string> = {
  simple: 'bg-green-900/40 text-green-400',
  medium: 'bg-yellow-900/40 text-yellow-400',
  complex: 'bg-red-900/40 text-red-400',
};

const VERDICT_COLORS: Record<string, string> = {
  feasible: 'bg-green-900/40 text-green-400',
  infeasible: 'bg-red-900/40 text-red-400',
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PipelineProgress({ stage }: { stage: string }) {
  const currentStep = STAGE_INDEX[stage] ?? 0;
  return (
    <div className="flex items-center gap-1">
      {STAGES.map((s) => (
        <div key={s.key} className="flex items-center">
          <div
            className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-mono transition-colors ${
              s.step < currentStep
                ? 'bg-green-600 text-white'
                : s.step === currentStep
                ? 'bg-[var(--color-accent)] text-white'
                : 'bg-[var(--color-bg-hover)] text-[var(--color-text-muted)]'
            }`}
            title={s.label}
          >
            {s.step}
          </div>
          {s.step < STAGES.length - 1 && (
            <div
              className={`w-3 h-0.5 ${
                s.step < currentStep ? 'bg-green-600' : 'bg-[var(--color-border)]'
              }`}
            />
          )}
        </div>
      ))}
    </div>
  );
}

function WorkspaceCard({
  ws,
  selected,
  onSelect,
  onDelete,
}: {
  ws: IMWorkspaceSummary;
  selected: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      className={`rounded-lg border p-3 cursor-pointer transition-colors ${
        selected
          ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10'
          : 'border-[var(--color-border)] bg-[var(--color-bg-card)] hover:border-[var(--color-accent)]/50'
      }`}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium line-clamp-2">{ws.raw_intent}</p>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          className="text-[var(--color-text-muted)] hover:text-red-400 text-xs shrink-0"
          title="Delete workspace"
        >
          ×
        </button>
      </div>
      <div className="mt-2">
        <PipelineProgress stage={ws.stage} />
      </div>
      <div className="mt-1 flex items-center gap-2 text-[10px] text-[var(--color-text-muted)] font-mono">
        <span>{ws.workspace_id.slice(0, 8)}</span>
        <span>v{ws.version}</span>
        <span>{ws.updated_at ? new Date(ws.updated_at).toLocaleDateString() : ''}</span>
      </div>
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: string | number | null; color?: string }) {
  return (
    <div className="bg-[var(--color-bg-card)] rounded-lg border border-[var(--color-border)] p-3">
      <div className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider">{label}</div>
      <div className={`text-lg font-mono mt-1 ${color ?? 'text-[var(--color-text)]'}`}>
        {value ?? '---'}
      </div>
    </div>
  );
}

function AuditTrail({ trail }: { trail: AuditEntry[] }) {
  if (!trail.length) return null;
  return (
    <div className="bg-[var(--color-bg-card)] rounded-lg border border-[var(--color-border)] overflow-hidden">
      <div className="p-3 border-b border-[var(--color-border)]">
        <h3 className="text-sm font-semibold">Audit Trail ({trail.length} events)</h3>
      </div>
      <div className="overflow-auto max-h-[300px]">
        <table className="w-full text-xs">
          <thead className="bg-[var(--color-bg-hover)] sticky top-0">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-[var(--color-text-muted)]">Stage</th>
              <th className="px-3 py-2 text-left font-medium text-[var(--color-text-muted)]">Tool</th>
              <th className="px-3 py-2 text-left font-medium text-[var(--color-text-muted)]">Input</th>
              <th className="px-3 py-2 text-left font-medium text-[var(--color-text-muted)]">Output</th>
              <th className="px-3 py-2 text-left font-medium text-[var(--color-text-muted)]">Time</th>
            </tr>
          </thead>
          <tbody>
            {trail.map((e, i) => (
              <tr key={i} className="border-t border-[var(--color-border)] hover:bg-[var(--color-bg-hover)]">
                <td className="px-3 py-1.5 font-mono text-[var(--color-accent)]">{e.stage}</td>
                <td className="px-3 py-1.5">{e.tool_name}</td>
                <td className="px-3 py-1.5 text-[var(--color-text-muted)] max-w-[200px] truncate">{e.input_summary}</td>
                <td className="px-3 py-1.5 text-[var(--color-text-muted)] max-w-[200px] truncate">{e.output_summary}</td>
                <td className="px-3 py-1.5 text-[var(--color-text-muted)]">
                  {e.created_at ? new Date(e.created_at).toLocaleTimeString() : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function IMDesignerPage() {
  const [workspaces, setWorkspaces] = useState<IMWorkspaceSummary[]>([]);
  const [selected, setSelected] = useState<IMWorkspaceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newIntent, setNewIntent] = useState('');
  const [running, setRunning] = useState(false);
  const [pipelineLog, setPipelineLog] = useState<string[]>([]);

  const loadWorkspaces = useCallback(async () => {
    try {
      const data = await fetchJson<{ workspaces: IMWorkspaceSummary[] }>('/api/im/workspaces');
      setWorkspaces(data.workspaces ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load workspaces');
    }
    setLoading(false);
  }, []);

  const loadDetail = useCallback(async (id: string) => {
    try {
      const data = await fetchJson<IMWorkspaceDetail>(`/api/im/workspaces/${id}`);
      setSelected(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load workspace');
    }
  }, []);

  useEffect(() => {
    loadWorkspaces();
    const interval = setInterval(loadWorkspaces, 15000);
    return () => clearInterval(interval);
  }, [loadWorkspaces]);

  const handleRunPipeline = async () => {
    if (!newIntent.trim()) return;
    setRunning(true);
    setError(null);
    setPipelineLog(['Starting full pipeline...']);

    try {
      const result = await postJson<PipelineResult>('/api/im/pipeline/full', {
        raw_intent: newIntent.trim(),
      });

      if (result.error) {
        setError(result.error);
        setPipelineLog((prev) => [...prev, `Error: ${result.error}`]);
      } else {
        setPipelineLog((prev) => [
          ...prev,
          `Pipeline complete: ${result.verdict ?? 'unknown'}`,
          `Workspace: ${result.workspace_id}`,
        ]);
        setNewIntent('');
        await loadWorkspaces();
        if (result.workspace_id) {
          await loadDetail(result.workspace_id);
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Pipeline failed');
      setPipelineLog((prev) => [...prev, `Failed: ${e}`]);
    }
    setRunning(false);
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteJson(`/api/im/workspaces/${id}`);
      if (selected?.workspace_id === id) setSelected(null);
      await loadWorkspaces();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed');
    }
  };

  const handleStepRun = async (step: string) => {
    if (!selected) return;
    setRunning(true);
    setError(null);
    try {
      const url = `/api/im/pipeline/${selected.workspace_id}/${step}`;
      const result = await postJson<PipelineResult>(url, {});
      if (result.error) {
        setError(result.error);
      } else {
        await loadDetail(selected.workspace_id);
        await loadWorkspaces();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Step failed');
    }
    setRunning(false);
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <Header
        title="IM Designer"
        subtitle="Architecture Selection Rule — Informational Monism Pipeline"
        right={
          <button
            onClick={loadWorkspaces}
            className="text-xs text-[var(--color-accent)] hover:underline"
          >
            Refresh
          </button>
        }
      />

      <div className="flex-1 overflow-auto p-4">
        {error && (
          <div className="bg-red-900/30 border border-red-700/50 text-red-300 rounded-lg px-4 py-2 text-sm mb-4">
            {error}
            <button
              onClick={() => setError(null)}
              className="ml-2 text-red-400 hover:text-red-300"
            >
              ×
            </button>
          </div>
        )}

        {/* New workspace input */}
        <div className="bg-[var(--color-bg-card)] rounded-lg border border-[var(--color-border)] p-4 mb-4">
          <h3 className="text-sm font-semibold mb-2">New Architecture Design</h3>
          <div className="flex gap-2">
            <input
              type="text"
              value={newIntent}
              onChange={(e) => setNewIntent(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !running && handleRunPipeline()}
              placeholder="Describe your system goal in natural language..."
              className="flex-1 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)]"
              disabled={running}
            />
            <button
              onClick={handleRunPipeline}
              disabled={running || !newIntent.trim()}
              className="px-4 py-2 text-sm rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-40 transition-colors whitespace-nowrap"
            >
              {running ? 'Running...' : 'Run Pipeline'}
            </button>
          </div>
          {pipelineLog.length > 0 && (
            <div className="mt-2 text-xs font-mono text-[var(--color-text-muted)] space-y-0.5">
              {pipelineLog.map((l, i) => (
                <div key={i}>{l}</div>
              ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Left: workspace list */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-[var(--color-text-muted)] mb-2">
              Workspaces ({workspaces.length})
            </h3>
            {loading ? (
              <div className="text-sm text-[var(--color-text-muted)]">Loading...</div>
            ) : workspaces.length === 0 ? (
              <div className="text-sm text-[var(--color-text-muted)]">
                No workspaces yet. Enter a goal above to start.
              </div>
            ) : (
              workspaces.map((ws) => (
                <WorkspaceCard
                  key={ws.workspace_id}
                  ws={ws}
                  selected={selected?.workspace_id === ws.workspace_id}
                  onSelect={() => loadDetail(ws.workspace_id)}
                  onDelete={() => handleDelete(ws.workspace_id)}
                />
              ))
            )}
          </div>

          {/* Right: detail view */}
          <div className="lg:col-span-2 space-y-4">
            {!selected ? (
              <div className="bg-[var(--color-bg-card)] rounded-lg border border-[var(--color-border)] p-8 text-center text-sm text-[var(--color-text-muted)]">
                Select a workspace to view details, or run a new pipeline above.
              </div>
            ) : (
              <>
                {/* Header stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <StatBox label="Codimension" value={selected.codimension} color="text-[var(--color-accent)]" />
                  <StatBox
                    label="Regime"
                    value={selected.regime?.toUpperCase() ?? null}
                    color={selected.regime ? 'text-yellow-400' : undefined}
                  />
                  <StatBox
                    label="Verdict"
                    value={selected.verdict?.toUpperCase() ?? null}
                    color={selected.verdict === 'feasible' ? 'text-green-400' : selected.verdict === 'infeasible' ? 'text-red-400' : undefined}
                  />
                  <StatBox label="Predicates" value={selected.predicate_count} />
                </div>

                {/* Pipeline progress */}
                <div className="bg-[var(--color-bg-card)] rounded-lg border border-[var(--color-border)] p-3">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold">Pipeline Progress</h3>
                    <span className="text-xs text-[var(--color-text-muted)] font-mono">
                      Stage: {selected.stage}
                    </span>
                  </div>
                  <PipelineProgress stage={selected.stage} />

                  {/* Step-by-step buttons */}
                  <div className="mt-3 flex flex-wrap gap-1">
                    {[
                      { step: 'predicates', label: 'Predicates', requires: 'goal_parsed' },
                      { step: 'coupling', label: 'Coupling', requires: 'predicates_generated' },
                      { step: 'codimension', label: 'Codimension', requires: 'coupling_built' },
                      { step: 'rank-budget', label: 'Rank Budget', requires: 'codimension_estimated' },
                      { step: 'memory', label: 'Memory', requires: 'rank_budgeted' },
                      { step: 'agents', label: 'Agents', requires: 'memory_designed' },
                      { step: 'workflow', label: 'Workflow', requires: 'agents_synthesized' },
                      { step: 'feasibility', label: 'Feasibility', requires: 'workflow_synthesized' },
                    ].map(({ step, label, requires }) => {
                      const current = STAGE_INDEX[selected.stage] ?? 0;
                      const needed = STAGE_INDEX[requires] ?? 0;
                      const enabled = current >= needed;
                      return (
                        <button
                          key={step}
                          onClick={() => handleStepRun(step)}
                          disabled={!enabled || running}
                          className={`px-2 py-1 text-[10px] rounded font-mono transition-colors ${
                            enabled
                              ? 'bg-[var(--color-bg-hover)] text-[var(--color-text)] hover:bg-[var(--color-accent)] hover:text-white'
                              : 'bg-[var(--color-bg)] text-[var(--color-text-muted)] opacity-40 cursor-not-allowed'
                          }`}
                        >
                          {label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Goal tuple */}
                {selected.goal_tuple && Object.keys(selected.goal_tuple).length > 0 && (
                  <div className="bg-[var(--color-bg-card)] rounded-lg border border-[var(--color-border)] p-3">
                    <h3 className="text-sm font-semibold mb-2">Goal Tuple</h3>
                    <pre className="text-xs font-mono text-[var(--color-text-muted)] overflow-auto max-h-[200px] whitespace-pre-wrap">
                      {JSON.stringify(selected.goal_tuple, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Regime + verdict badges */}
                <div className="flex flex-wrap gap-2">
                  {selected.regime && (
                    <span className={`px-3 py-1 rounded text-xs font-mono ${REGIME_COLORS[selected.regime] ?? ''}`}>
                      Regime: {selected.regime.toUpperCase()}
                    </span>
                  )}
                  {selected.verdict && (
                    <span className={`px-3 py-1 rounded text-xs font-mono ${VERDICT_COLORS[selected.verdict] ?? ''}`}>
                      Verdict: {selected.verdict.toUpperCase()}
                    </span>
                  )}
                  {selected.coupling_locked && (
                    <span className="px-3 py-1 rounded text-xs font-mono bg-blue-900/40 text-blue-400">
                      Coupling Locked
                    </span>
                  )}
                  <span className="px-3 py-1 rounded text-xs font-mono bg-[var(--color-bg-hover)] text-[var(--color-text-muted)]">
                    {selected.predicate_count} predicates / {selected.block_count} blocks
                  </span>
                </div>

                {/* Audit trail */}
                <AuditTrail trail={selected.audit_trail ?? []} />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
