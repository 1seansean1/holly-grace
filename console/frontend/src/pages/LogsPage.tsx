import { useEffect, useRef, useState } from 'react';
import Header from '@/components/layout/Header';
import { useLogStream, type LogEntry } from '@/hooks/useLogStream';

const LEVEL_COLORS: Record<string, string> = {
  error: '#ef4444',
  warning: '#f59e0b',
  info: '#3b82f6',
  debug: '#6b7280',
};

const AGENT_COLORS: Record<string, string> = {
  orchestrator: '#4ade80',
  sales_marketing: '#60a5fa',
  operations: '#60a5fa',
  revenue_analytics: '#a78bfa',
  sub_agents: '#fb923c',
};

export default function LogsPage() {
  const { logs, clearLogs } = useLogStream();
  const [pinToBottom, setPinToBottom] = useState(true);
  const [levelFilter, setLevelFilter] = useState<string | null>(null);
  const [agentFilter, setAgentFilter] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (pinToBottom && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, pinToBottom]);

  const filteredLogs = logs.filter((log) => {
    if (levelFilter && log.level !== levelFilter) return false;
    if (agentFilter && log.agent !== agentFilter) return false;
    return true;
  });

  return (
    <div className="flex flex-col h-full">
      <Header title="Logs" subtitle="Real-time streaming logs" />

      {/* Filters */}
      <div className="flex items-center gap-3 px-4 py-2 bg-[var(--color-bg-card)] border-b border-[var(--color-border)]">
        <span className="text-xs text-[var(--color-text-muted)]">Level:</span>
        {['error', 'warning', 'info', 'debug'].map((level) => (
          <button
            key={level}
            onClick={() => setLevelFilter(levelFilter === level ? null : level)}
            style={{
              padding: '2px 8px',
              borderRadius: 4,
              fontSize: 11,
              fontWeight: 500,
              border: '1px solid',
              borderColor: levelFilter === level ? LEVEL_COLORS[level] : 'var(--color-border)',
              background: levelFilter === level ? `${LEVEL_COLORS[level]}22` : 'transparent',
              color: LEVEL_COLORS[level],
              cursor: 'pointer',
            }}
          >
            {level.toUpperCase()}
          </button>
        ))}
        <span className="text-xs text-[var(--color-text-muted)] ml-3">Agent:</span>
        {['orchestrator', 'sales_marketing', 'operations', 'revenue_analytics', 'sub_agents'].map(
          (agent) => (
            <button
              key={agent}
              onClick={() => setAgentFilter(agentFilter === agent ? null : agent)}
              style={{
                padding: '2px 8px',
                borderRadius: 4,
                fontSize: 11,
                fontWeight: 500,
                border: '1px solid',
                borderColor:
                  agentFilter === agent ? AGENT_COLORS[agent] : 'var(--color-border)',
                background:
                  agentFilter === agent ? `${AGENT_COLORS[agent]}22` : 'transparent',
                color: AGENT_COLORS[agent] || 'var(--color-text)',
                cursor: 'pointer',
              }}
            >
              {agent.replace('_', ' ')}
            </button>
          )
        )}
        <div className="ml-auto flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] cursor-pointer">
            <input
              type="checkbox"
              checked={pinToBottom}
              onChange={(e) => setPinToBottom(e.target.checked)}
              className="accent-[var(--color-accent)]"
            />
            Auto-scroll
          </label>
          <button
            onClick={clearLogs}
            style={{
              padding: '2px 8px',
              borderRadius: 4,
              fontSize: 11,
              border: '1px solid var(--color-border)',
              background: 'transparent',
              color: 'var(--color-text-muted)',
              cursor: 'pointer',
            }}
          >
            Clear
          </button>
          <span className="text-xs text-[var(--color-text-muted)]">
            {filteredLogs.length} entries
          </span>
        </div>
      </div>

      {/* Log entries */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto font-mono"
        style={{ fontSize: 12, lineHeight: '20px' }}
      >
        {filteredLogs.length === 0 ? (
          <div className="flex items-center justify-center h-full text-[var(--color-text-muted)] text-sm">
            {logs.length === 0
              ? 'Waiting for log events...'
              : 'No logs match current filters'}
          </div>
        ) : (
          filteredLogs.map((log, i) => <LogLine key={i} log={log} />)
        )}
      </div>
    </div>
  );
}

function LogLine({ log }: { log: LogEntry }) {
  const time = log.timestamp
    ? new Date(log.timestamp * 1000).toLocaleTimeString()
    : '';

  return (
    <div
      className="px-4 py-0.5 hover:bg-[var(--color-bg-card)] border-b border-[var(--color-border)]"
      style={{ display: 'flex', gap: 8 }}
    >
      <span style={{ color: 'var(--color-text-muted)', minWidth: 70 }}>{time}</span>
      <span
        style={{
          color: LEVEL_COLORS[log.level] || '#888',
          minWidth: 50,
          fontWeight: 600,
          textTransform: 'uppercase',
          fontSize: 10,
          lineHeight: '20px',
        }}
      >
        {log.level}
      </span>
      {log.agent && (
        <span
          style={{
            color: AGENT_COLORS[log.agent] || 'var(--color-text-muted)',
            minWidth: 100,
            fontSize: 11,
          }}
        >
          [{log.agent}]
        </span>
      )}
      <span style={{ color: 'var(--color-text)', flex: 1, wordBreak: 'break-all' }}>
        {log.message}
      </span>
    </div>
  );
}
