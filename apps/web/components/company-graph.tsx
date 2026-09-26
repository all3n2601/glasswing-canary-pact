"use client";

import type { BlastEdge, BlastNode, BlastRadius, DecisionPackage, DomainGraph, Edge as DomainEdge, Entity, Impact } from "@canary-pact/contracts/generated";
import { Background, Controls, MiniMap, type Edge, type Node, ReactFlow } from "@xyflow/react";
import { CalendarClock, FileText, Filter, Search, ShieldAlert, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type GraphMode = "twin" | "blast";
type SelectedItem = { kind: "node"; id: string } | { kind: "edge"; id: string } | null;

const typeOrder = ["vendor", "dataset", "workflow", "system", "department", "kpi", "control", "knowledge_asset", "role", "customer_segment", "project"];
const levelOrder = ["direct", "dependent", "second_order", "delayed", "feedback"];
const typeColors: Record<string, string> = {
  vendor: "#2563eb",
  dataset: "#7c3aed",
  workflow: "#0891b2",
  system: "#475569",
  department: "#18181b",
  kpi: "#d97706",
  control: "#059669",
  knowledge_asset: "#9333ea",
  role: "#64748b",
  customer_segment: "#db2777",
  project: "#0f766e",
  decision: "#18181b",
  outcome: "#0f766e",
};

function title(value?: string | null) {
  return value ? value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) : "Unclassified";
}

function nodeStyle(color: string, selected = false) {
  const borderColor = selected ? color : "#e4e4e7";

  return {
    width: 196,
    borderRadius: 16,
    borderTop: `1px solid ${borderColor}`,
    borderRight: `1px solid ${borderColor}`,
    borderBottom: `1px solid ${borderColor}`,
    borderLeft: `5px solid ${color}`,
    background: "rgba(255,255,255,.97)",
    boxShadow: selected ? `0 14px 34px ${color}22` : "0 8px 24px rgb(0 0 0 / .06)",
    padding: 12,
    color: "#18181b",
    fontSize: 11,
  } as const;
}

function TwinNodeLabel({ entity, onSelect }: { entity: Entity; onSelect: () => void }) {
  return <button type="button" aria-label={`Inspect ${entity.name}`} className="nodrag w-full text-left" onFocus={onSelect} onPointerDown={(event) => { event.stopPropagation(); onSelect(); }} onClick={(event) => { event.stopPropagation(); onSelect(); }}><span className="text-[8px] font-bold uppercase tracking-[.12em] text-zinc-400">{title(entity.type)}</span><strong className="mt-1 block text-xs leading-4">{entity.name}</strong>{entity.criticality ? <span className="mt-1 block text-[9px] text-zinc-500">{title(entity.criticality)} criticality</span> : null}</button>;
}

function BlastNodeLabel({ node, entity, onSelect }: { node: BlastNode; entity?: Entity; onSelect: () => void }) {
  return <button type="button" aria-label={`Inspect ${entity?.name ?? node.headline}`} className="nodrag w-full text-left" onFocus={onSelect} onPointerDown={(event) => { event.stopPropagation(); onSelect(); }} onClick={(event) => { event.stopPropagation(); onSelect(); }}><span className="text-[8px] font-bold uppercase tracking-[.12em] text-zinc-400">{node.kind === "entity" ? title(entity?.type) : title(node.kind)}</span><strong className="mt-1 block text-xs leading-4">{entity?.name ?? node.headline}</strong>{entity?.name ? <span className="mt-1 block text-[9px] leading-3 text-zinc-500">{node.headline.replaceAll("_", " ")}</span> : null}<span className="mt-2 flex items-center gap-1.5 text-[8px] font-semibold uppercase text-zinc-400">{node.level ? title(node.level) : node.kind}{node.first_effect_day !== null && node.first_effect_day !== undefined ? ` · day ${node.first_effect_day}` : ""}</span></button>;
}

function twinLayout(entities: Entity[], selected: SelectedItem, onSelect: (id: string) => void): Node[] {
  const grouped = new Map<string, Entity[]>();
  entities.forEach((entity) => grouped.set(entity.type, [...(grouped.get(entity.type) ?? []), entity]));
  const orderedTypes = [...grouped.keys()].sort((left, right) => {
    const leftIndex = typeOrder.indexOf(left);
    const rightIndex = typeOrder.indexOf(right);
    return (leftIndex < 0 ? 99 : leftIndex) - (rightIndex < 0 ? 99 : rightIndex);
  });
  return orderedTypes.flatMap((type, column) => (grouped.get(type) ?? []).map((entity, row) => ({
    id: entity.id,
    position: { x: column * 250, y: row * 105 },
    data: { label: <TwinNodeLabel entity={entity} onSelect={() => onSelect(entity.id)} /> },
    style: nodeStyle(typeColors[entity.type] ?? "#71717a", selected?.kind === "node" && selected.id === entity.id),
  })));
}

function blastLayout(blast: BlastRadius, entities: Map<string, Entity>, day: number, selected: SelectedItem, onSelect: (id: string) => void): Node[] {
  const visible = (blast.nodes ?? []).filter((node) => node.first_effect_day === null || node.first_effect_day === undefined || node.first_effect_day <= day);
  const visibleLevels = levelOrder.filter((level) => visible.some((node) => node.level === level));
  const grouped = new Map<number, BlastNode[]>();
  visible.forEach((node) => {
    const column = node.kind === "decision" ? 0 : node.kind === "outcome" ? visibleLevels.length + 1 : Math.max(0, visibleLevels.indexOf(node.level ?? "direct")) + 1;
    grouped.set(column, [...(grouped.get(column) ?? []), node]);
  });
  return [...grouped.entries()].flatMap(([column, nodes]) => nodes.map((node, row) => {
    const entity = entities.get(node.entity_id ?? node.node_id);
    const color = node.kind === "outcome" ? typeColors.outcome : node.kind === "decision" ? typeColors.decision : node.polarity === "harm" ? "#e11d48" : "#059669";
    return {
      id: node.node_id,
      position: { x: column * 255, y: row * 125 },
      data: { label: <BlastNodeLabel node={node} entity={entity} onSelect={() => onSelect(node.node_id)} /> },
      style: nodeStyle(color, selected?.kind === "node" && selected.id === node.node_id),
    };
  }));
}

function twinEdges(edges: DomainEdge[], visibleIds: Set<string>, selected: SelectedItem): Edge[] {
  return edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target)).map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.label ?? title(edge.relation),
    style: { stroke: selected?.kind === "edge" && selected.id === edge.id ? "#2563eb" : edge.criticality === "critical" ? "#e11d48" : "#a1a1aa", strokeWidth: edge.criticality === "critical" ? 2 : 1.2 },
    labelStyle: { fontSize: 8, fill: "#71717a" },
  }));
}

function blastEdges(edges: BlastEdge[], visibleIds: Set<string>, selected: SelectedItem): Edge[] {
  return edges.map((edge, index) => ({ edge, index })).filter(({ edge }) => visibleIds.has(edge.source) && visibleIds.has(edge.target)).map(({ edge, index }) => {
    const id = `blast_${edge.source}_${edge.target}_${index}`;
    return {
      id,
      source: edge.source,
      target: edge.target,
      label: title(edge.level ?? edge.label),
      animated: true,
      style: { stroke: selected?.kind === "edge" && selected.id === id ? "#2563eb" : edge.critical_constraint ? "#e11d48" : "#64748b", strokeWidth: edge.critical_constraint ? 2.5 : 1.5 },
      labelStyle: { fontSize: 8, fill: edge.critical_constraint ? "#be123c" : "#52525b", fontWeight: 600 },
    };
  });
}

function EvidenceInspector({ selected, graph, blast, decisionPackage, onClose }: { selected: SelectedItem; graph: DomainGraph; blast?: BlastRadius | null; decisionPackage?: DecisionPackage | null; onClose: () => void }) {
  if (!selected) return null;
  const entities = graph.nodes ?? [];
  const domainEdges = graph.edges ?? [];
  const entity = selected.kind === "node" ? entities.find((item) => item.id === selected.id) : undefined;
  const blastNode = selected.kind === "node" ? blast?.nodes?.find((item) => item.node_id === selected.id) : undefined;
  const blastEdgeIndex = selected.kind === "edge" && selected.id.startsWith("blast_") ? Number(selected.id.split("_").at(-1)) : -1;
  const blastEdge = blastEdgeIndex >= 0 ? blast?.edges?.[blastEdgeIndex] : undefined;
  const domainEdge = selected.kind === "edge" ? domainEdges.find((item) => item.id === selected.id) : undefined;
  const blastSource = blast?.nodes?.find((item) => item.node_id === blastEdge?.source);
  const blastTarget = blast?.nodes?.find((item) => item.node_id === blastEdge?.target);
  const result = decisionPackage?.portfolios.recommended?.result ?? decisionPackage?.portfolios.naive.result;
  const impact = blastNode?.impact_ids?.map((id) => result?.impacts?.find((item) => item.impact_id === id)).find(Boolean) as Impact | undefined;
  const connected = entity ? domainEdges.filter((edge) => edge.source === entity.id || edge.target === entity.id) : [];
  const evidence = [...new Set([...(entity?.evidence_refs ?? []), ...(impact?.evidence_refs ?? []), ...(domainEdge?.evidence_refs ?? []), ...connected.flatMap((edge) => edge.evidence_refs ?? [])])];
  const heading = entity?.name ?? blastNode?.headline ?? domainEdge?.label ?? title(blastEdge?.label) ?? selected.id;

  return <aside className="absolute bottom-20 right-4 top-40 z-20 flex w-[min(350px,calc(100%-32px))] flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-white/97 shadow-[0_24px_70px_rgb(0_0_0/.18)] backdrop-blur-xl">
    <header className="flex items-start justify-between gap-3 border-b border-zinc-100 p-4"><div><Badge variant="outline" className="border-zinc-200 uppercase tracking-[.1em] text-zinc-500">{selected.kind === "edge" ? "Dependency" : blastNode ? "Impact node" : "Twin node"}</Badge><h2 className="mt-3 text-xl font-semibold tracking-[-.035em]">{heading}</h2></div><Button variant="ghost" size="icon" onClick={onClose} aria-label="Close evidence inspector"><X /></Button></header>
    <div className="flex-1 space-y-5 overflow-y-auto p-4">
      {blastNode ? <section className="grid grid-cols-2 gap-2">{[["Impact level", title(blastNode.level)], ["Category", title(blastNode.category)], ["Severity", blastNode.severity ? `${blastNode.severity} / 5` : "Not scored"], ["First effect", blastNode.first_effect_day !== null && blastNode.first_effect_day !== undefined ? `Day ${blastNode.first_effect_day}` : "Baseline"]].map(([label, value]) => <div className="rounded-xl bg-zinc-50 p-3" key={label}><span className="text-[8px] uppercase tracking-[.1em] text-zinc-400">{label}</span><strong className="mt-1 block text-xs">{value}</strong></div>)}</section> : null}
      {impact ? <section><h3 className="text-[9px] font-bold uppercase tracking-[.12em] text-zinc-400">Calculated impact</h3><div className="mt-2 rounded-xl border border-zinc-200 p-3"><strong className="text-xs">{title(impact.metric)}</strong><p className="mt-1 text-[10px] leading-4 text-zinc-500">{impact.direction} by {Math.abs(impact.magnitude)} {impact.unit} · {Math.round(impact.confidence * 100)}% confidence</p></div></section> : null}
      {domainEdge || blastEdge ? <section><h3 className="text-[9px] font-bold uppercase tracking-[.12em] text-zinc-400">Relationship</h3><dl className="mt-2 space-y-2 rounded-xl border border-zinc-200 p-3 text-[10px]"><div className="flex justify-between gap-3"><dt className="text-zinc-500">From</dt><dd className="font-semibold">{entities.find((item) => item.id === (domainEdge?.source ?? blastEdge?.source))?.name ?? blastSource?.headline ?? domainEdge?.source ?? blastEdge?.source}</dd></div><div className="flex justify-between gap-3"><dt className="text-zinc-500">To</dt><dd className="font-semibold">{entities.find((item) => item.id === (domainEdge?.target ?? blastEdge?.target))?.name ?? blastTarget?.headline ?? domainEdge?.target ?? blastEdge?.target}</dd></div>{domainEdge ? <><div className="flex justify-between gap-3"><dt className="text-zinc-500">Confidence</dt><dd className="font-semibold">{Math.round(domainEdge.confidence * 100)}%</dd></div><div className="flex justify-between gap-3"><dt className="text-zinc-500">Validated</dt><dd className="font-semibold">{domainEdge.last_validated ?? "Not recorded"}</dd></div></> : null}</dl></section> : null}
      {entity ? <section><h3 className="text-[9px] font-bold uppercase tracking-[.12em] text-zinc-400">Connected dependencies</h3><p className="mt-2 text-xs text-zinc-600">{connected.length} incoming or outgoing relationship{connected.length === 1 ? "" : "s"} in the current twin.</p></section> : null}
      <section><h3 className="flex items-center gap-2 text-[9px] font-bold uppercase tracking-[.12em] text-zinc-400"><FileText className="size-3.5" />Evidence references</h3>{evidence.length ? <ul className="mt-2 space-y-2">{evidence.map((reference) => <li key={reference} className="rounded-xl border border-zinc-200 px-3 py-2 text-[10px] font-medium text-zinc-600">{reference}</li>)}</ul> : <div className="mt-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-[10px] text-amber-800">No evidence reference is attached to this item.</div>}</section>
    </div>
  </aside>;
}

export function CompanyGraph({ graph, blastRadius, decisionPackage, day, loading, error }: { graph: DomainGraph | null; blastRadius?: BlastRadius | null; decisionPackage?: DecisionPackage | null; day: number; loading: boolean; error: string | null }) {
  const [mode, setMode] = useState<GraphMode>(blastRadius ? "blast" : "twin");
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [selected, setSelected] = useState<SelectedItem>(null);
  useEffect(() => {
    if (blastRadius) {
      setMode("blast");
      setSelected(null);
    }
  }, [blastRadius]);
  const baseGraph = graph ?? { nodes: [], edges: [] };
  const entities = baseGraph.nodes ?? [];
  const entityMap = useMemo(() => new Map(entities.map((entity) => [entity.id, entity])), [entities]);
  const availableTypes = useMemo(() => [...new Set(entities.map((entity) => entity.type))].sort(), [entities]);
  const filteredEntities = useMemo(() => entities.filter((entity) => (typeFilter === "all" || entity.type === typeFilter) && (!search.trim() || `${entity.name} ${entity.id}`.toLowerCase().includes(search.trim().toLowerCase()))), [entities, search, typeFilter]);
  const nodes = useMemo(() => {
    const onSelect = (id: string) => setSelected({ kind: "node", id });
    return mode === "blast" && blastRadius ? blastLayout(blastRadius, entityMap, day, selected, onSelect) : twinLayout(filteredEntities, selected, onSelect);
  }, [blastRadius, day, entityMap, filteredEntities, mode, selected]);
  const visibleIds = useMemo(() => new Set(nodes.map((node) => node.id)), [nodes]);
  const edges = useMemo(() => mode === "blast" && blastRadius ? blastEdges(blastRadius.edges ?? [], visibleIds, selected) : twinEdges(baseGraph.edges ?? [], visibleIds, selected), [baseGraph.edges, blastRadius, mode, selected, visibleIds]);

  if (loading) return <div className="absolute inset-0 grid place-items-center bg-zinc-50 pt-20"><div className="text-center"><div className="mx-auto size-10 animate-pulse rounded-2xl bg-zinc-200" /><p className="mt-3 text-xs text-zinc-500">Loading company dependencies…</p></div></div>;
  if (error) return <div className="absolute inset-0 grid place-items-center bg-zinc-50 pt-20"><div className="max-w-sm rounded-2xl border border-rose-100 bg-white p-6 text-center"><ShieldAlert className="mx-auto size-5 text-rose-600" /><strong className="mt-3 block text-sm">The dependency graph is unavailable.</strong><p className="mt-2 text-xs text-zinc-500">{error}</p></div></div>;

  return <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_35%,white,#eef2ef_80%)] pt-20" aria-label={mode === "blast" ? "Organizational blast radius" : "Company dependency graph"}>
    <ReactFlow key={`${mode}-${nodes.length}`} nodes={nodes} edges={edges} fitView fitViewOptions={{ padding: 0.24 }} minZoom={0.18} maxZoom={1.5} nodesDraggable={false} nodesConnectable={false} onNodeClick={(_, node) => setSelected({ kind: "node", id: node.id })} onEdgeClick={(_, edge) => setSelected({ kind: "edge", id: edge.id })}>
      <Background gap={24} size={1} color="rgba(113,113,122,.16)" />
      <Controls showInteractive={false} position="bottom-right" />
      <MiniMap pannable zoomable nodeColor={(node) => String(node.style?.borderLeft ?? "#71717a").split(" ").at(-1) ?? "#71717a"} className="!rounded-xl !border !border-zinc-200 !bg-white/90" />
    </ReactFlow>

    <div className="absolute left-4 top-[92px] z-10 w-[min(340px,calc(100%-32px))] rounded-2xl border border-white bg-white/95 p-3 shadow-[0_14px_40px_rgb(0_0_0/.1)] backdrop-blur-xl">
      <div className="flex items-center justify-between gap-3"><div><span className="text-[8px] font-bold uppercase tracking-[.14em] text-zinc-400">Graph view</span><strong className="mt-0.5 block text-xs">{mode === "blast" ? "Decision blast radius" : "Company twin"}</strong></div>{blastRadius ? <div className="flex rounded-lg bg-zinc-100 p-1"><button type="button" onClick={() => { setMode("twin"); setSelected(null); }} className={`rounded-md px-2.5 py-1.5 text-[9px] font-semibold ${mode === "twin" ? "bg-white text-zinc-950 shadow-sm" : "text-zinc-500"}`}>Twin</button><button type="button" onClick={() => { setMode("blast"); setSelected(null); }} className={`rounded-md px-2.5 py-1.5 text-[9px] font-semibold ${mode === "blast" ? "bg-zinc-950 text-white" : "text-zinc-500"}`}>Blast radius</button></div> : null}</div>
      {mode === "twin" ? <div className="mt-3 grid grid-cols-[1fr_120px] gap-2"><label className="relative"><Search className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-zinc-400" /><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search nodes" className="h-9 border-zinc-200 pl-9 text-xs" /></label><label className="relative"><Filter className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-zinc-400" /><select aria-label="Filter node type" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} className="h-9 w-full rounded-xl border border-zinc-200 bg-white pl-8 pr-2 text-[10px]"><option value="all">All types</option>{availableTypes.map((type) => <option key={type} value={type}>{title(type)}</option>)}</select></label></div> : <div className="mt-3 flex flex-wrap gap-1.5">{levelOrder.map((level) => <Badge key={level} variant="outline" className="border-zinc-200 bg-white text-[8px] text-zinc-500"><span className={`mr-1 size-1.5 rounded-full ${level === "direct" ? "bg-blue-500" : level === "dependent" ? "bg-violet-500" : level === "second_order" ? "bg-rose-500" : level === "delayed" ? "bg-amber-500" : "bg-emerald-500"}`} />{title(level)}</Badge>)}</div>}
      <select aria-label="Inspect graph item" value={selected ? `${selected.kind}:${selected.id}` : ""} onChange={(event) => { const [kind, ...idParts] = event.target.value.split(":"); setSelected(event.target.value ? { kind: kind as "node" | "edge", id: idParts.join(":") } : null); }} className="mt-2 h-8 w-full rounded-xl border border-zinc-200 bg-white px-2 text-[10px] text-zinc-600">
        <option value="">Inspect a node or dependency…</option>
        <optgroup label="Nodes">{nodes.map((node) => <option key={node.id} value={`node:${node.id}`}>{entityMap.get(node.id)?.name ?? blastRadius?.nodes?.find((item) => item.node_id === node.id)?.headline ?? node.id}</option>)}</optgroup>
        {edges.length ? <optgroup label="Dependencies">{edges.map((edge) => <option key={edge.id} value={`edge:${edge.id}`}>{String(edge.label ?? edge.id)}</option>)}</optgroup> : null}
      </select>
      <div className="mt-3 flex items-center justify-between border-t border-zinc-100 pt-2 text-[9px] text-zinc-500"><span>{nodes.length} nodes · {edges.length} dependencies</span>{mode === "blast" ? <span className="flex items-center gap-1"><CalendarClock className="size-3" />Through day {day}</span> : <span>Click a node or edge</span>}</div>
    </div>

    <EvidenceInspector selected={selected} graph={baseGraph} blast={mode === "blast" ? blastRadius : null} decisionPackage={decisionPackage} onClose={() => setSelected(null)} />
  </div>;
}
