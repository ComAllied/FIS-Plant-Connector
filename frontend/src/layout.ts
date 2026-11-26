import ELK, {type ElkNode} from "elkjs/lib/elk-api.js";
import workerUrl from "elkjs/lib/elk-worker.min.js?url";
import {groupId, groupLabel, type Graph, type Layout, type Point} from "./model";

const CARD_WIDTH = 154;
const CARD_HEIGHT = 58;

function groupsFor(graph: Graph) {
  const groups = new Map<string, {label: string; nodes: string[]}>();
  for (const node of graph.nodes) {
    const id = groupId(node);
    if (!groups.has(id)) groups.set(id, {label: groupLabel(node), nodes: []});
    groups.get(id)!.nodes.push(node.id);
  }
  return [...groups].sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0);
}

function gridLayout(graph: Graph): Layout {
  const layout: Layout = {
    engine: "grouped-grid", version: 1, width: 0, height: 0, groups: [], nodes: {}, edges: {},
  };
  let top = 28;
  for (const [id, group] of groupsFor(graph)) {
    const columns = Math.min(8, group.nodes.length);
    const rows = Math.ceil(group.nodes.length / columns);
    const width = 64 + columns * 208;
    const height = 64 + rows * 102;
    layout.groups.push({id, label: group.label, x: 28, y: top, width, height});
    group.nodes.forEach((node, index) => {
      layout.nodes[node] = {
        x: 64 + index % columns * 208, y: top + 52 + Math.floor(index / columns) * 102,
        width: CARD_WIDTH, height: CARD_HEIGHT,
      };
    });
    top += height + 28;
    layout.width = Math.max(layout.width, width + 56);
  }
  layout.height = top;
  for (const edge of graph.edges) {
    const source = layout.nodes[edge.source];
    const target = layout.nodes[edge.target];
    const from = {x: source.x + source.width, y: source.y + source.height / 2};
    const to = {x: target.x, y: target.y + target.height / 2};
    if (edge.source === edge.target) {
      layout.edges[edge.id] = [[
        from, {x: from.x + 14, y: from.y}, {x: from.x + 14, y: source.y - 14},
        {x: source.x - 14, y: source.y - 14}, {x: source.x - 14, y: to.y}, to,
      ]];
    } else if (target.x >= source.x + source.width) {
      layout.edges[edge.id] = [[from, to]];
    } else if (target.x + target.width <= source.x) {
      layout.edges[edge.id] = [[
        {x: source.x, y: from.y}, {x: target.x + target.width, y: to.y},
      ]];
    } else {
      const down = target.y >= source.y + source.height;
      layout.edges[edge.id] = [[
        {x: source.x + source.width / 2, y: source.y + (down ? source.height : 0)},
        {x: target.x + target.width / 2, y: target.y + (down ? 0 : target.height)},
      ]];
    }
  }
  return layout;
}

async function layeredLayout(graph: Graph, elk: InstanceType<typeof ELK>): Promise<Layout> {
  const groups = groupsFor(graph);
  const labels = new Map(groups.map(([id, group]) => [id, group.label]));
  const root: ElkNode = {
    id: "production-network",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.hierarchyHandling": "INCLUDE_CHILDREN",
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.layered.spacing.nodeNodeBetweenLayers": "72",
      "elk.spacing.componentComponent": "32",
      "elk.spacing.nodeNode": "34",
      "elk.padding": "[top=28,left=28,bottom=28,right=28]",
      "elk.randomSeed": "1",
    },
    children: groups.map(([id, group]) => ({
      id,
      layoutOptions: {
        "elk.padding": "[top=46,left=20,bottom=20,right=20]",
        "elk.spacing.nodeNode": "34",
      },
      children: group.nodes.map(node => ({id: node, width: CARD_WIDTH, height: CARD_HEIGHT})),
    })),
    edges: graph.edges.map(edge => ({id: edge.id, sources: [edge.source], targets: [edge.target]})),
  };
  const placed = await elk.layout(root);
  const result: Layout = {
    engine: "elk-layered", version: 1, width: placed.width!, height: placed.height!,
    groups: [], nodes: {}, edges: {},
  };
  const origin: Record<string, Point> = {[placed.id]: {x: 0, y: 0}};
  for (const group of placed.children ?? []) {
    const box = {x: group.x!, y: group.y!, width: group.width!, height: group.height!};
    origin[group.id] = box;
    result.groups.push({...box, id: group.id, label: labels.get(group.id)!});
    for (const node of group.children ?? []) {
      result.nodes[node.id] = {
        x: box.x + node.x!, y: box.y + node.y!, width: CARD_WIDTH, height: CARD_HEIGHT,
      };
    }
  }
  for (const edge of placed.edges ?? []) {
    const offset = origin[edge.container ?? placed.id] ?? origin[placed.id];
    result.edges[edge.id] = (edge.sections ?? []).map(section =>
      [section.startPoint, ...(section.bendPoints ?? []), section.endPoint].map(point => ({
        x: point.x + offset.x, y: point.y + offset.y,
      })),
    );
  }
  if (graph.nodes.some(node => !result.nodes[node.id]) ||
      graph.edges.some(edge => !result.edges[edge.id]?.length)) {
    throw new Error("Incomplete layout");
  }
  return result;
}

export async function layoutGraph(graph: Graph, signal: AbortSignal): Promise<Layout> {
  if (!graph.nodes.length || graph.nodes.length > 220 || graph.edges.length > 700) {
    return gridLayout(graph);
  }
  const elk = new ELK({workerUrl});
  const stop = () => elk.terminateWorker();
  signal.addEventListener("abort", stop, {once: true});
  try {
    return await layeredLayout(graph, elk);
  } catch {
    return gridLayout(graph);
  } finally {
    signal.removeEventListener("abort", stop);
    if (!signal.aborted) stop();
  }
}
