import { useEffect, useState, useCallback } from 'react';
import Header from '@/components/layout/Header';
import { fetchJson } from '@/lib/api';
import type { AutonomyStatus, QueuedTask, AuditLog } from '@/types/autonomy';

const API_BASE = '/api/autonomy';

export default function AutonomyPage() {
  const [status, setStatus] = useState<AutonomyStatus | null>(null);
  const [queue, setQueue] = useState<QueuedTask[]>([]);
  const [audit, setAudit] = useState<AuditLog[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditPage, setAuditPage] = useState(0);
  const [expandedAudit, setExpandedAudit] = useState<number | null>(null);
  const AUDIT_LIMIT = 20;

  const loadStatus = useCallback(() => {
    fetchJson<AutonomyStatus>(`${API_BASE}/status`).then(setStatus).catch(() => {});
  }, []);

  const loadQueue = useCallback(() => {
    fetchJson<{ tasks: QueuedTask[] }>(`${API_BASE}/queue`).then((r) => setQueue(r?.tasks ?? [])).catch(() => {});
  }, []);

  const loadAudit = useCallback(() => {
    fetchJson<{ logs: AuditLog[]; total: number }>(`${API_BASE}/audit?limit=${AUDIT_LIMIT}&offset=${auditPage * AUDIT_LIMIT}`)
      .then((r) => {
        setAudit(r?.logs ?? []);
        setAuditTotal(r?.total ?? 0);
      })
      .catch(() => {});
  }, [auditPage]);

  useEffect(() => {
    loadStatus();
    loadQueue();
    loadAudit();
    const interval = setInterval(() => {
      loadStatus();
      loadQueue();
    }, 5000);
    return () => clearInterval(interval);
  }, [loadStatus, loadQueue, loadAudit]);

  useEffect(() => {
    loadAudit();
  }, [loadAudit]);

  const handlePause = async () => {
    await fetch(`${API_BASE}/pause`, { method: 'POST' });
    loadStatus();
  };

  const handleResume = async () => {
    await fetch(`${API_BASE}/resume`, { method: 'POST' });
    loadStatus();
  };

  const handleCancelTask = async (taskId: string) => {
    await fetch(`${API_BASE}/queue/${taskId}`, { method: 'DELETE' });
    loadQueue();
    loadStatus();
  };

  const handleClearQueue = async () => {
    await fetch(`${API_BASE}/queue`, { method: 'DELETE' });
    loadQueue();
    loadStatus();
  };

  const paused = status?.paused;
  const running = status?.running;

  const statusColor = paused ? '#eab308' : running ? '#22c55e' : '#ef4444';
  const statusLabel = paused ? 'Paused' : running ? 'Running' : 'Stopped';

  const outcomeBadge = (outcome: string) => {
    if (outcome === 'completed') return { bg: '#22c55e20', color: '#22c55e', label: 'OK' };
    if (outcome === 'failed') return { bg: '#ef444420', color: '#ef4444', label: 'FAIL' };
    if (outcome === 'credit_paused') return { bg: '#eab30820', color: '#eab308', label: 'CREDIT' };
    return { bg: '#6b728020', color: '#6b7280', label: outcome };
  };

  const priorityBadge = (p: string) => {
    if (p === 'critical') return { bg: '#ef444420', color: '#ef4444' };
    if (p === 'high') return { bg: '#f9731620', color: '#f97316' };
    return { bg: '#6b728020', color: '#6b7280' };
  };

  const relTime = (iso: string) => {
    try {
      const diff = Date.now() - new Date(iso).getTime();
      const mins = Math.floor(diff / 60000);
      if (mins < 1) return 'just now';
      if (mins < 60) return `${mins}m ago`;
      const hrs = Math.floor(mins / 60);
      if (hrs < 24) return `${hrs}h ago`;
      return `${Math.floor(hrs / 24)}d ago`;
    } catch {
      return iso;
    }
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <Header title="Autonomy" subtitle="Holly's autonomous execution loop" />
      <div className="p-4 space-y-4 max-w-5xl mx-auto w-full">

        {/* Status Card */}
        <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: statusColor, display: 'inline-block' }} />
              <span className="text-sm font-medium text-[var(--color-text)]">{statusLabel}</span>
              {status?.detail && (
                <span className="text-xs text-[var(--color-text-muted)] ml-2 truncate max-w-md">{status.detail}</span>
              )}
            </div>
            <div className="flex gap-2">
              {running && !paused && (
                <button onClick={handlePause} className="text-xs px-3 py-1 rounded border border-[#eab308] text-[#eab308] hover:bg-[#eab30810] transition-colors">
                  Pause
                </button>
              )}
              {paused && (
                <button onClick={handleResume} className="text-xs px-3 py-1 rounded border border-[#22c55e] text-[#22c55e] hover:bg-[#22c55e10] transition-colors">
                  Resume
                </button>
              )}
            </div>
          </div>
          <div className="grid grid-cols-5 gap-4">
            {[
              { label: 'Queue Depth', value: status?.queue_depth ?? '-' },
              { label: 'Tasks Done', value: status?.tasks_completed ?? '-' },
              { label: 'Errors', value: status?.consecutive_errors ?? '-' },
              { label: 'Monitor Interval', value: status?.monitor_interval ? `${status.monitor_interval}s` : '-' },
              { label: 'Idle Sweeps', value: status?.idle_sweeps ?? '-' },
            ].map((m) => (
              <div key={m.label} className="text-center">
                <div className="text-lg font-mono text-[var(--color-text)]">{m.value}</div>
                <div className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wide">{m.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Queue Panel */}
        <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg">
          <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-border)]">
            <span className="text-sm font-medium text-[var(--color-text)]">Queue ({queue.length})</span>
            {queue.length > 0 && (
              <button onClick={handleClearQueue} className="text-[10px] px-2 py-0.5 rounded border border-[#ef4444] text-[#ef4444] hover:bg-[#ef444410]">
                Clear All
              </button>
            )}
          </div>
          {queue.length === 0 ? (
            <div className="px-4 py-6 text-center text-xs text-[var(--color-text-muted)]">Queue empty</div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[var(--color-text-muted)] text-left border-b border-[var(--color-border)]">
                  <th className="px-4 py-2 font-normal w-20">ID</th>
                  <th className="px-2 py-2 font-normal w-16">Priority</th>
                  <th className="px-2 py-2 font-normal w-24">Type</th>
                  <th className="px-2 py-2 font-normal">Objective</th>
                  <th className="px-2 py-2 font-normal w-20">Submitted</th>
                  <th className="px-2 py-2 font-normal w-16" />
                </tr>
              </thead>
              <tbody>
                {queue.map((t) => {
                  const pb = priorityBadge(t.priority);
                  return (
                    <tr key={t.id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-bg-hover)]">
                      <td className="px-4 py-2 font-mono">{t.id}</td>
                      <td className="px-2 py-2">
                        <span style={{ background: pb.bg, color: pb.color }} className="px-1.5 py-0.5 rounded text-[10px] font-medium">
                          {t.priority}
                        </span>
                      </td>
                      <td className="px-2 py-2 text-[var(--color-text-muted)]">{t.type}</td>
                      <td className="px-2 py-2 text-[var(--color-text)] truncate max-w-xs">{t.objective.slice(0, 120)}</td>
                      <td className="px-2 py-2 text-[var(--color-text-muted)]">{relTime(t.submitted_at)}</td>
                      <td className="px-2 py-2">
                        <button onClick={() => handleCancelTask(t.id)} className="text-[#ef4444] hover:underline">Cancel</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Audit Log */}
        <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg">
          <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-border)]">
            <span className="text-sm font-medium text-[var(--color-text)]">Audit Log ({auditTotal})</span>
            <div className="flex gap-2 text-xs">
              <button
                disabled={auditPage === 0}
                onClick={() => setAuditPage((p) => Math.max(0, p - 1))}
                className="px-2 py-0.5 rounded border border-[var(--color-border)] text-[var(--color-text-muted)] disabled:opacity-30"
              >
                Prev
              </button>
              <span className="text-[var(--color-text-muted)] py-0.5">
                {auditPage * AUDIT_LIMIT + 1}–{Math.min((auditPage + 1) * AUDIT_LIMIT, auditTotal)} of {auditTotal}
              </span>
              <button
                disabled={(auditPage + 1) * AUDIT_LIMIT >= auditTotal}
                onClick={() => setAuditPage((p) => p + 1)}
                className="px-2 py-0.5 rounded border border-[var(--color-border)] text-[var(--color-text-muted)] disabled:opacity-30"
              >
                Next
              </button>
            </div>
          </div>
          {audit.length === 0 ? (
            <div className="px-4 py-6 text-center text-xs text-[var(--color-text-muted)]">No audit entries yet</div>
          ) : (
            <div>
              {audit.map((entry) => {
                const ob = outcomeBadge(entry.outcome);
                const expanded = expandedAudit === entry.id;
                return (
                  <div key={entry.id} className="border-b border-[var(--color-border)]">
                    <button
                      onClick={() => setExpandedAudit(expanded ? null : entry.id)}
                      className="w-full text-left px-4 py-2 hover:bg-[var(--color-bg-hover)] flex items-center gap-3 text-xs"
                    >
                      <span className="text-[var(--color-text-muted)] w-16 shrink-0">{relTime(entry.finished_at)}</span>
                      <span className="font-mono w-16 shrink-0 text-[var(--color-text-muted)]">{entry.task_id}</span>
                      <span className="w-24 shrink-0 text-[var(--color-text-muted)]">{entry.task_type}</span>
                      <span style={{ background: ob.bg, color: ob.color }} className="px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0">
                        {ob.label}
                      </span>
                      <span className="text-[var(--color-text-muted)] shrink-0 w-14 text-right">{entry.duration_sec.toFixed(1)}s</span>
                      <span className="text-[var(--color-text)] truncate flex-1">{entry.objective.slice(0, 100)}</span>
                    </button>
                    {expanded && (
                      <div className="px-4 pb-3 pt-1 text-xs space-y-1 bg-[var(--color-bg)]/50">
                        <div className="text-[var(--color-text)]"><strong>Objective:</strong> {entry.objective}</div>
                        {entry.error_message && (
                          <div className="text-[#ef4444]"><strong>Error:</strong> {entry.error_message}</div>
                        )}
                        <div className="text-[var(--color-text-muted)]">
                          Started: {new Date(entry.started_at).toLocaleString()} | Finished: {new Date(entry.finished_at).toLocaleString()}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
