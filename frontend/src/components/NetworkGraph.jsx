import React, { useEffect, useRef, useState, useCallback } from "react";
import React, { useEffect, useRef, useState, useCallback } from "react";
import { DataSet, Network } from "vis-network/standalone";
import { Download, Loader2, AlertCircle } from "lucide-react";

const NetworkGraph = ({ authorId, onNodeSelect, expandTrigger, selectedAuthorName, activeFilters, onDataLoad }) => {
  const containerRef = useRef(null);
  const networkRef = useRef(null);
  const [isLoading, setIsLoading] = useState(true);
  const [noData, setNoData] = useState(false);
  const nodesRef = useRef(new DataSet([]));
  const edgesRef = useRef(new DataSet([]));

  const handleExportGraphJSON = () => {
    const nodes = nodesRef.current.get();
    const edges = edgesRef.current.get();
    if (nodes.length === 0) return;
    const dataStr = JSON.stringify({ nodes, edges }, null, 2);
    const blob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const fileName = selectedAuthorName ? `${selectedAuthorName.trim().replace(/\s+/g, '_')}_Network.json` : `Author_${authorId}_Network.json`;
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const loadNetworkData = useCallback(async (id) => {
    setIsLoading(true);
    setNoData(false);
    try {
      const response = await fetch(`/api/viz/author-network/${id}`);
      if (!response.ok) throw new Error("Graph API error");
      const data = await response.json();
      if (onDataLoad) onDataLoad(data);
      if (onDataLoad) onDataLoad(data);

      if (!data.edges || data.edges.length === 0) setNoData(true);

      if (data.nodes && data.nodes.length > 0) {
        nodesRef.current.clear();
        nodesRef.current.clear();
        nodesRef.current.update(
          data.nodes.map((n) => {
            const isAuthor = n.id === authorId || n.group === "author";
            const isWork = n.group === "work";

            return {
              ...n,
              label: n.full_title || n.label,
              shape: "dot",
              size: isAuthor ? 25 : isWork ? 12 : 20, // Distinguish by size
              font: { color: "#f8fafc", size: isAuthor ? 14 : 11, face: "Inter, sans-serif", bold: isAuthor },
              borderWidth: isAuthor ? 3 : 2,
              color: {
                border: isAuthor ? "#4ecdc4" : isWork ? "#2563eb" : "#7c3aed",
                background: isAuthor ? "#0d1117" : isWork ? "#3b82f6" : "#8b5cf6",
                highlight: { background: "#ffffff", border: "#4ecdc4" },
              },
            };
          })
        );
      }

      if (data.edges && data.edges.length > 0) {
        edgesRef.current.clear();
        edgesRef.current.clear();
        edgesRef.current.update(
          data.edges.map((e) => ({
            ...e,
            font: { size: 9, color: "#6c97c0", strokeWidth: 0, align: "top", vadjust: -1 },
            color: { color: "#334155", highlight: "#4ecdc4" },
            arrows: { to: { enabled: true, scaleFactor: 0.4 } },
            smooth: { type: "continuous" },
          }))
        );
      }

      if (networkRef.current) {
        networkRef.current.fit({ animation: true });
        networkRef.current?.selectNodes?.([authorId]);
        const centralNode = nodesRef.current.get(authorId);
        if (onNodeSelect) onNodeSelect(centralNode);
      }
    } catch (err) {
      console.error("❌ Graph Load failed:", err);
      setNoData(true);
    } finally {
      setIsLoading(false);
    }
  }, [authorId, onDataLoad, onNodeSelect]);

  useEffect(() => {
    const initGraph = async () => {
      if (!nodesRef.current || !edgesRef.current) return;
      nodesRef.current.clear();
      edgesRef.current.clear();

      const options = {
        nodes: { widthConstraint: { maximum: 200 } },
        physics: {
          enabled: true,
          forceAtlas2Based: { gravitationalConstant: -100, springLength: 100, springConstant: 0.08 },
          solver: "forceAtlas2Based",
          stabilization: { iterations: 150, updateInterval: 25 },
        },
        interaction: { hover: true, tooltipDelay: 200, hideEdgesOnDrag: true, selectable: true },
      };

      if (networkRef.current) networkRef.current.destroy();
      networkRef.current = new Network(containerRef.current, { nodes: nodesRef.current, edges: edgesRef.current }, options);

      networkRef.current.on("stabilizationIterationsDone", () => {
        if (networkRef.current) {
          networkRef.current.setOptions({ physics: { enabled: false } });
        }
      });

      networkRef.current.on("selectNode", (params) => {
        const nodeId = params.nodes[0];
        const nodeData = nodesRef.current.get(nodeId);
        if (onNodeSelect) onNodeSelect(nodeData);
      });

      await loadNetworkData(authorId);
    };
    initGraph();
  }, [authorId, selectedAuthorName, onNodeSelect, loadNetworkData]);

  useEffect(() => {
    if (expandTrigger) loadNetworkData(expandTrigger);
  }, [expandTrigger, loadNetworkData]);

  useEffect(() => {
    if (!nodesRef.current || !activeFilters) return;
    const allNodes = nodesRef.current.get();
    const update = allNodes.map(node => {
      let hidden = false;
      if (node.group === 'work') {
        if (activeFilters.year !== 'all' && node.year !== activeFilters.year) hidden = true;
      }
      if (node.group === 'organization') {
        if (activeFilters.organization !== 'all' && node.label !== activeFilters.organization) hidden = true;
      }
      if (node.id === authorId) hidden = false;
      return { id: node.id, hidden: hidden };
    });
    nodesRef.current.update(update);
    if (networkRef.current) networkRef.current.fit({ animation: { duration: 500 } });
  }, [activeFilters, authorId]);

  return (
    <div style={{ position: "relative", height: "100%", minHeight: "600px", width: "100%" }}>
      <div className="absolute top-4 left-4 z-10 flex flex-col gap-2 pointer-events-none">
        {isLoading && (
          <div className="flex items-center gap-2 bg-slate-800/80 backdrop-blur-sm text-aegis-cyan text-xs px-4 py-2 rounded border border-slate-700 shadow-lg">
            <Loader2 size={14} className="animate-spin" /> Analyzing Connections...
          </div>
        )}
        {noData && !isLoading && (
          <div className="flex items-center gap-2 bg-slate-800/80 backdrop-blur-sm text-yellow-500 text-xs px-4 py-2 rounded border border-yellow-500/30 shadow-lg">
            <AlertCircle size={14} /> No external connections found.
          </div>
        )}
      </div>
      <div className="absolute top-4 right-4 z-10">
        <button onClick={handleExportGraphJSON} className="flex items-center gap-2 bg-slate-800 hover:bg-aegis-cyan hover:text-[#0d1117] text-slate-300 text-xs px-4 py-2 rounded transition-colors font-bold tracking-wider border border-slate-700 shadow-lg">
          <Download size={14} /> Export JSON
        </button>
      </div>
      <div ref={containerRef} data-testid="network-container" style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%" }} className="bg-[#0a0c10] cursor-grab active:cursor-grabbing" />
    </div>
  );
};

export default NetworkGraph;
