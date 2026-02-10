import { useCallback, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import AgentNode from './nodes/AgentNode';
import StartEndNode from './nodes/StartEndNode';
import { layoutGraph, layoutSubGraph } from './useGraphLayout';
import type { GraphDefinition } from '@/types/graph';
import type { NodeMetadata } from '@/hooks/useCanvasMetadata';

const nodeTypes = {
  agent: AgentNode,
  startEnd: StartEndNode,
};

interface WorkflowCanvasProps {
  graphDef: GraphDefinition | null;
  showSubGraph: boolean;
  activeNodes?: Set<string>;
  metadata?: Record<string, NodeMetadata>;
  editable?: boolean;
}

export default function WorkflowCanvas({
  graphDef,
  showSubGraph,
  activeNodes,
  metadata,
  editable = false,
}: WorkflowCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Layout nodes when graph definition or sub-graph toggle changes
  useEffect(() => {
    if (!graphDef) return;

    const master = layoutGraph(graphDef);
    let allNodes = master.nodes;
    let allEdges = master.edges;

    if (showSubGraph && graphDef.subgraphs?.sub_agents) {
      const sub = layoutSubGraph(graphDef.subgraphs.sub_agents);
      const maxX = Math.max(...master.nodes.map((n) => n.position.x)) + 300;
      const subNodes = sub.nodes.map((n) => ({
        ...n,
        position: { x: n.position.x + maxX, y: n.position.y },
      }));
      allNodes = [...allNodes, ...subNodes];
      allEdges = [...allEdges, ...sub.edges];
    }

    setNodes(allNodes);
    setEdges(allEdges);
  }, [graphDef, showSubGraph, setNodes, setEdges]);

  // Merge metadata + activeNodes into node data
  useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => {
        const data = node.data as Record<string, unknown>;
        const nodeId = node.id.replace('sub_', '');
        const isActive = activeNodes
          ? activeNodes.has(nodeId) || activeNodes.has(node.id)
          : false;
        const nodeMeta = metadata?.[nodeId] ?? metadata?.[node.id];

        if (data.isActive !== isActive || data.metadata !== nodeMeta) {
          return { ...node, data: { ...data, isActive, metadata: nodeMeta } };
        }
        return node;
      })
    );
  }, [activeNodes, metadata, setNodes]);

  const onInit = useCallback(() => {}, []);

  return (
    <div className="w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onInit={onInit}
        nodeTypes={nodeTypes}
        nodesDraggable
        nodesConnectable={editable}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        className="bg-[var(--color-bg)]"
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1a1a1a" />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={(node) => {
            const provider = (node.data as Record<string, unknown>)?.modelProvider as string;
            if (provider === 'ollama') return '#4ade80';
            if (provider === 'openai') return '#60a5fa';
            if (provider === 'anthropic') return '#a78bfa';
            return '#555';
          }}
          maskColor="rgba(0,0,0,0.8)"
        />
      </ReactFlow>
    </div>
  );
}
