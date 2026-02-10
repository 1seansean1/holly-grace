/**
 * Hook that subscribes to /ws/execution for real-time graph execution events.
 * Tracks active nodes and maintains an event log.
 */

import { useEffect, useState, useCallback } from 'react';
import { WebSocketManager } from '@/lib/ws';

export interface ExecutionEvent {
  type: string;
  node?: string;
  tool?: string;
  model?: string;
  run_id?: string;
  timestamp?: number;
  error?: string;
  inputs_preview?: string;
  outputs_preview?: string;
  output_preview?: string;
  token_usage?: Record<string, number>;
  level?: string;
  message?: string;
  status?: string;
}

const MAX_EVENTS = 200;

export function useExecutionStream() {
  const [activeNodes, setActiveNodes] = useState<Set<string>>(new Set());
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = WebSocketManager.get('/ws/execution');

    const unsub = ws.subscribe(
      (raw) => {
        const event = raw as ExecutionEvent;

        // Track active nodes
        if (event.type === 'node_entered' && event.node) {
          setActiveNodes((prev) => new Set([...prev, event.node!]));
        }
        if (event.type === 'node_exited' && event.node) {
          setActiveNodes((prev) => {
            const next = new Set(prev);
            next.delete(event.node!);
            return next;
          });
        }
        if (event.type === 'node_error' && event.node) {
          setActiveNodes((prev) => {
            const next = new Set(prev);
            next.delete(event.node!);
            return next;
          });
        }

        // Append to event log (skip log-type events — handled by LogsPage)
        if (event.type !== 'log' && event.type !== 'bridge_status') {
          setEvents((prev) => {
            const next = [...prev, event];
            return next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next;
          });
        }
      },
      (isConnected) => setConnected(isConnected)
    );

    return unsub;
  }, []);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { activeNodes, events, connected, clearEvents };
}
