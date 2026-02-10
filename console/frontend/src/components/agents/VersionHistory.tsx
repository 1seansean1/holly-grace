import type { AgentVersion } from '@/types/agents';

interface Props {
  versions: AgentVersion[];
  currentVersion: number;
  onRollback: (version: number) => void;
  rollingBack: boolean;
}

function getModelLabel(modelId: string): string {
  const map: Record<string, string> = {
    ollama_qwen: 'Qwen 2.5 3B',
    gpt4o_mini: 'GPT-4o Mini',
    gpt4o: 'GPT-4o',
    claude_opus: 'Opus 4.6',
  };
  return map[modelId] ?? modelId;
}

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

export default function VersionHistory({ versions, currentVersion, onRollback, rollingBack }: Props) {
  if (versions.length === 0) {
    return (
      <div className="text-xs text-[var(--color-text-muted)] py-4 text-center">
        No version history yet. Make changes and save to create versions.
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {versions.map((v) => {
        const isCurrent = v.version === currentVersion;
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
              <div className="flex items-center gap-2">
                <span className="text-xs text-[var(--color-text)]">{v.display_name}</span>
                <span className="text-[10px] text-[var(--color-text-muted)]">
                  {getModelLabel(v.model_id)}
                </span>
                {v.tool_ids.length > 0 && (
                  <span className="text-[10px] text-[var(--color-text-muted)]">
                    {v.tool_ids.length} tools
                  </span>
                )}
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
                  onClick={() => onRollback(v.version)}
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
  );
}
