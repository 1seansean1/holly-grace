import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import ModelBadge from '../../shared/ModelBadge';
import type { NodeMetadata } from '@/hooks/useCanvasMetadata';

interface AgentNodeData {
  label: string;
  nodeType: string;
  modelId?: string;
  modelProvider?: string;
  isActive?: boolean;
  metadata?: NodeMetadata;
  [key: string]: unknown;
}

const NODE_TYPE_STYLES: Record<string, string> = {
  orchestrator: 'border-green-500/60 bg-green-950/40',
  agent: 'border-blue-500/60 bg-blue-950/40',
  sub_agent: 'border-orange-500/60 bg-orange-950/40',
  error_handler: 'border-red-500/60 bg-red-950/40',
};

const NODE_TYPE_ICONS: Record<string, string> = {
  orchestrator: '\u{1F9ED}',
  agent: '\u{1F916}',
  sub_agent: '\u{26A1}',
  error_handler: '\u{1F6E1}',
};

function pFailColor(p: number | null | undefined): string {
  if (p == null) return '#888';
  if (p < 0.1) return '#4ade80';
  if (p < 0.3) return '#facc15';
  return '#ef4444';
}

function AgentNode({ data }: NodeProps) {
  const d = data as AgentNodeData;
  const style = NODE_TYPE_STYLES[d.nodeType] ?? 'border-gray-500/60 bg-gray-950/40';
  const icon = NODE_TYPE_ICONS[d.nodeType] ?? '';
  const meta = d.metadata;

  return (
    <div
      className={`px-4 py-3 rounded-xl border-2 min-w-[160px] ${style} ${d.isActive ? 'node-active' : ''}`}
    >
      <Handle type="target" position={Position.Top} className="!bg-gray-600 !w-2 !h-2 !border-0" />
      <div className="flex items-center gap-2 mb-1">
        <span className="text-sm">{icon}</span>
        <span className="text-sm font-semibold text-[var(--color-text)]">{d.label}</span>
      </div>
      {d.modelProvider && (
        <ModelBadge modelId={d.modelId} provider={d.modelProvider} />
      )}
      {meta && (
        <div className="mt-1.5 flex items-center gap-1.5 text-[10px] text-[var(--color-text-muted)] font-mono leading-tight">
          <span>{meta.channel_id}</span>
          <span style={{ color: '#555' }}>&middot;</span>
          <span style={{ color: pFailColor(meta.p_fail) }}>
            p={meta.p_fail != null ? meta.p_fail.toFixed(2) : '\u2014'}
          </span>
          <span style={{ color: '#555' }}>&middot;</span>
          <span>{meta.last_latency_ms != null ? `${Math.round(meta.last_latency_ms)}ms` : '\u2014'}</span>
          <span style={{ color: '#555' }}>&middot;</span>
          <span>{meta.tool_count}t</span>
          <span style={{ color: '#555' }}>&middot;</span>
          <span>v{meta.version}</span>
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-gray-600 !w-2 !h-2 !border-0" />
    </div>
  );
}

export default memo(AgentNode);
