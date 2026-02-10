import { useEffect, useState, useCallback } from 'react';
import Header from '@/components/layout/Header';
import { fetchJson, postJson, putJson, deleteJson } from '@/lib/api';
import type { Workflow, WorkflowVersion, WorkflowCreatePayload } from '@/types/workflows';

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

type DetailTab = 'overview' | 'definition' | 'versions';

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selected, setSelected] = useState<Workflow | null>(null);
  const [versions, setVersions] = useState<WorkflowVersion[]>([]);
  const [tab, setTab] = useState<DetailTab>('overview');
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [activating, setActivating] = useState(false);
  const [compiling, setCompiling] = useState(false);
  const [compileResult, setCompileResult] = useState<string | null>(null);
  const [rollingBack, setRollingBack] = useState(false);
  const [loadingList, setLoadingList] = useState(true);

  // Escape key to close create dialog
  useEffect(() => {
    if (!showCreate) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setShowCreate(false); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [showCreate]);

  // Create form state
  const [createId, setCreateId] = useState('');
  const [createName, setCreateName] = useState('');
  const [createDesc, setCreateDesc] = useState('');
  const [createError, setCreateError] = useState('');

  const loadWorkflows = useCallback(() => {
    setLoadingList(true);
    fetchJson<{ workflows: Workflow[] }>('/api/workflows')
      .then((d) => setWorkflows(d.workflows ?? []))
      .catch(() => {})
      .finally(() => setLoadingList(false));
  }, []);

  useEffect(() => {
    loadWorkflows();
  }, [loadWorkflows]);

  const loadVersions = useCallback((workflowId: string) => {
    fetchJson<{ versions: WorkflowVersion[] }>(`/api/workflows/${workflowId}/versions`)
      .then((d) => setVersions(d.versions ?? []))
      .catch(() => setVersions([]));
  }, []);

  const selectWorkflow = (wf: Workflow) => {
    setSelected(wf);
    setToast(null);
    setTab('overview');
    setCompileResult(null);
    loadVersions(wf.workflow_id);
  };

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const handleActivate = async () => {
    if (!selected) return;
    setActivating(true);
    try {
      await postJson(`/api/workflows/${selected.workflow_id}/activate`, {});
      showToast(`Activated "${selected.display_name}"`, true);
      loadWorkflows();
      // Refresh selected
      const updated = await fetchJson<Workflow>(`/api/workflows/${selected.workflow_id}`);
      setSelected(updated);
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Activation failed', false);
    }
    setActivating(false);
  };

  const handleCompile = async () => {
    if (!selected) return;
    setCompiling(true);
    setCompileResult(null);
    try {
      const result = await postJson<{ status: string; nodes?: number; edges?: number; error?: string }>(
        `/api/workflows/${selected.workflow_id}/compile`,
        {},
      );
      if (result.status === 'valid') {
        setCompileResult(`Valid: ${result.nodes} nodes, ${result.edges} edges`);
      } else {
        setCompileResult(`Error: ${result.error ?? 'Unknown error'}`);
      }
    } catch (e) {
      setCompileResult(e instanceof Error ? e.message : 'Compile failed');
    }
    setCompiling(false);
  };

  const handleDelete = async () => {
    if (!selected || selected.is_builtin) return;
    if (!window.confirm(`Delete workflow "${selected.display_name}"? This cannot be undone.`)) return;
    try {
      await deleteJson(`/api/workflows/${selected.workflow_id}`);
      setSelected(null);
      loadWorkflows();
      showToast('Workflow deleted', true);
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Delete failed', false);
    }
  };

  const handleRollback = async (targetVersion: number) => {
    if (!selected) return;
    setRollingBack(true);
    try {
      const result = await postJson<Workflow>(`/api/workflows/${selected.workflow_id}/rollback`, {
        target_version: targetVersion,
      });
      setSelected(result);
      showToast(`Rolled back to v${targetVersion} -> v${result.version}`, true);
      loadWorkflows();
      loadVersions(selected.workflow_id);
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Rollback failed', false);
    }
    setRollingBack(false);
  };

  const handleCreate = async () => {
    if (!createId || !createName) return;
    setCreateError('');
    try {
      const payload: WorkflowCreatePayload = {
        workflow_id: createId,
        display_name: createName,
        description: createDesc,
        definition: {
          nodes: [],
          edges: [],
          error_config: { max_retries: 3 },
        },
      };
      await postJson('/api/workflows', payload);
      setShowCreate(false);
      setCreateId('');
      setCreateName('');
      setCreateDesc('');
      loadWorkflows();
      showToast(`Created "${createName}"`, true);
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : 'Create failed');
    }
  };

  return (
    <div className="flex flex-col h-full">
      <Header title="Workflows" subtitle="Manage workflow definitions, compilation, and version history" />
      <div className="flex-1 flex overflow-hidden">
        {/* Workflow list panel */}
        <div className="w-72 shrink-0 border-r border-[var(--color-border)] overflow-auto p-3 space-y-2">
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs text-[var(--color-text-muted)] font-semibold uppercase tracking-wider">
              {loadingList ? 'Loading...' : `${workflows.length} workflows`}
            </div>
            <button
              onClick={() => setShowCreate(true)}
              className="px-2 py-1 text-[10px] font-semibold rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 transition-colors"
            >
              + New
            </button>
          </div>
          {workflows.map((wf) => {
            const isSelected = selected?.workflow_id === wf.workflow_id;
            return (
              <button
                key={wf.workflow_id}
                onClick={() => selectWorkflow(wf)}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  isSelected
                    ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10'
                    : 'border-[var(--color-border)] bg-[var(--color-bg-card)] hover:border-[var(--color-text-muted)]'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-semibold text-[var(--color-text)]">
                    {wf.display_name}
                  </span>
                  <div className="flex items-center gap-1">
                    {wf.is_active && (
                      <span className="text-[8px] px-1 py-0.5 rounded bg-emerald-950/30 text-emerald-400 font-semibold">
                        active
                      </span>
                    )}
                    {wf.is_builtin && (
                      <span className="text-[8px] px-1 py-0.5 rounded bg-[var(--color-bg-hover)] text-[var(--color-text-muted)]">
                        built-in
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--color-bg-hover)] text-[var(--color-text-muted)]">
                    v{wf.version}
                  </span>
                  <span className="text-[10px] text-[var(--color-text-muted)]">
                    {wf.definition?.nodes?.length ?? 0} nodes
                  </span>
                  <span className="text-[10px] text-[var(--color-text-muted)]">
                    {wf.definition?.edges?.length ?? 0} edges
                  </span>
                </div>
                <div className="text-[10px] text-[var(--color-text-muted)] mt-1 line-clamp-2">
                  {wf.description}
                </div>
              </button>
            );
          })}
          {!loadingList && workflows.length === 0 && (
            <div className="text-sm text-[var(--color-text-muted)] p-4 text-center">
              No workflows found
            </div>
          )}
        </div>

        {/* Detail panel */}
        <div className="flex-1 overflow-auto p-6">
          {selected ? (
            <div className="max-w-3xl space-y-5">
              {/* Header */}
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-semibold text-[var(--color-text)]">
                      {selected.display_name}
                    </h2>
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-[var(--color-bg-hover)] text-[var(--color-text-muted)]">
                      {selected.workflow_id}
                    </span>
                    {selected.is_active && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950/30 text-emerald-400 font-semibold">
                        active
                      </span>
                    )}
                    {selected.is_builtin && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-bg-hover)] text-[var(--color-text-muted)]">
                        built-in
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-[var(--color-text-muted)]">
                    <span>Version: {selected.version}</span>
                    <span>Nodes: {selected.definition?.nodes?.length ?? 0}</span>
                    <span>Edges: {selected.definition?.edges?.length ?? 0}</span>
                    <span>Updated: {formatDate(selected.updated_at)}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {!selected.is_builtin && (
                    <button
                      onClick={handleDelete}
                      className="px-3 py-1.5 text-xs rounded-lg border border-red-500/30 text-red-400 hover:bg-red-950/20 transition-colors"
                    >
                      Delete
                    </button>
                  )}
                  {!selected.is_active && (
                    <button
                      onClick={handleActivate}
                      disabled={activating}
                      className="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white hover:opacity-90 disabled:opacity-40 transition-colors"
                    >
                      {activating ? 'Activating...' : 'Activate'}
                    </button>
                  )}
                  <button
                    onClick={handleCompile}
                    disabled={compiling}
                    className="px-3 py-1.5 text-xs rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-40 transition-colors"
                  >
                    {compiling ? 'Compiling...' : 'Compile'}
                  </button>
                </div>
              </div>

              {/* Toast */}
              {toast && (
                <div
                  className={`text-xs px-3 py-2 rounded-lg ${
                    toast.ok
                      ? 'bg-emerald-950/30 text-emerald-400 border border-emerald-500/30'
                      : 'bg-red-950/30 text-red-400 border border-red-500/30'
                  }`}
                >
                  {toast.msg}
                </div>
              )}

              {/* Compile result */}
              {compileResult && (
                <div
                  className={`text-xs px-3 py-2 rounded-lg border ${
                    compileResult.startsWith('Valid')
                      ? 'bg-emerald-950/30 text-emerald-400 border-emerald-500/30'
                      : 'bg-red-950/30 text-red-400 border-red-500/30'
                  }`}
                >
                  Compile: {compileResult}
                </div>
              )}

              {/* Tabs */}
              <div className="flex gap-1 border-b border-[var(--color-border)]">
                {(['overview', 'definition', 'versions'] as DetailTab[]).map((t) => (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    className={`px-3 py-2 text-xs font-semibold transition-colors border-b-2 -mb-px ${
                      tab === t
                        ? 'border-[var(--color-accent)] text-[var(--color-text)]'
                        : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
                    }`}
                  >
                    {t === 'overview'
                      ? 'Overview'
                      : t === 'definition'
                        ? 'Definition'
                        : `Versions (${versions.length})`}
                  </button>
                ))}
              </div>

              {/* Overview tab */}
              {tab === 'overview' && (
                <div className="space-y-4">
                  <div className="text-xs text-[var(--color-text-muted)]">
                    {selected.description || 'No description.'}
                  </div>

                  {/* Nodes */}
                  <div>
                    <h3 className="text-xs font-semibold text-[var(--color-text)] mb-2">Nodes</h3>
                    <div className="space-y-1">
                      {(selected.definition?.nodes ?? []).map((node) => (
                        <div
                          key={node.node_id}
                          className="flex items-center gap-3 px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)]"
                        >
                          <span className="text-xs font-mono font-semibold text-[var(--color-text)]">
                            {node.node_id}
                          </span>
                          <span className="text-[10px] text-[var(--color-text-muted)]">
                            agent: {node.agent_id}
                          </span>
                          {node.is_entry_point && (
                            <span className="text-[8px] px-1 py-0.5 rounded bg-emerald-950/30 text-emerald-400">
                              entry
                            </span>
                          )}
                          {node.is_error_handler && (
                            <span className="text-[8px] px-1 py-0.5 rounded bg-red-950/30 text-red-400">
                              error handler
                            </span>
                          )}
                        </div>
                      ))}
                      {(selected.definition?.nodes ?? []).length === 0 && (
                        <div className="text-xs text-[var(--color-text-muted)] py-2 text-center">
                          No nodes defined
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Edges */}
                  <div>
                    <h3 className="text-xs font-semibold text-[var(--color-text)] mb-2">Edges</h3>
                    <div className="space-y-1">
                      {(selected.definition?.edges ?? []).map((edge) => (
                        <div
                          key={edge.edge_id}
                          className="flex items-center gap-3 px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)]"
                        >
                          <span className="text-xs font-mono text-[var(--color-text)]">
                            {edge.source_node_id}
                          </span>
                          <span className="text-[10px] text-[var(--color-text-muted)]">-&gt;</span>
                          <span className="text-xs font-mono text-[var(--color-text)]">
                            {edge.target_node_id}
                          </span>
                          <span
                            className={`text-[8px] px-1 py-0.5 rounded ${
                              edge.edge_type === 'conditional'
                                ? 'bg-violet-950/30 text-violet-400'
                                : 'bg-[var(--color-bg-hover)] text-[var(--color-text-muted)]'
                            }`}
                          >
                            {edge.edge_type}
                          </span>
                          {edge.conditions && (
                            <span className="text-[10px] text-[var(--color-text-muted)]">
                              {edge.conditions.length} conditions
                            </span>
                          )}
                        </div>
                      ))}
                      {(selected.definition?.edges ?? []).length === 0 && (
                        <div className="text-xs text-[var(--color-text-muted)] py-2 text-center">
                          No edges defined
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Definition tab (raw JSON) */}
              {tab === 'definition' && (
                <div>
                  <div className="text-xs text-[var(--color-text-muted)] mb-2">
                    Raw workflow definition JSON. Edit via the API for now.
                  </div>
                  <pre className="text-xs font-mono p-4 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] overflow-auto max-h-[600px] leading-relaxed">
                    {JSON.stringify(selected.definition, null, 2)}
                  </pre>
                </div>
              )}

              {/* Versions tab */}
              {tab === 'versions' && (
                <div>
                  <div className="text-xs text-[var(--color-text-muted)] mb-3">
                    Each update creates a version snapshot. Rollback restores a previous version.
                  </div>
                  {versions.length === 0 ? (
                    <div className="text-xs text-[var(--color-text-muted)] py-4 text-center">
                      No version history yet.
                    </div>
                  ) : (
                    <div className="space-y-1">
                      {versions.map((v) => {
                        const isCurrent = v.version === selected.version;
                        return (
                          <div
                            key={v.version}
                            className={`flex items-center gap-3 px-3 py-2 rounded-lg border transition-colors ${
                              isCurrent
                                ? 'border-[var(--color-accent)]/40 bg-[var(--color-accent)]/5'
                                : 'border-[var(--color-border)] bg-[var(--color-bg-card)]'
                            }`}
                          >
                            <div className="flex items-center justify-center w-7 h-7 rounded-full bg-[var(--color-bg-hover)] text-xs font-mono font-bold text-[var(--color-text-muted)] shrink-0">
                              v{v.version}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="text-xs text-[var(--color-text)]">
                                {v.definition?.nodes?.length ?? 0} nodes, {v.definition?.edges?.length ?? 0} edges
                              </div>
                              <div className="text-[10px] text-[var(--color-text-muted)]">
                                {formatDate(v.created_at)}
                                {v.change_summary && ` — ${v.change_summary}`}
                              </div>
                            </div>
                            <div className="shrink-0">
                              {isCurrent ? (
                                <span className="text-[10px] px-2 py-0.5 rounded bg-[var(--color-accent)]/20 text-[var(--color-accent)]">
                                  current
                                </span>
                              ) : (
                                <button
                                  onClick={() => handleRollback(v.version)}
                                  disabled={rollingBack}
                                  className="text-[10px] px-2 py-0.5 rounded border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-text-muted)] disabled:opacity-40 transition-colors"
                                >
                                  rollback
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-[var(--color-text-muted)]">
              Select a workflow from the list to view details
            </div>
          )}
        </div>
      </div>

      {/* Create dialog */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl w-[440px] p-6 space-y-4">
            <h3 className="text-sm font-semibold text-[var(--color-text)]">New Workflow</h3>

            <div>
              <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1">
                Workflow ID
              </label>
              <input
                type="text"
                value={createId}
                onChange={(e) => setCreateId(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                placeholder="my_workflow"
                className="w-full px-3 py-2 text-sm rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1">
                Display Name
              </label>
              <input
                type="text"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                placeholder="My Custom Workflow"
                className="w-full px-3 py-2 text-sm rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1">
                Description
              </label>
              <textarea
                value={createDesc}
                onChange={(e) => setCreateDesc(e.target.value)}
                rows={3}
                placeholder="Describe what this workflow does..."
                className="w-full px-3 py-2 text-xs rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none resize-y"
              />
            </div>

            <div className="text-[10px] text-[var(--color-text-muted)]">
              The workflow will be created with an empty definition. Add nodes and edges via the API or canvas editor.
            </div>

            {createError && (
              <div className="text-xs px-3 py-2 rounded-lg bg-red-950/30 text-red-400 border border-red-500/30">
                {createError}
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowCreate(false);
                  setCreateId('');
                  setCreateName('');
                  setCreateDesc('');
                  setCreateError('');
                }}
                className="px-4 py-1.5 text-xs rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={!createId || !createName}
                className="px-4 py-1.5 text-xs rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-40 transition-colors"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
