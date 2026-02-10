import dagre from 'dagre';
import type { Node, Edge } from '@xyflow/react';
import type { GraphDefinition } from '@/types/graph';

const NODE_WIDTH = 180;
const NODE_HEIGHT = 70;

export function layoutGraph(graphDef: GraphDefinition): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', ranksep: 80, nodesep: 60 });

  for (const node of graphDef.nodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const edge of graphDef.edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  const nodes: Node[] = graphDef.nodes.map((n) => {
    const pos = g.node(n.id);
    return {
      id: n.id,
      type: n.node_type === 'terminal' ? 'startEnd' : 'agent',
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      data: {
        label: n.label,
        nodeType: n.node_type,
        modelId: n.model_id,
        modelProvider: n.model_provider,
        isActive: false,
      },
    };
  });

  const edges: Edge[] = graphDef.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    animated: e.conditional,
    style: {
      stroke: e.conditional ? '#555' : '#444',
      strokeWidth: 2,
      strokeDasharray: e.conditional ? '6 3' : undefined,
    },
    label: e.label,
    labelStyle: { fill: '#888', fontSize: 10 },
    labelBgStyle: { fill: '#0a0a0a', fillOpacity: 0.8 },
  }));

  return { nodes, edges };
}

export function layoutSubGraph(graphDef: GraphDefinition): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', ranksep: 60, nodesep: 50 });

  for (const node of graphDef.nodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const edge of graphDef.edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  const nodes: Node[] = graphDef.nodes.map((n) => {
    const pos = g.node(n.id);
    return {
      id: `sub_${n.id}`,
      type: n.node_type === 'terminal' ? 'startEnd' : 'agent',
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      data: {
        label: n.label,
        nodeType: n.node_type,
        modelId: n.model_id,
        modelProvider: n.model_provider,
        isActive: false,
      },
    };
  });

  const edges: Edge[] = graphDef.edges.map((e) => ({
    id: `sub_${e.id}`,
    source: `sub_${e.source}`,
    target: `sub_${e.target}`,
    animated: false,
    style: { stroke: '#fb923c55', strokeWidth: 2 },
  }));

  return { nodes, edges };
}
