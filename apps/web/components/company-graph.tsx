"use client";

import { Background, Controls, Edge, Node, ReactFlow } from "@xyflow/react";

const nodes: Node[] = [
  { id: "decision", position: { x: 20, y: 130 }, data: { label: "Remove Beacon + Echo" }, className: "graph-node decision" },
  { id: "enrichment", position: { x: 260, y: 50 }, data: { label: "Lead enrichment" }, className: "graph-node workflow" },
  { id: "targeting", position: { x: 260, y: 210 }, data: { label: "Campaign targeting" }, className: "graph-node workflow" },
  { id: "sales", position: { x: 520, y: 35 }, data: { label: "Sales pipeline" }, className: "graph-node impact" },
  { id: "marketing", position: { x: 520, y: 195 }, data: { label: "Acquisition cost" }, className: "graph-node impact" },
];

const edges: Edge[] = [
  { id: "d-e", source: "decision", target: "enrichment", animated: true },
  { id: "d-t", source: "decision", target: "targeting", animated: true },
  { id: "e-s", source: "enrichment", target: "sales" },
  { id: "t-m", source: "targeting", target: "marketing" },
];

export function CompanyGraph() {
  return (
    <div className="graph-frame" aria-label="Organizational blast radius">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false} nodesConnectable={false}>
        <Background gap={24} size={1} color="rgba(126, 160, 151, .16)" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

