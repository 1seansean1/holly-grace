import { useEffect, useRef, useState } from 'react';
import { fetchJson } from '@/lib/api';

export interface NodeMetadata {
  channel_id: string;
  p_fail: number | null;
  last_latency_ms: number | null;
  tool_count: number;
  version: number;
  model_id: string;
  capacity: number | null;
  n_observations: number;
}

interface MetadataResponse {
  nodes: Record<string, NodeMetadata>;
}

const POLL_INTERVAL_MS = 10_000;

export function useCanvasMetadata() {
  const [metadata, setMetadata] = useState<Record<string, NodeMetadata>>({});
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const poll = () => {
      fetchJson<MetadataResponse>('/api/graph/metadata')
        .then((res) => setMetadata(res.nodes))
        .catch(() => {});
    };

    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return metadata;
}
