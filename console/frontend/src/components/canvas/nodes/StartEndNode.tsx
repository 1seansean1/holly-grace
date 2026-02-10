import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';

interface StartEndData {
  label: string;
  [key: string]: unknown;
}

function StartEndNode({ data, id }: NodeProps) {
  const d = data as StartEndData;
  const isStart = id.includes('start');
  return (
    <div
      className={`px-4 py-2 rounded-full border-2 text-xs font-bold ${
        isStart
          ? 'border-green-500/60 text-green-400 bg-green-950/30'
          : 'border-red-400/60 text-red-400 bg-red-950/30'
      }`}
    >
      {!isStart && <Handle type="target" position={Position.Top} className="!bg-gray-600 !w-2 !h-2 !border-0" />}
      {d.label}
      {isStart && <Handle type="source" position={Position.Bottom} className="!bg-gray-600 !w-2 !h-2 !border-0" />}
    </div>
  );
}

export default memo(StartEndNode);
