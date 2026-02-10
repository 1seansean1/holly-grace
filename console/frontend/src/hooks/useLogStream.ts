/**
 * Hook that subscribes to /ws/logs for streaming log events.
 */

import { useEffect, useState, useCallback } from 'react';
import { WebSocketManager } from '@/lib/ws';

export interface LogEntry {
  type: 'log';
  level: string;
  logger: string;
  message: string;
  agent: string | null;
  timestamp: number;
}

const MAX_LOGS = 1000;

export function useLogStream() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = WebSocketManager.get('/ws/logs');

    const unsub = ws.subscribe(
      (raw) => {
        const event = raw as LogEntry;
        if (event.type === 'log') {
          setLogs((prev) => {
            const next = [...prev, event];
            return next.length > MAX_LOGS ? next.slice(-MAX_LOGS) : next;
          });
        }
      },
      (isConnected) => setConnected(isConnected)
    );

    return unsub;
  }, []);

  const clearLogs = useCallback(() => setLogs([]), []);

  return { logs, connected, clearLogs };
}
