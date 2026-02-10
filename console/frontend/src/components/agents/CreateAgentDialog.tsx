import { useState, useEffect } from 'react';
import type { AgentCreatePayload, ToolDefinition } from '@/types/agents';

const MODEL_OPTIONS = [
  { id: 'ollama_qwen', label: 'Ollama Qwen 2.5 3B', provider: 'ollama' },
  { id: 'gpt4o_mini', label: 'GPT-4o Mini', provider: 'openai' },
  { id: 'gpt4o', label: 'GPT-4o', provider: 'openai' },
  { id: 'claude_opus', label: 'Claude Opus 4.6', provider: 'anthropic' },
];

interface Props {
  tools: ToolDefinition[];
  onSubmit: (payload: AgentCreatePayload) => Promise<void>;
  onClose: () => void;
}

export default function CreateAgentDialog({ tools, onSubmit, onClose }: Props) {
  const [form, setForm] = useState<AgentCreatePayload>({
    agent_id: '',
    channel_id: '',
    display_name: '',
    description: '',
    model_id: 'gpt4o_mini',
    system_prompt: '',
    tool_ids: [],
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  const handleSubmit = async () => {
    if (!form.agent_id || !form.display_name || !form.model_id) {
      setError('Agent ID, display name, and model are required');
      return;
    }
    // Auto-generate channel_id if not provided
    const payload = {
      ...form,
      channel_id: form.channel_id || `K${Date.now() % 1000}`,
    };
    setSubmitting(true);
    setError('');
    try {
      await onSubmit(payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Create failed');
      setSubmitting(false);
    }
  };

  const toggleTool = (toolId: string) => {
    setForm((f) => ({
      ...f,
      tool_ids: f.tool_ids.includes(toolId)
        ? f.tool_ids.filter((t) => t !== toolId)
        : [...f.tool_ids, toolId],
    }));
  };

  const categories = [...new Set(tools.map((t) => t.category))].sort();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl w-full max-w-2xl max-h-[90vh] overflow-auto shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
          <h2 className="text-base font-semibold text-[var(--color-text)]">Create New Agent</h2>
          <button
            onClick={onClose}
            className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] text-lg leading-none"
          >
            &times;
          </button>
        </div>

        <div className="p-5 space-y-4">
          {error && (
            <div className="text-xs px-3 py-2 rounded-lg bg-red-950/30 text-red-400 border border-red-500/30">
              {error}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1">
                Agent ID <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={form.agent_id}
                onChange={(e) => setForm({ ...form, agent_id: e.target.value.replace(/[^a-z0-9_]/g, '') })}
                placeholder="my_custom_agent"
                className="w-full px-3 py-2 text-sm rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1">
                Channel ID
              </label>
              <input
                type="text"
                value={form.channel_id}
                onChange={(e) => setForm({ ...form, channel_id: e.target.value })}
                placeholder="Auto-generated"
                className="w-full px-3 py-2 text-sm rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1">
              Display Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={form.display_name}
              onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              placeholder="My Custom Agent"
              className="w-full px-3 py-2 text-sm rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1">
              Description
            </label>
            <input
              type="text"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Brief description of what this agent does"
              className="w-full px-3 py-2 text-sm rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1">Model</label>
            <div className="grid grid-cols-2 gap-2">
              {MODEL_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => setForm({ ...form, model_id: opt.id })}
                  className={`p-2 rounded-lg border text-left transition-colors text-xs ${
                    form.model_id === opt.id
                      ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-text)]'
                      : 'border-[var(--color-border)] bg-[var(--color-bg)] hover:border-[var(--color-text-muted)] text-[var(--color-text-muted)]'
                  }`}
                >
                  <div className="font-semibold">{opt.label}</div>
                  <div className="text-[10px] opacity-60">{opt.provider}</div>
                </button>
              ))}
            </div>
          </div>

          {categories.length > 0 && (
            <div>
              <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-2">
                Tools ({form.tool_ids.length} selected)
              </label>
              <div className="space-y-3 max-h-40 overflow-auto">
                {categories.map((cat) => (
                  <div key={cat}>
                    <div className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1">
                      {cat}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {tools
                        .filter((t) => t.category === cat)
                        .map((t) => (
                          <button
                            key={t.tool_id}
                            onClick={() => toggleTool(t.tool_id)}
                            className={`px-2 py-1 text-[10px] rounded border transition-colors ${
                              form.tool_ids.includes(t.tool_id)
                                ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-text)]'
                                : 'border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-text-muted)]'
                            }`}
                          >
                            {t.display_name}
                          </button>
                        ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1">
              System Prompt
            </label>
            <textarea
              value={form.system_prompt}
              onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
              rows={8}
              placeholder="You are a..."
              className="w-full px-3 py-2 text-xs font-mono leading-relaxed rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none resize-y"
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-[var(--color-border)]">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="px-4 py-2 text-xs rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-40 transition-colors"
          >
            {submitting ? 'Creating...' : 'Create Agent'}
          </button>
        </div>
      </div>
    </div>
  );
}
