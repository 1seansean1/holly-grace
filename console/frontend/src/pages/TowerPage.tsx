import { useEffect, useState, useCallback } from 'react';
import Header from '@/components/layout/Header';
import { fetchJson, postJson } from '@/lib/api';
import type { TowerRun, TowerTicket, TowerEvent } from '@/types/tower';
import {
  Inbox,
  Play,
  Pause,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  RefreshCw,
  ChevronRight,
  ShieldAlert,
  Loader2,
} from 'lucide-react';

type Tab = 'inbox' | 'runs';

const STATUS_STYLES: Record<string, string> = {
  queued: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  running: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  waiting_approval: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  completed: 'bg-green-500/20 text-green-400 border-green-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  cancelled: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  pending: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  approved: 'bg-green-500/20 text-green-400 border-green-500/30',
  rejected: 'bg-red-500/20 text-red-400 border-red-500/30',
  expired: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
};

const RISK_STYLES: Record<string, string> = {
  high: 'bg-red-500/20 text-red-400 border-red-500/30',
  medium: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  low: 'bg-green-500/20 text-green-400 border-green-500/30',
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${STATUS_STYLES[status] ?? 'bg-gray-500/20 text-gray-400 border-gray-500/30'}`}>
      {status.replace('_', ' ')}
    </span>
  );
}

function RiskBadge({ risk }: { risk: string }) {
  return (
    <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${RISK_STYLES[risk] ?? ''}`}>
      {risk}
    </span>
  );
}

function TimeAgo({ ts }: { ts: string }) {
  const secs = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (secs < 60) return <span>{secs}s ago</span>;
  if (secs < 3600) return <span>{Math.floor(secs / 60)}m ago</span>;
  if (secs < 86400) return <span>{Math.floor(secs / 3600)}h ago</span>;
  return <span>{Math.floor(secs / 86400)}d ago</span>;
}

export default function TowerPage() {
  const [tab, setTab] = useState<Tab>('inbox');
  const [tickets, setTickets] = useState<TowerTicket[]>([]);
  const [runs, setRuns] = useState<TowerRun[]>([]);
  const [selectedTicket, setSelectedTicket] = useState<TowerTicket | null>(null);
  const [selectedRun, setSelectedRun] = useState<TowerRun | null>(null);
  const [events, setEvents] = useState<TowerEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  // Load inbox tickets
  const loadTickets = useCallback(async () => {
    try {
      const data = await fetchJson<{ tickets: TowerTicket[] }>('/api/tower/inbox?status=pending&limit=100');
      setTickets(data.tickets ?? []);
    } catch { /* silent */ }
  }, []);

  // Load runs
  const loadRuns = useCallback(async () => {
    try {
      const params = statusFilter !== 'all' ? `?status=${statusFilter}&limit=100` : '?limit=100';
      const data = await fetchJson<{ runs: TowerRun[] }>(`/api/tower/runs${params}`);
      setRuns(data.runs ?? []);
    } catch { /* silent */ }
  }, [statusFilter]);

  // Load events for selected run
  const loadEvents = useCallback(async (runId: string) => {
    try {
      const data = await fetchJson<{ events: TowerEvent[] }>(`/api/tower/runs/${runId}/events`);
      setEvents(data.events ?? []);
    } catch {
      setEvents([]);
    }
  }, []);

  // Initial load + polling
  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await Promise.all([loadTickets(), loadRuns()]);
      setLoading(false);
    };
    load();
    const interval = setInterval(() => {
      loadTickets();
      loadRuns();
    }, 5000);
    return () => clearInterval(interval);
  }, [loadTickets, loadRuns]);

  // Load events when a run is selected
  useEffect(() => {
    if (selectedRun) loadEvents(selectedRun.run_id);
  }, [selectedRun, loadEvents]);

  // Select ticket → also select its run
  const handleSelectTicket = async (ticket: TowerTicket) => {
    setSelectedTicket(ticket);
    if (ticket.run_id) {
      try {
        const run = await fetchJson<TowerRun>(`/api/tower/runs/${ticket.run_id}`);
        setSelectedRun(run);
      } catch { /* silent */ }
    }
  };

  // Decide a ticket
  const handleDecide = async (ticketId: number, decision: 'approve' | 'reject') => {
    setDeciding(true);
    try {
      await postJson(`/api/tower/tickets/${ticketId}/decide`, {
        decision,
        decided_by: 'console',
        expected_checkpoint_id: selectedTicket?.checkpoint_id,
      });
      showToast(`Ticket ${ticketId} ${decision === 'approve' ? 'approved' : 'rejected'}`, true);
      setSelectedTicket(null);
      await loadTickets();
      await loadRuns();
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Decision failed', false);
    } finally {
      setDeciding(false);
    }
  };

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (tab === 'inbox' && selectedTicket) {
        if (e.key === 'a') handleDecide(selectedTicket.id, 'approve');
        if (e.key === 'r') handleDecide(selectedTicket.id, 'reject');
      }
      if (e.key === 'j' || e.key === 'k') {
        const items = tab === 'inbox' ? tickets : runs;
        const sel = tab === 'inbox' ? selectedTicket?.id : selectedRun?.run_id;
        const idx = items.findIndex(i => (tab === 'inbox' ? (i as TowerTicket).id === sel : (i as TowerRun).run_id === sel));
        const next = e.key === 'j' ? Math.min(idx + 1, items.length - 1) : Math.max(idx - 1, 0);
        if (tab === 'inbox') handleSelectTicket(items[next] as TowerTicket);
        else setSelectedRun(items[next] as TowerRun);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  });

  return (
    <div className="flex flex-col h-full">
      <Header title="Control Tower" subtitle="Durable runs, approval tickets, and system supervision" />

      {/* Toast */}
      {toast && (
        <div className={`mx-6 mt-2 text-xs px-3 py-2 rounded-lg ${
          toast.ok ? 'bg-emerald-950/30 text-emerald-400 border border-emerald-500/30' : 'bg-red-950/30 text-red-400 border border-red-500/30'
        }`}>{toast.msg}</div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 px-6 pt-4 border-b border-[var(--color-border)]">
        {(['inbox', 'runs'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-xs font-semibold transition-colors border-b-2 -mb-px flex items-center gap-1.5 ${
              tab === t
                ? 'border-[var(--color-accent)] text-[var(--color-text)]'
                : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
            }`}
          >
            {t === 'inbox' ? <Inbox size={14} /> : <Play size={14} />}
            {t === 'inbox' ? `Inbox (${tickets.length})` : `Runs (${runs.length})`}
          </button>
        ))}
      </div>

      {/* Main content: three-panel layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left rail: list */}
        <div className="w-80 border-r border-[var(--color-border)] overflow-y-auto shrink-0">
          {tab === 'runs' && (
            <div className="flex gap-1 px-3 py-2 border-b border-[var(--color-border)] flex-wrap">
              {['all', 'queued', 'running', 'waiting_approval', 'completed', 'failed'].map(s => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={`px-2 py-0.5 text-[10px] rounded ${
                    statusFilter === s
                      ? 'bg-[var(--color-accent)] text-white'
                      : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] border border-[var(--color-border)]'
                  }`}
                >{s === 'all' ? 'All' : s.replace('_', ' ')}</button>
              ))}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center h-32">
              <Loader2 size={20} className="animate-spin text-[var(--color-text-muted)]" />
            </div>
          ) : tab === 'inbox' ? (
            tickets.length === 0 ? (
              <div className="text-center py-16">
                <CheckCircle size={32} className="mx-auto mb-3 text-[var(--color-text-muted)] opacity-30" />
                <p className="text-xs text-[var(--color-text-muted)]">No pending tickets</p>
              </div>
            ) : (
              tickets.map(t => (
                <div
                  key={t.id}
                  onClick={() => handleSelectTicket(t)}
                  className={`px-3 py-3 border-b border-[var(--color-border)] cursor-pointer transition-colors ${
                    selectedTicket?.id === t.id
                      ? 'bg-[var(--color-accent)]/10 border-l-2 border-l-[var(--color-accent)]'
                      : 'hover:bg-[var(--color-bg-hover)]'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-[var(--color-text)]">{t.context_pack?.tldr ?? `Ticket #${t.id}`}</span>
                    <RiskBadge risk={t.risk_level} />
                  </div>
                  <div className="text-[10px] text-[var(--color-text-muted)] flex items-center gap-2">
                    <span>{t.ticket_type}</span>
                    <span><TimeAgo ts={t.created_at} /></span>
                  </div>
                </div>
              ))
            )
          ) : (
            runs.length === 0 ? (
              <div className="text-center py-16">
                <Play size={32} className="mx-auto mb-3 text-[var(--color-text-muted)] opacity-30" />
                <p className="text-xs text-[var(--color-text-muted)]">No runs</p>
              </div>
            ) : (
              runs.map(r => (
                <div
                  key={r.run_id}
                  onClick={() => setSelectedRun(r)}
                  className={`px-3 py-3 border-b border-[var(--color-border)] cursor-pointer transition-colors ${
                    selectedRun?.run_id === r.run_id
                      ? 'bg-[var(--color-accent)]/10 border-l-2 border-l-[var(--color-accent)]'
                      : 'hover:bg-[var(--color-bg-hover)]'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-[var(--color-text)] truncate max-w-[180px]">
                      {r.run_name ?? r.run_id.slice(4, 16)}
                    </span>
                    <StatusBadge status={r.status} />
                  </div>
                  <div className="text-[10px] text-[var(--color-text-muted)] flex items-center gap-2">
                    <span>{r.workflow_id}</span>
                    <span><TimeAgo ts={r.created_at} /></span>
                  </div>
                </div>
              ))
            )
          )}
        </div>

        {/* Center: context pack / detail */}
        <div className="flex-1 overflow-y-auto p-6">
          {tab === 'inbox' && selectedTicket ? (
            <ContextPackPanel
              ticket={selectedTicket}
              deciding={deciding}
              onDecide={handleDecide}
            />
          ) : tab === 'runs' && selectedRun ? (
            <RunInspector run={selectedRun} events={events} onRefresh={() => loadEvents(selectedRun.run_id)} />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-[var(--color-text-muted)]">
              <ShieldAlert size={48} className="mb-3 opacity-20" />
              <p className="text-sm">Select a {tab === 'inbox' ? 'ticket' : 'run'} to inspect</p>
              {tab === 'inbox' && <p className="text-xs mt-1 opacity-60">Keyboard: j/k navigate, a approve, r reject</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Context pack panel: shows ticket details + approve/reject actions. */
function ContextPackPanel({
  ticket,
  deciding,
  onDecide,
}: {
  ticket: TowerTicket;
  deciding: boolean;
  onDecide: (id: number, decision: 'approve' | 'reject') => void;
}) {
  const cp = ticket.context_pack;
  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <h2 className="text-lg font-semibold text-[var(--color-text)]">{cp?.tldr ?? 'Approval Required'}</h2>
          <RiskBadge risk={ticket.risk_level} />
          <StatusBadge status={ticket.status} />
        </div>
        <p className="text-sm text-[var(--color-text-muted)]">{cp?.why_stopped}</p>
      </div>

      {/* Proposed action */}
      {ticket.proposed_action && Object.keys(ticket.proposed_action).length > 0 && (
        <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-4">
          <h3 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase mb-2">Proposed Action</h3>
          <pre className="text-xs text-[var(--color-text)] overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(ticket.proposed_action, null, 2)}
          </pre>
        </div>
      )}

      {/* Impact + risk flags */}
      <div className="grid grid-cols-2 gap-4">
        {cp?.impact && (
          <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-4">
            <h3 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase mb-2">Impact</h3>
            <p className="text-sm text-[var(--color-text)]">{cp.impact}</p>
          </div>
        )}
        {cp?.risk_flags && cp.risk_flags.length > 0 && (
          <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-4">
            <h3 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase mb-2">Risk Flags</h3>
            <div className="flex flex-wrap gap-1">
              {cp.risk_flags.map((f, i) => (
                <span key={i} className="px-2 py-0.5 text-xs bg-red-500/10 text-red-400 border border-red-500/20 rounded-full">{f}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Metadata */}
      <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-4 text-xs text-[var(--color-text-muted)] space-y-1">
        <div className="flex justify-between"><span>Ticket ID</span><span className="text-[var(--color-text)]">#{ticket.id}</span></div>
        <div className="flex justify-between"><span>Run ID</span><span className="text-[var(--color-text)] font-mono">{ticket.run_id}</span></div>
        <div className="flex justify-between"><span>Checkpoint</span><span className="text-[var(--color-text)] font-mono truncate max-w-[200px]">{ticket.checkpoint_id ?? 'N/A'}</span></div>
        <div className="flex justify-between"><span>Created</span><span className="text-[var(--color-text)]">{new Date(ticket.created_at).toLocaleString()}</span></div>
      </div>

      {/* Action buttons */}
      {ticket.status === 'pending' && (
        <div className="flex gap-3 pt-2">
          <button
            onClick={() => onDecide(ticket.id, 'approve')}
            disabled={deciding}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-green-600 hover:bg-green-500 text-white text-sm font-semibold transition-colors disabled:opacity-50"
          >
            {deciding ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />}
            Approve (a)
          </button>
          <button
            onClick={() => onDecide(ticket.id, 'reject')}
            disabled={deciding}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-semibold transition-colors disabled:opacity-50"
          >
            {deciding ? <Loader2 size={16} className="animate-spin" /> : <XCircle size={16} />}
            Reject (r)
          </button>
        </div>
      )}
    </div>
  );
}

/** Run inspector: shows run details + event timeline. */
function RunInspector({
  run,
  events,
  onRefresh,
}: {
  run: TowerRun;
  events: TowerEvent[];
  onRefresh: () => void;
}) {
  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h2 className="text-lg font-semibold text-[var(--color-text)]">{run.run_name ?? run.run_id}</h2>
            <StatusBadge status={run.status} />
          </div>
          <p className="text-xs text-[var(--color-text-muted)] font-mono">{run.run_id}</p>
        </div>
        <button
          onClick={onRefresh}
          className="p-2 rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] transition-colors"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {/* Run metadata */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-3">
          <div className="text-[10px] text-[var(--color-text-muted)] uppercase mb-1">Workflow</div>
          <div className="text-sm text-[var(--color-text)]">{run.workflow_id}</div>
        </div>
        <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-3">
          <div className="text-[10px] text-[var(--color-text-muted)] uppercase mb-1">Created</div>
          <div className="text-sm text-[var(--color-text)]">{new Date(run.created_at).toLocaleString()}</div>
        </div>
        <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-3">
          <div className="text-[10px] text-[var(--color-text-muted)] uppercase mb-1">Duration</div>
          <div className="text-sm text-[var(--color-text)]">
            {run.finished_at && run.started_at
              ? `${((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000).toFixed(1)}s`
              : run.started_at ? 'In progress' : 'Not started'}
          </div>
        </div>
      </div>

      {/* Error */}
      {run.last_error && (
        <div className="bg-red-950/30 border border-red-500/30 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle size={14} className="text-red-400" />
            <span className="text-xs font-semibold text-red-400">Error</span>
          </div>
          <p className="text-xs text-red-300 font-mono whitespace-pre-wrap">{run.last_error}</p>
        </div>
      )}

      {/* Event timeline */}
      <div>
        <h3 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase mb-3">Event Timeline ({events.length})</h3>
        {events.length === 0 ? (
          <p className="text-xs text-[var(--color-text-muted)]">No events yet</p>
        ) : (
          <div className="space-y-0 relative">
            <div className="absolute left-[7px] top-2 bottom-2 w-px bg-[var(--color-border)]" />
            {events.map((evt, i) => (
              <div key={evt.id ?? i} className="flex gap-3 py-1.5 relative">
                <div className={`w-3.5 h-3.5 rounded-full border-2 shrink-0 mt-0.5 z-10 ${
                  evt.event_type.includes('failed') ? 'border-red-400 bg-red-400/20' :
                  evt.event_type.includes('completed') ? 'border-green-400 bg-green-400/20' :
                  evt.event_type.includes('waiting') ? 'border-purple-400 bg-purple-400/20' :
                  'border-[var(--color-border)] bg-[var(--color-bg-card)]'
                }`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-[var(--color-text)]">{evt.event_type}</span>
                    <span className="text-[10px] text-[var(--color-text-muted)]">{new Date(evt.created_at).toLocaleTimeString()}</span>
                  </div>
                  {evt.payload && Object.keys(evt.payload).length > 0 && (
                    <pre className="text-[10px] text-[var(--color-text-muted)] mt-0.5 truncate">
                      {JSON.stringify(evt.payload)}
                    </pre>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
