import {useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent} from "react";
import {createRoot} from "react-dom/client";
import {layoutGraph} from "./layout";
import {groupId, groupLabel, type Graph, type Layout, type Reader, type Rectangle, type Transition} from "./model";
import "./style.css";

const number = new Intl.NumberFormat("en", {maximumFractionDigits: 1});
const percent = new Intl.NumberFormat("en", {style: "percent", maximumFractionDigits: 1});
const pretty = (value: string) => value.replaceAll("_", " ");
const duration = (seconds: number) =>
  seconds >= 3600 ? `${number.format(seconds / 3600)} h` :
    seconds >= 60 ? `${number.format(seconds / 60)} min` : `${number.format(seconds)} s`;

function useGraph() {
  const [graph, setGraph] = useState<Graph>();
  const [error, setError] = useState("");
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let etag: string | null = null;
    const controller = new AbortController();
    async function update() {
      try {
        const response = await fetch("/api/topology", {
          headers: etag ? {"If-None-Match": etag} : {},
          cache: "no-store",
          signal: controller.signal,
        });
        if (response.status !== 304) {
          if (!response.ok) throw new Error("Graph unavailable");
          setGraph(await response.json());
          etag = response.headers.get("etag");
        }
        setError("");
      } catch {
        if (!controller.signal.aborted) setError("Graph unavailable. Run discovery to generate a graph.");
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(update, 3500);
      }
    }
    void update();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, []);
  return {graph, error};
}

function useLayout(graph: Graph) {
  const layoutKey = useMemo(() => JSON.stringify([
    graph.nodes.map(node => [node.id, groupId(node)]),
    graph.edges.map(edge => edge.id),
  ]), [graph]);
  const [placed, setPlaced] = useState<{id: string; layout: Layout}>();
  const [failed, setFailed] = useState<string>();
  useEffect(() => {
    const controller = new AbortController();
    void layoutGraph(graph, controller.signal).then(
      layout => {if (!controller.signal.aborted) setPlaced({id: layoutKey, layout});},
      () => {if (!controller.signal.aborted) setFailed(layoutKey);},
    );
    return () => controller.abort();
    // Only the identities and line groups affect the layout.
  }, [layoutKey]);
  return {layout: placed?.id === layoutKey ? placed.layout : undefined, failed: failed === layoutKey};
}

function KeyValues({items}: {items: Array<[string, string | number]>}) {
  return <dl>{items.map(([label, value]) => (
    <div key={label}><dt>{label}</dt><dd>{typeof value === "number" ? number.format(value) : value}</dd></div>
  ))}</dl>;
}

function Details({graph, reader, transition, onClear}: {
  graph: Graph; reader?: Reader; transition?: Transition; onClear: () => void;
}) {
  const names = new Map(graph.nodes.map(node => [node.id, node.label]));
  const excluded = Object.values(graph.quality.excludedPairs).reduce((sum, count) => sum + count, 0);
  return <aside className="details" aria-label="Graph details">
    <div className="panel-heading">
      <h2>{reader ? "Reader" : transition ? "Transition" : "Data quality"}</h2>
      {(reader || transition) && <button onClick={onClear} aria-label="Clear selection">×</button>}
    </div>
    {reader ? <>
      <h3>{reader.label}</h3>
      <p>{groupLabel(reader)}</p>
      {reader.description && <p>{reader.description}</p>}
      <KeyValues items={[
        ["Readings", reader.eventCount], ["Distinct case keys", reader.distinctCaseCount],
        ["Incoming transitions", graph.edges.filter(edge => edge.target === reader.id).length],
        ["Outgoing transitions", graph.edges.filter(edge => edge.source === reader.id).length],
        ...(reader.areaId ? [["Area", reader.areaId] as [string, string]] : []),
      ]}/>
      {reader.qualityFlags.map(flag => <p className="attention" key={flag}>{pretty(flag)}</p>)}
    </> : transition ? <>
      <h3>{names.get(transition.source)} → {names.get(transition.target)}</h3>
      <KeyValues items={[
        ["Observed passages", transition.transitionCount], ["Distinct case keys", transition.distinctCaseCount],
        ["Outgoing share", percent.format(transition.outgoingShare)], ["Active days (UTC)", transition.activeDaysUtc],
        ["Minimum duration", duration(transition.minDurationSeconds)],
        ["Median duration", duration(transition.medianDurationSeconds)],
        ["90th percentile", duration(transition.p90DurationSeconds)],
        ["Maximum duration", duration(transition.maxDurationSeconds)],
        ["Long gaps", transition.longGapCount],
      ]}/>
    </> : <>
      <p>{graph.source.fileCount} Parquet {graph.source.fileCount === 1 ? "file" : "files"}</p>
      <KeyValues items={[
        ["Input events", graph.quality.inputRows], ["Excluded pairs", excluded],
        ...Object.entries(graph.quality.excludedPairs).map(([key, count]): [string, number] => [pretty(key), count]),
        ["Events without case", graph.quality.missingCaseRows],
        ["Events without reader", graph.quality.missingReaderRows],
        ["Events without time", graph.quality.missingTimeRows],
        ["Deduplicated events", graph.quality.deduplicatedRows],
        ["Conflicting event keys", graph.quality.conflictingEventKeys],
        ["Repeated file contents", graph.source.repeatedContentFiles],
        ["Distinct observed variants", graph.variants.distinctVariantCount],
      ]}/>
    </>}
  </aside>;
}

function KeyboardSelect(event: KeyboardEvent<SVGGElement>, action: () => void) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    action();
  }
}

function Network({graph}: {graph: Graph}) {
  const {layout, failed} = useLayout(graph);
  const [filterLine, setLine] = useState("");
  const [minimum, setMinimum] = useState(1);
  const [search, setSearch] = useState("");
  const [selection, setSelection] = useState("");
  const [view, setView] = useState<Rectangle>();
  const drag = useRef<{x: number; y: number; base: Rectangle; pixel: number} | null>(null);
  const groups = useMemo(() => [...new Map(graph.nodes.map(reader => [groupId(reader), groupLabel(reader)]))]
    .sort(([, a], [, b]) => a.localeCompare(b)), [graph]);
  const line = groups.some(([id]) => id === filterLine) ? filterLine : "";
  useEffect(() => {setView(undefined);}, [layout]);
  const readers = graph.nodes.filter(reader => !line || line === groupId(reader));
  const visibleIds = new Set(readers.map(reader => reader.id));
  const transitions = graph.edges.filter(edge =>
    edge.transitionCount >= minimum && visibleIds.has(edge.source) && visibleIds.has(edge.target));
  const nodes = new Map(graph.nodes.map(reader => [reader.id, reader]));
  const activeReader = nodes.get(selection);
  const activeEdge = graph.edges.find(edge => edge.id === selection);
  const connected = new Set(transitions.filter(edge => edge.source === selection || edge.target === selection)
    .flatMap(edge => [edge.source, edge.target]));
  const query = search.trim().toLowerCase();
  const results = query ? readers.filter(reader =>
    [reader.label, groupLabel(reader), reader.description ?? ""].some(text => text.toLowerCase().includes(query)))
    .slice(0, 10) : [];

  const fullView = layout && {x: 0, y: 0, width: layout.width, height: layout.height};
  const groupView = line && layout?.groups.find(group => group.id === line) || undefined;
  const currentView = view ?? groupView ?? fullView;
  function zoom(factor: number) {
    if (!currentView || !fullView) return;
    const width = Math.max(fullView.width * 0.045, Math.min(fullView.width * 2.5, currentView.width * factor));
    const scale = width / currentView.width;
    const height = currentView.height * scale;
    setView({
      x: currentView.x + (currentView.width - width) / 2,
      y: currentView.y + (currentView.height - height) / 2,
      width, height,
    });
  }

  function focus(reader: Reader) {
    setSearch("");
    setSelection(reader.id);
    const box = layout?.nodes[reader.id];
    if (box) setView({x: box.x - 204, y: box.y - 160, width: box.width + 408, height: box.height + 320});
  }

  function beginPan(event: PointerEvent<SVGSVGElement>) {
    if (!currentView || event.button !== 0) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const pixel = Math.max(currentView.width / bounds.width, currentView.height / bounds.height);
    drag.current = {x: event.clientX, y: event.clientY, base: currentView, pixel};
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function movePan(event: PointerEvent<SVGSVGElement>) {
    const start = drag.current;
    if (!start) return;
    setView({...start.base,
      x: start.base.x - (event.clientX - start.x) * start.pixel,
      y: start.base.y - (event.clientY - start.y) * start.pixel,
    });
  }

  function exportLayout() {
    if (!layout) return;
    const content = JSON.stringify({topologyId: graph.topologyId, ...layout}, null, 2);
    const href = URL.createObjectURL(new Blob([content], {type: "application/json"}));
    const link = document.createElement("a");
    link.href = href;
    link.download = "production-layout.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(href), 1000);
  }

  return <>
    <section className="stats" aria-label="Graph metrics">
      <div><span>Readers</span><strong>{number.format(graph.nodes.length)}</strong></div>
      <div><span>Directed links</span><strong>{number.format(graph.edges.length)}</strong></div>
      <div><span>Observed transitions</span><strong>{number.format(graph.quality.includedPairs)}</strong></div>
      <div><span>Line groups</span><strong>{number.format(groups.length)}</strong></div>
    </section>
    <section className="workbench" aria-label="Production graph">
      <div className="toolbar">
        <label className="search">
          <span>Find a reader</span>
          <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Reader, line or description"/>
        </label>
        {query && <div className="search-results">
          {results.length ? results.map(reader => <button key={reader.id} onClick={() => focus(reader)}>
            {reader.label}<small>{groupLabel(reader)}</small>
          </button>) : <p>No readers match.</p>}
        </div>}
        <label><span>Line</span>
          <select value={line} onChange={event => {setLine(event.target.value); setView(undefined); setSelection("");}}>
            <option value="">All lines</option>
            {groups.map(([id, label]) => <option value={id} key={id}>{label}</option>)}
          </select>
        </label>
        <label><span>Min. transitions</span>
          <input type="number" min={1} value={minimum}
            onChange={event => setMinimum(Math.max(1, Math.floor(Number(event.target.value))))}/>
        </label>
        <button className="export" disabled={!layout || !graph.nodes.length} onClick={exportLayout}>Export layout</button>
      </div>
      <div className="workspace">
        <div className="diagram">
          {failed ? <p className="empty">The automatic layout could not load.</p>
            : !graph.nodes.length ? <p className="empty">No valid readers were found in this dataset.</p>
              : !layout || !currentView ? <p className="empty" role="status">Arranging readers…</p>
                : <>
                  <svg className="network" role="group" aria-label="Reader transition diagram"
                    viewBox={`${currentView.x} ${currentView.y} ${currentView.width} ${currentView.height}`}
                    onPointerDown={beginPan} onPointerMove={movePan}
                    onPointerUp={() => {drag.current = null;}} onPointerCancel={() => {drag.current = null;}}>
                    <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3"
                      orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L8 3L0 6Z" fill="context-stroke"/></marker></defs>
                    {layout.groups.filter(group => !line || group.id === line).map(group => (
                      <g className="lane" key={group.id}>
                        <rect x={group.x} y={group.y} width={group.width} height={group.height} rx="12"/>
                        <text x={group.x + 14} y={group.y + 25}>{group.label}</text>
                      </g>
                    ))}
                    {transitions.map(edge => {
                      const related = selection === edge.id || selection === edge.target || selection === edge.source;
                      const dim = selection && !related ? " dim" : "";
                      const label = `${nodes.get(edge.source)?.label} to ${nodes.get(edge.target)?.label}`;
                      const select = () => setSelection(edge.id);
                      return <g className={`transition${related ? " related" : ""}${dim}`} key={edge.id} role="button"
                        aria-label={label} tabIndex={0} onClick={select} onKeyDown={event => KeyboardSelect(event, select)}
                        onPointerDown={event => event.stopPropagation()}>
                        <title>{label} · {edge.transitionCount}</title>
                        {layout.edges[edge.id].map((section, index, sections) => {
                          const points = section.map(point => `${point.x},${point.y}`).join(" ");
                          return <g key={index}>
                            <polyline className="edge-hit" points={points}/>
                            <polyline points={points} className={edge.longGapCount > 0 ? "edge gap" : "edge"}
                              strokeWidth={Math.min(4.5, 1.4 + Math.log10(edge.transitionCount) / 1.5)}
                              markerEnd={index === sections.length - 1 ? "url(#arrow)" : undefined}/>
                          </g>;
                        })}
                      </g>;
                    })}
                    {readers.map(reader => {
                      const box = layout.nodes[reader.id];
                      const selected = reader.id === selection;
                      const dim = activeReader && !selected && !connected.has(reader.id) ? " dim" : "";
                      const select = () => setSelection(reader.id);
                      return <g className={`reader${selected ? " selected" : ""}${dim}`} key={reader.id}
                        transform={`translate(${box.x} ${box.y})`} role="button" tabIndex={0}
                        aria-label={`Reader ${reader.label} · ${groupLabel(reader)}`} onClick={select}
                        onKeyDown={event => KeyboardSelect(event, select)} onPointerDown={event => event.stopPropagation()}>
                        <title>{reader.label} · {groupLabel(reader)}</title>
                        <rect width={box.width} height={box.height} rx="9"/>
                        <text x="13" y="25" className="reader-name">{reader.label.length > 15 ? `${reader.label.slice(0, 14)}…` : reader.label}</text>
                        <text x="13" y="43">{number.format(reader.eventCount)} readings</text>
                      </g>;
                    })}
                  </svg>
                  <div className="camera" aria-label="View controls">
                    <button onClick={() => zoom(0.72)} aria-label="Zoom in">+</button>
                    <button onClick={() => zoom(1.38)} aria-label="Zoom out">−</button>
                    <button onClick={() => setView(undefined)}>Fit</button>
                  </div>
                  <span className="visible-count">{readers.length} readers · {transitions.length} links</span>
                </>}
        </div>
        <Details graph={graph} reader={activeReader} transition={activeEdge} onClear={() => setSelection("")}/>
      </div>
    </section>
  </>;
}

function App() {
  const {graph, error} = useGraph();
  return <main>
    <header>
      <div className="identity"><div className="mark" aria-hidden="true">FIS</div>
        <div><h1>Production network</h1><p>Observed reader transitions</p></div>
      </div>
      {graph?.mappingStatus === "synthetic" && <span className="data-status">Synthetic data</span>}
      {graph?.mappingStatus === "candidate" && <span className="data-status provisional">Provisional mapping</span>}
    </header>
    {error && <p className="attention" role="alert">{error}{graph && " Showing the last loaded graph."}</p>}
    {graph ? <Network graph={graph}/> : !error && <p role="status">Loading graph…</p>}
  </main>;
}

createRoot(document.getElementById("root")!).render(<App/>);
