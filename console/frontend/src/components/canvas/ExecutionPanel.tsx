/**
 * Side panel showing real-time execution events and invoke control.
 */

import { useState } from 'react';
import type { ExecutionEvent } from '@/hooks/useExecutionStream';

interface ExecutionPanelProps {
  events: ExecutionEvent[];
  activeNodes: Set<string>;
  connected: boolean;
  onClearEvents: () => void;
}

const EVENT_COLORS: Record<string, string> = {
  node_entered: '#22c55e',
  node_exited: '#3b82f6',
  node_error: '#ef4444',
  llm_start: '#a855f7',
  llm_end: '#a855f7',
  tool_start: '#f59e0b',
  tool_end: '#f59e0b',
  bridge_status: '#6b7280',
};

const EVENT_ICONS: Record<string, string> = {
  node_entered: '\u25B6',
  node_exited: '\u2714',
  node_error: '\u2716',
  llm_start: '\u2726',
  llm_end: '\u2726',
  tool_start: '\u2692',
  tool_end: '\u2692',
};

export default function ExecutionPanel({
  events,
  activeNodes,
  connected,
  onClearEvents,
}: ExecutionPanelProps) {
  const [task, setTask] = useState('');
  const [invoking, setInvoking] = useState(false);

  const handleInvoke = async () => {
    if (!task.trim() || invoking) return;
    setInvoking(true);
    try {
      await fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: task.trim() }),
      });
    } catch {
      /* errors handled by event stream */
    } finally {
      setInvoking(false);
    }
  };

  return (
    <div
      style={{
        width: 320,
        borderLeft: '1px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--color-bg)',
        fontSize: 13,
      }}
    >
      {/* Invoke Section */}
      <div style={{ padding: '12px', borderBottom: '1px solid var(--color-border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <span style={{ fontWeight: 600 }}>Invoke Agent</span>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: connected ? '#22c55e' : '#ef4444',
            }}
          />
        </div>
        <textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="Enter a task for the agent..."
          rows={2}
          style={{
            width: '100%',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 6,
            padding: '8px',
            color: 'var(--color-text)',
            resize: 'none',
            fontFamily: 'inherit',
            fontSize: 12,
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleInvoke();
          }}
        />
        <button
          onClick={handleInvoke}
          disabled={invoking || !task.trim()}
          style={{
            marginTop: 6,
            width: '100%',
            padding: '6px 12px',
            background: invoking ? '#666' : 'var(--color-accent)',
            color: '#fff',
            border: 'none',
            borderRadius: 6,
            cursor: invoking ? 'wait' : 'pointer',
            fontWeight: 500,
            fontSize: 12,
          }}
        >
          {invoking ? 'Executing...' : 'Run Task (Ctrl+Enter)'}
        </button>
      </div>

      {/* Active Nodes */}
      {activeNodes.size > 0 && (
        <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--color-border)' }}>
          <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 11, color: '#22c55e' }}>
            ACTIVE NODES
          </div>
          {[...activeNodes].map((node) => (
            <div
              key={node}
              style={{
                display: 'inline-block',
                padding: '2px 8px',
                margin: '2px',
                borderRadius: 4,
                background: '#22c55e22',
                border: '1px solid #22c55e44',
                fontSize: 11,
              }}
            >
              {node}
            </div>
          ))}
        </div>
      )}

      {/* Event Feed */}
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px 4px' }}>
        <span style={{ fontWeight: 600, fontSize: 11, color: 'var(--color-text-muted)' }}>
          EVENTS ({events.length})
        </span>
        <button
          onClick={onClearEvents}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--color-text-muted)',
            cursor: 'pointer',
            fontSize: 10,
          }}
        >
          Clear
        </button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 12px 12px' }}>
        {events.length === 0 ? (
          <div
            style={{
              color: 'var(--color-text-muted)',
              textAlign: 'center',
              padding: 24,
              fontSize: 12,
            }}
          >
            No events yet. Invoke a task or wait for a scheduled job.
          </div>
        ) : (
          [...events].reverse().map((event, i) => (
            <div
              key={i}
              style={{
                padding: '4px 0',
                borderBottom: '1px solid var(--color-border)',
                fontSize: 11,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ color: EVENT_COLORS[event.type] || '#888' }}>
                  {EVENT_ICONS[event.type] || '\u2022'}
                </span>
                <span style={{ fontWeight: 500 }}>{event.type}</span>
                {event.node && (
                  <span style={{ color: 'var(--color-text-muted)' }}>{event.node}</span>
                )}
                {event.tool && (
                  <span style={{ color: '#f59e0b' }}>{event.tool}</span>
                )}
                {event.timestamp && (
                  <span
                    style={{
                      marginLeft: 'auto',
                      color: 'var(--color-text-muted)',
                      fontSize: 10,
                    }}
                  >
                    {new Date(event.timestamp * 1000).toLocaleTimeString()}
                  </span>
                )}
              </div>
              {event.error && (
                <div style={{ color: '#ef4444', fontSize: 10, marginTop: 2 }}>{event.error}</div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
