import { useEffect, useState, useCallback } from 'react';
import Header from '@/components/layout/Header';
import { fetchJson } from '@/lib/api';

interface TraceRun {
  run_id: string;
  name: string;
  run_type: string;
  status: string;
  start_time: string | null;
  end_time: string | null;
  duration_ms: number;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost: number;
  error: string | null;
  inputs_preview: string;
  outputs_preview: string;
  steps?: TraceRun[];
}

const STATUS_COLORS: Record<string, string> = {
  success: '#22c55e',
  error: '#ef4444',
  pending: '#f59e0b',
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

function formatTime(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatCost(cost: number): string {
  if (cost === 0) return 'Free';
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}

export default function TracesPage() {
  const [traces, setTraces] = useState<TraceRun[]>([]);
  const [selected, setSelected] = useState<TraceRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [days, setDays] = useState(7);

  const loadTraces = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchJson<{ traces: TraceRun[] }>(`/api/traces?days=${days}&limit=100`);
      setTraces(data.traces);
    } catch {
      setTraces([]);
    }
    setLoading(false);
  }, [days]);

  useEffect(() => {
    loadTraces();
  }, [loadTraces]);

  const selectTrace = async (trace: TraceRun) => {
    setSelected(trace);
    setDetailLoading(true);
    try {
      const detail = await fetchJson<TraceRun>(`/api/traces/${trace.run_id}`);
      setSelected(detail);
    } catch { /* keep basic trace */ }
    setDetailLoading(false);
  };

  return (
    <div className="flex flex-col h-full">
      <Header title="Traces" subtitle="LangSmith trace explorer" />
      <div className="flex items-center gap-3 px-4 py-2 bg-[var(--color-bg-card)] border-b border-[var(--color-border)]">
        <span className="text-xs text-[var(--color-text-muted)]">Period:</span>
        {[1, 7, 30].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className="px-2 py-0.5 text-xs rounded"
            style={{
              background: days === d ? 'var(--color-accent)' : 'transparent',
              color: days === d ? '#fff' : 'var(--color-text-muted)',
              border: days === d ? 'none' : '1px solid var(--color-border)',
            }}
          >
            {d === 1 ? 'Today' : d === 7 ? '7 days' : '30 days'}
          </button>
        ))}
        <button
          onClick={loadTraces}
          className="ml-auto text-xs text-[var(--color-accent)] hover:underline"
        >
          Refresh
        </button>
        <span className="text-xs text-[var(--color-text-muted)]">{traces.length} traces</span>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Trace List */}
        <div className="w-[420px] border-r border-[var(--color-border)] overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center h-32 text-sm text-[var(--color-text-muted)]">
              Loading traces...
            </div>
          ) : traces.length === 0 ? (
            <div className="flex items-center justify-center h-32 text-sm text-[var(--color-text-muted)]">
              No traces found. Run a task first.
            </div>
          ) : (
            traces.map((trace) => (
              <div
                key={trace.run_id}
                onClick={() => selectTrace(trace)}
                className="px-4 py-3 border-b border-[var(--color-border)] cursor-pointer hover:bg-[var(--color-bg-card)] transition-colors"
                style={{
                  background:
                    selected?.run_id === trace.run_id ? 'var(--color-bg-card)' : 'transparent',
                  borderLeft:
                    selected?.run_id === trace.run_id
                      ? '3px solid var(--color-accent)'
                      : '3px solid transparent',
                }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: STATUS_COLORS[trace.status] || '#6b7280',
                      display: 'inline-block',
                      flexShrink: 0,
                    }}
                  />
                  <span className="text-sm font-medium text-[var(--color-text)] truncate">
                    {trace.name || trace.run_id.slice(0, 8)}
                  </span>
                  <span className="ml-auto text-xs text-[var(--color-text-muted)]">
                    {formatDuration(trace.duration_ms)}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-[var(--color-text-muted)]">
                  <span>{formatTime(trace.start_time)}</span>
                  <span>{trace.total_tokens > 0 ? `${trace.total_tokens} tok` : ''}</span>
                  <span className="ml-auto">{formatCost(trace.cost)}</span>
                </div>
                {trace.error && (
                  <div className="mt-1 text-xs text-red-400 truncate">{trace.error}</div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Trace Detail */}
        <div className="flex-1 overflow-y-auto p-4">
          {!selected ? (
            <div className="flex items-center justify-center h-full text-sm text-[var(--color-text-muted)]">
              Select a trace to view details
            </div>
          ) : (
            <div>
              <div className="mb-4">
                <h2 className="text-lg font-semibold text-[var(--color-text)] mb-2">
                  {selected.name || selected.run_id.slice(0, 8)}
                </h2>
                <div className="grid grid-cols-4 gap-3">
                  {[
                    { label: 'Status', value: selected.status ?? 'unknown', color: STATUS_COLORS[selected.status] },
                    { label: 'Duration', value: formatDuration(selected.duration_ms ?? 0) },
                    { label: 'Tokens', value: (selected.total_tokens ?? 0).toLocaleString() },
                    { label: 'Cost', value: formatCost(selected.cost ?? 0) },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-3"
                    >
                      <div className="text-xs text-[var(--color-text-muted)] mb-1">{item.label}</div>
                      <div
                        className="text-sm font-medium"
                        style={{ color: item.color || 'var(--color-text)' }}
                      >
                        {item.value}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {detailLoading ? (
                <div className="text-sm text-[var(--color-text-muted)]">Loading steps...</div>
              ) : selected.steps && selected.steps.length > 0 ? (
                <div>
                  <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">
                    Execution Steps ({selected.steps.length})
                  </h3>
                  <TimelineBar steps={selected.steps} totalMs={selected.duration_ms} />
                  <div className="mt-3 space-y-1">
                    {selected.steps.map((step) => (
                      <div
                        key={step.run_id}
                        className="flex items-center gap-3 px-3 py-2 rounded bg-[var(--color-bg-card)] border border-[var(--color-border)]"
                      >
                        <span
                          style={{
                            width: 6, height: 6, borderRadius: '50%',
                            background: STATUS_COLORS[step.status] || '#6b7280',
                            display: 'inline-block', flexShrink: 0,
                          }}
                        />
                        <span className="text-xs font-medium text-[var(--color-text)] w-40 truncate">{step.name}</span>
                        <span className="text-xs text-[var(--color-text-muted)] w-20">{step.run_type}</span>
                        <span className="text-xs text-[var(--color-text-muted)] w-24">{step.model !== 'unknown' ? step.model : ''}</span>
                        <span className="text-xs text-[var(--color-text-muted)] w-16 text-right">{formatDuration(step.duration_ms)}</span>
                        <span className="text-xs text-[var(--color-text-muted)] w-16 text-right">{step.total_tokens > 0 ? `${step.total_tokens}` : ''}</span>
                        <span className="text-xs text-[var(--color-text-muted)] w-16 text-right">{step.cost > 0 ? formatCost(step.cost) : ''}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-sm text-[var(--color-text-muted)]">No child steps found.</div>
              )}

              {(selected.inputs_preview || selected.outputs_preview) && (
                <div className="mt-4 space-y-3">
                  {selected.inputs_preview && (
                    <div>
                      <div className="text-xs font-semibold text-[var(--color-text-muted)] mb-1">Input</div>
                      <pre className="text-xs text-[var(--color-text)] bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">{selected.inputs_preview}</pre>
                    </div>
                  )}
                  {selected.outputs_preview && (
                    <div>
                      <div className="text-xs font-semibold text-[var(--color-text-muted)] mb-1">Output</div>
                      <pre className="text-xs text-[var(--color-text)] bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">{selected.outputs_preview}</pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TimelineBar({ steps, totalMs }: { steps: TraceRun[]; totalMs: number }) {
  if (totalMs === 0 || steps.length === 0) return null;
  const minTime = steps.reduce((min, s) => {
    const t = s.start_time ? new Date(s.start_time).getTime() : Infinity;
    return t < min ? t : min;
  }, Infinity);
  const COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#22c55e', '#06b6d4', '#ef4444'];
  return (
    <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-3">
      <div className="space-y-1.5">
        {steps.filter((s) => s.duration_ms > 0).slice(0, 20).map((step, i) => {
          const startOffset = step.start_time ? new Date(step.start_time).getTime() - minTime : 0;
          const leftPct = Math.min((startOffset / totalMs) * 100, 95);
          const widthPct = Math.max((step.duration_ms / totalMs) * 100, 1);
          return (
            <div key={step.run_id} className="flex items-center gap-2 h-5">
              <span className="text-[10px] text-[var(--color-text-muted)] w-28 truncate text-right">{step.name}</span>
              <div className="flex-1 relative h-4 bg-[var(--color-bg)] rounded overflow-hidden">
                <div
                  className="absolute h-full rounded"
                  style={{
                    left: `${leftPct}%`,
                    width: `${Math.min(widthPct, 100 - leftPct)}%`,
                    background: COLORS[i % COLORS.length],
                    opacity: 0.8,
                  }}
                  title={`${step.name}: ${formatDuration(step.duration_ms)}`}
                />
              </div>
              <span className="text-[10px] text-[var(--color-text-muted)] w-12 text-right">{formatDuration(step.duration_ms)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
