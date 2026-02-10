import { useState, useEffect, useCallback } from 'react';
import { ShieldCheck, ShieldAlert, Clock, XCircle, CheckCircle, RefreshCw, AlertTriangle } from 'lucide-react';

interface Approval {
  id: number;
  action_type: string;
  agent_id: string | null;
  tool_name: string;
  parameters: Record<string, unknown>;
  risk_level: string;
  status: string;
  requested_at: string;
  decided_at: string | null;
  decided_by: string | null;
  expires_at: string;
  reason: string;
}

const RISK_COLORS: Record<string, string> = {
  high: 'bg-red-500/20 text-red-400 border-red-500/30',
  medium: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  low: 'bg-green-500/20 text-green-400 border-green-500/30',
};

const STATUS_ICONS: Record<string, typeof ShieldCheck> = {
  pending: Clock,
  approved: CheckCircle,
  rejected: XCircle,
  expired: AlertTriangle,
};

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [filter, setFilter] = useState<'pending' | 'all'>('pending');
  const [loading, setLoading] = useState(true);

  const fetchApprovals = useCallback(async () => {
    try {
      const resp = await fetch(`/api/approvals?status=${filter}`);
      const data = await resp.json();
      setApprovals(data.approvals || []);
    } catch {
      setApprovals([]);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchApprovals();
    const interval = setInterval(fetchApprovals, 5000);
    return () => clearInterval(interval);
  }, [fetchApprovals]);

  const handleDecision = async (id: number, decision: 'approve' | 'reject') => {
    try {
      await fetch(`/api/approvals/${id}/${decision}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decided_by: 'console' }),
      });
      fetchApprovals();
    } catch (err) {
      console.error('Failed to process approval:', err);
    }
  };

  const pending = approvals.filter(a => a.status === 'pending');

  return (
    <div className="flex flex-col h-full">
      <div className="shrink-0 px-6 pt-6 pb-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldCheck size={24} className="text-[var(--color-accent)]" />
          <h1 className="text-xl font-semibold">Approval Queue</h1>
          {pending.length > 0 && (
            <span className="bg-[var(--color-accent)] text-white text-xs font-bold px-2 py-0.5 rounded-full">
              {pending.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setFilter(filter === 'pending' ? 'all' : 'pending')}
            className="px-3 py-1.5 text-xs rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] transition-colors"
          >
            {filter === 'pending' ? 'Show All' : 'Pending Only'}
          </button>
          <button
            onClick={fetchApprovals}
            className="p-1.5 rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] transition-colors"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-6">
      {loading ? (
        <div className="text-center text-[var(--color-text-muted)] py-12">Loading...</div>
      ) : approvals.length === 0 ? (
        <div className="text-center py-16">
          <ShieldCheck size={48} className="mx-auto mb-4 text-[var(--color-text-muted)] opacity-30" />
          <p className="text-[var(--color-text-muted)]">
            {filter === 'pending' ? 'No pending approvals' : 'No approval history'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {approvals.map(approval => {
            const StatusIcon = STATUS_ICONS[approval.status] || Clock;
            return (
              <div
                key={approval.id}
                className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-4"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${RISK_COLORS[approval.risk_level] || RISK_COLORS.medium}`}>
                        {approval.risk_level.toUpperCase()}
                      </span>
                      <code className="text-sm font-mono text-[var(--color-text)]">{approval.tool_name}</code>
                      {approval.agent_id && (
                        <span className="text-xs text-[var(--color-text-muted)]">
                          via {approval.agent_id}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-[var(--color-text-muted)] space-y-1">
                      <div>
                        <span className="opacity-60">Params: </span>
                        <code className="text-[var(--color-text-muted)]">
                          {JSON.stringify(approval.parameters).slice(0, 120)}
                          {JSON.stringify(approval.parameters).length > 120 ? '...' : ''}
                        </code>
                      </div>
                      <div>
                        <span className="opacity-60">Requested: </span>
                        {new Date(approval.requested_at).toLocaleString()}
                        <span className="opacity-60 ml-3">Expires: </span>
                        {new Date(approval.expires_at).toLocaleString()}
                      </div>
                      {approval.decided_at && (
                        <div>
                          <span className="opacity-60">Decided: </span>
                          {new Date(approval.decided_at).toLocaleString()}
                          <span className="opacity-60 ml-2">by</span> {approval.decided_by}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {approval.status === 'pending' ? (
                      <>
                        <button
                          onClick={() => handleDecision(approval.id, 'approve')}
                          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-green-600/20 text-green-400 border border-green-500/30 hover:bg-green-600/30 transition-colors"
                        >
                          <CheckCircle size={14} /> Approve
                        </button>
                        <button
                          onClick={() => handleDecision(approval.id, 'reject')}
                          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-red-600/20 text-red-400 border border-red-500/30 hover:bg-red-600/30 transition-colors"
                        >
                          <XCircle size={14} /> Reject
                        </button>
                      </>
                    ) : (
                      <span className={`flex items-center gap-1 px-2 py-1 text-xs rounded-lg ${
                        approval.status === 'approved' ? 'text-green-400' :
                        approval.status === 'rejected' ? 'text-red-400' :
                        'text-[var(--color-text-muted)]'
                      }`}>
                        <StatusIcon size={14} />
                        {approval.status}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
      </div>
    </div>
  );
}
