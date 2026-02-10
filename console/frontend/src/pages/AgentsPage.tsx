import { useEffect, useState, useCallback } from 'react';
import Header from '@/components/layout/Header';
import CreateAgentDialog from '@/components/agents/CreateAgentDialog';
import ToolSelector from '@/components/agents/ToolSelector';
import VersionHistory from '@/components/agents/VersionHistory';
import PerformanceTab from '@/components/agents/PerformanceTab';
import { fetchJson, postJson, putJson, deleteJson } from '@/lib/api';
import type {
  AgentConfig,
  AgentCreatePayload,
  AgentUpdatePayload,
  AgentVersion,
  ToolDefinition,
} from '@/types/agents';

const MODEL_OPTIONS = [
  { id: 'ollama_qwen', label: 'Ollama Qwen 2.5 3B', provider: 'ollama' },
  { id: 'gpt4o_mini', label: 'GPT-4o Mini', provider: 'openai' },
  { id: 'gpt4o', label: 'GPT-4o', provider: 'openai' },
  { id: 'claude_opus', label: 'Claude Opus 4.6', provider: 'anthropic' },
];

const PROVIDER_STYLES: Record<string, { bg: string; text: string }> = {
  ollama: { bg: 'bg-emerald-950/30', text: 'text-emerald-400' },
  openai: { bg: 'bg-violet-950/30', text: 'text-violet-400' },
  anthropic: { bg: 'bg-amber-950/30', text: 'text-amber-400' },
};

type EditorTab = 'config' | 'tools' | 'versions' | 'performance';

function getProvider(modelId: string): string {
  return MODEL_OPTIONS.find((m) => m.id === modelId)?.provider ?? 'unknown';
}

function getModelLabel(modelId: string): string {
  return MODEL_OPTIONS.find((m) => m.id === modelId)?.label ?? modelId;
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [selected, setSelected] = useState<AgentConfig | null>(null);
  const [draft, setDraft] = useState<Partial<AgentConfig>>({});
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const [loadingDefault, setLoadingDefault] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [versions, setVersions] = useState<AgentVersion[]>([]);
  const [rollingBack, setRollingBack] = useState(false);
  const [tab, setTab] = useState<EditorTab>('config');
  const [loadingList, setLoadingList] = useState(true);

  const loadAgents = useCallback(() => {
    setLoadingList(true);
    fetchJson<{ agents: AgentConfig[] }>('/api/agents')
      .then((d) => setAgents(d.agents ?? []))
      .catch(() => {})
      .finally(() => setLoadingList(false));
  }, []);

  const loadTools = useCallback(() => {
    fetchJson<{ tools: ToolDefinition[] }>('/api/tools')
      .then((d) => setTools(d.tools ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadAgents();
    loadTools();
  }, [loadAgents, loadTools]);

  const loadVersions = useCallback((agentId: string) => {
    fetchJson<{ versions: AgentVersion[] }>(`/api/agents/${agentId}/versions`)
      .then((d) => setVersions(d.versions ?? []))
      .catch(() => setVersions([]));
  }, []);

  const selectAgent = (agent: AgentConfig) => {
    setSelected(agent);
    setDraft({
      display_name: agent.display_name,
      description: agent.description,
      model_id: agent.model_id,
      system_prompt: agent.system_prompt,
      tool_ids: agent.tool_ids ?? [],
    });
    setToast(null);
    setTab('config');
    loadVersions(agent.agent_id);
  };

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    setToast(null);
    try {
      const payload: AgentUpdatePayload = {
        expected_version: selected.version,
      };
      if (draft.display_name !== selected.display_name) payload.display_name = draft.display_name;
      if (draft.description !== selected.description) payload.description = draft.description;
      if (draft.model_id !== selected.model_id) payload.model_id = draft.model_id;
      if (draft.system_prompt !== selected.system_prompt) payload.system_prompt = draft.system_prompt;
      if (JSON.stringify(draft.tool_ids) !== JSON.stringify(selected.tool_ids))
        payload.tool_ids = draft.tool_ids;

      const updated = await putJson<AgentConfig>(`/api/agents/${selected.agent_id}`, payload);
      setSelected(updated);
      setDraft({
        display_name: updated.display_name,
        description: updated.description,
        model_id: updated.model_id,
        system_prompt: updated.system_prompt,
        tool_ids: updated.tool_ids ?? [],
      });
      showToast(`Saved v${updated.version}`, true);
      loadAgents();
      loadVersions(selected.agent_id);
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Save failed', false);
    }
    setSaving(false);
  };

  const handleResetDefault = async () => {
    if (!selected) return;
    setLoadingDefault(true);
    try {
      const def = await fetchJson<AgentConfig>(`/api/agents/${selected.agent_id}/default`);
      setDraft({
        display_name: def.display_name,
        description: def.description,
        model_id: def.model_id,
        system_prompt: def.system_prompt,
        tool_ids: def.tool_ids ?? [],
      });
    } catch {
      showToast('Could not load default', false);
    }
    setLoadingDefault(false);
  };

  const handleCreate = async (payload: AgentCreatePayload) => {
    await postJson('/api/agents', payload);
    setShowCreate(false);
    loadAgents();
    showToast(`Created "${payload.display_name}"`, true);
  };

  const handleDelete = async () => {
    if (!selected || selected.is_builtin) return;
    if (!window.confirm(`Delete agent "${selected.display_name}"? This cannot be undone.`)) return;
    try {
      await deleteJson(`/api/agents/${selected.agent_id}`);
      setSelected(null);
      setDraft({});
      loadAgents();
      showToast('Agent deleted', true);
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Delete failed', false);
    }
  };

  const handleRollback = async (targetVersion: number) => {
    if (!selected) return;
    setRollingBack(true);
    try {
      const result = await postJson<AgentConfig>(`/api/agents/${selected.agent_id}/rollback`, {
        target_version: targetVersion,
      });
      setSelected(result);
      setDraft({
        display_name: result.display_name,
        description: result.description,
        model_id: result.model_id,
        system_prompt: result.system_prompt,
        tool_ids: result.tool_ids ?? [],
      });
      showToast(`Rolled back to v${targetVersion} → v${result.version}`, true);
      loadAgents();
      loadVersions(selected.agent_id);
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Rollback failed', false);
    }
    setRollingBack(false);
  };

  const hasChanges =
    selected &&
    (draft.display_name !== selected.display_name ||
      draft.description !== selected.description ||
      draft.model_id !== selected.model_id ||
      draft.system_prompt !== selected.system_prompt ||
      JSON.stringify(draft.tool_ids) !== JSON.stringify(selected.tool_ids));

  return (
    <div className="flex flex-col h-full">
      <Header title="Agents" subtitle="Configure agent prompts, models, and tools" />
      <div className="flex-1 flex overflow-hidden">
        {/* Agent list panel */}
        <div className="w-72 shrink-0 border-r border-[var(--color-border)] overflow-auto p-3 space-y-2">
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs text-[var(--color-text-muted)] font-semibold uppercase tracking-wider">
              {loadingList ? 'Loading...' : `${agents.length} agents`}
            </div>
            <button
              onClick={() => setShowCreate(true)}
              className="px-2 py-1 text-[10px] font-semibold rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 transition-colors"
            >
              + New
            </button>
          </div>
          {agents.map((agent) => {
            const provider = getProvider(agent.model_id);
            const style = PROVIDER_STYLES[provider] ?? { bg: 'bg-gray-950/30', text: 'text-gray-400' };
            const isSelected = selected?.agent_id === agent.agent_id;
            return (
              <button
                key={agent.agent_id}
                onClick={() => selectAgent(agent)}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  isSelected
                    ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10'
                    : 'border-[var(--color-border)] bg-[var(--color-bg-card)] hover:border-[var(--color-text-muted)]'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-semibold text-[var(--color-text)]">
                    {agent.display_name}
                  </span>
                  <div className="flex items-center gap-1">
                    {agent.is_builtin && (
                      <span className="text-[8px] px-1 py-0.5 rounded bg-[var(--color-bg-hover)] text-[var(--color-text-muted)]">
                        built-in
                      </span>
                    )}
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--color-bg-hover)] text-[var(--color-text-muted)]">
                      {agent.channel_id}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span
                    className={`inline-flex items-center text-[10px] px-1.5 py-0.5 rounded ${style.bg} ${style.text}`}
                  >
                    {getModelLabel(agent.model_id)}
                  </span>
                  {(agent.tool_ids?.length ?? 0) > 0 && (
                    <span className="text-[10px] text-[var(--color-text-muted)]">
                      {agent.tool_ids.length} tools
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-[var(--color-text-muted)] mt-1 line-clamp-2">
                  {agent.description}
                </div>
              </button>
            );
          })}
          {!loadingList && agents.length === 0 && (
            <div className="text-sm text-[var(--color-text-muted)] p-4 text-center">
              No agents found
            </div>
          )}
        </div>

        {/* Editor panel */}
        <div className="flex-1 overflow-auto p-6">
          {selected ? (
            <div className="max-w-3xl space-y-5">
              {/* Header with ID and version */}
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-semibold text-[var(--color-text)]">
                      {selected.display_name}
                    </h2>
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-[var(--color-bg-hover)] text-[var(--color-text-muted)]">
                      {selected.agent_id}
                    </span>
                    {selected.is_builtin && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950/30 text-emerald-400">
                        built-in
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-[var(--color-text-muted)]">
                    <span>Channel: {selected.channel_id}</span>
                    <span>Version: {selected.version}</span>
                    <span>Tools: {selected.tool_ids?.length ?? 0}</span>
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
                  {selected.is_builtin && (
                    <button
                      onClick={handleResetDefault}
                      disabled={loadingDefault}
                      className="px-3 py-1.5 text-xs rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-text-muted)] disabled:opacity-50 transition-colors"
                    >
                      {loadingDefault ? 'Loading...' : 'Reset to Default'}
                    </button>
                  )}
                  <button
                    onClick={handleSave}
                    disabled={saving || !hasChanges}
                    className="px-3 py-1.5 text-xs rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-40 transition-colors"
                  >
                    {saving ? 'Saving...' : 'Save'}
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

              {/* Tabs */}
              <div className="flex gap-1 border-b border-[var(--color-border)]">
                {(['config', 'tools', 'versions', 'performance'] as EditorTab[]).map((t) => (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    className={`px-3 py-2 text-xs font-semibold transition-colors border-b-2 -mb-px ${
                      tab === t
                        ? 'border-[var(--color-accent)] text-[var(--color-text)]'
                        : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
                    }`}
                  >
                    {t === 'config' ? 'Configuration' : t === 'tools' ? `Tools (${draft.tool_ids?.length ?? 0})` : t === 'versions' ? `Versions (${versions.length})` : 'Performance'}
                  </button>
                ))}
              </div>

              {/* Config tab */}
              {tab === 'config' && (
                <div className="space-y-5">
                  {/* Display Name */}
                  <div>
                    <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1">
                      Display Name
                    </label>
                    <input
                      type="text"
                      value={draft.display_name ?? ''}
                      onChange={(e) => setDraft({ ...draft, display_name: e.target.value })}
                      className="w-full px-3 py-2 text-sm rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none"
                    />
                  </div>

                  {/* Description */}
                  <div>
                    <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1">
                      Description
                    </label>
                    <input
                      type="text"
                      value={draft.description ?? ''}
                      onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                      className="w-full px-3 py-2 text-sm rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none"
                    />
                  </div>

                  {/* Model selector */}
                  <div>
                    <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1">
                      Model
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      {MODEL_OPTIONS.map((opt) => {
                        const isActive = draft.model_id === opt.id;
                        const style =
                          PROVIDER_STYLES[opt.provider] ?? { bg: 'bg-gray-950/30', text: 'text-gray-400' };
                        return (
                          <button
                            key={opt.id}
                            onClick={() => setDraft({ ...draft, model_id: opt.id })}
                            className={`p-2.5 rounded-lg border text-left transition-colors ${
                              isActive
                                ? `border-[var(--color-accent)] ${style.bg}`
                                : 'border-[var(--color-border)] bg-[var(--color-bg-card)] hover:border-[var(--color-text-muted)]'
                            }`}
                          >
                            <div
                              className={`text-xs font-semibold ${isActive ? style.text : 'text-[var(--color-text)]'}`}
                            >
                              {opt.label}
                            </div>
                            <div className="text-[10px] text-[var(--color-text-muted)]">{opt.provider}</div>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* System Prompt */}
                  <div>
                    <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1">
                      System Prompt
                    </label>
                    <textarea
                      value={draft.system_prompt ?? ''}
                      onChange={(e) => setDraft({ ...draft, system_prompt: e.target.value })}
                      rows={16}
                      className="w-full px-3 py-2 text-xs font-mono leading-relaxed rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none resize-y"
                    />
                    <div className="text-[10px] text-[var(--color-text-muted)] mt-1">
                      {(draft.system_prompt ?? '').length} characters
                    </div>
                  </div>
                </div>
              )}

              {/* Tools tab */}
              {tab === 'tools' && (
                <div>
                  <div className="text-xs text-[var(--color-text-muted)] mb-3">
                    Select which tools this agent can use. Tools are bound to the LLM via function calling.
                  </div>
                  <ToolSelector
                    tools={tools}
                    selectedIds={draft.tool_ids ?? []}
                    onChange={(ids) => setDraft({ ...draft, tool_ids: ids })}
                  />
                </div>
              )}

              {/* Versions tab */}
              {tab === 'versions' && (
                <div>
                  <div className="text-xs text-[var(--color-text-muted)] mb-3">
                    Each save creates a version snapshot. Rollback restores a previous version as a new version.
                  </div>
                  <VersionHistory
                    versions={versions}
                    currentVersion={selected.version}
                    onRollback={handleRollback}
                    rollingBack={rollingBack}
                  />
                </div>
              )}

              {/* Performance tab */}
              {tab === 'performance' && (
                <PerformanceTab
                  agentId={selected.agent_id}
                  currentVersion={selected.version}
                />
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-[var(--color-text-muted)]">
              Select an agent from the list to configure
            </div>
          )}
        </div>
      </div>

      {/* Create dialog */}
      {showCreate && (
        <CreateAgentDialog
          tools={tools}
          onSubmit={handleCreate}
          onClose={() => setShowCreate(false)}
        />
      )}
    </div>
  );
}
