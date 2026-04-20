import React, { useEffect, useRef, useState } from "react";
import { DataSet, Network } from "vis-network/standalone";
import { Download, Loader2, AlertCircle } from "lucide-react";

const NetworkGraph = ({ authorId, onNodeSelect, expandTrigger, selectedAuthorName }) => {
  const containerRef = useRef(null);
  const networkRef = useRef(null);

  const [isLoading, setIsLoading] = useState(true);
  const [noData, setNoData] = useState(false);

  // DataSets are reactive containers
  const nodesRef = useRef(new DataSet([]));
  const edgesRef = useRef(new DataSet([]));

  const handleExportGraphJSON = () => {
    const nodes = nodesRef.current.get();
    const edges = edgesRef.current.get();

    if (nodes.length === 0) return;

    const dataStr = JSON.stringify({ nodes, edges }, null, 2);
    const blob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);

    const fileName = selectedAuthorName 
      ? `${selectedAuthorName.trim().replace(/\s+/g, '_')}_Network.json`
      : `Author_${authorId}_Network.json`;

    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const loadNetworkData = async (id) => {
    setIsLoading(true);
    setNoData(false);
    
    try {
      const response = await fetch(`http://localhost:8000/viz/author-network/${id}`);
      if (!response.ok) throw new Error("Graph API error");

      const data = await response.json();
      
      if (!data.edges || data.edges.length === 0) {
        setNoData(true);
      }

      // Update Nodes (vis-network automatically merges objects with matching IDs)
      if (data.nodes && data.nodes.length > 0) {
        nodesRef.current.update(
          data.nodes.map((n) => ({
            ...n,
            label: n.full_title || n.label,
            shape: "dot",
            size: n.group === "work" ? 12 : 20,
            font: { color: "#f8fafc", size: 12, face: "Inter, sans-serif" },
            borderWidth: 2,
            color: {
              border: n.group === "work" ? "#2d7a74" : "#475569",
              background: n.group === "work" ? "#4ecdc4" : "#94a3b8",
              highlight: { background: "#ffffff", border: "#4ecdc4" },
            },
          }))
        );
      }

      if (data.edges && data.edges.length > 0) {
        edgesRef.current.update(
          data.edges.map((e) => ({
            ...e,
            font: { size: 9, color: "#475569", strokeWidth: 0, align: "middle" },
            color: { color: "#334155", highlight: "#4ecdc4" },
            arrows: { to: { enabled: true, scaleFactor: 0.4 } },
            smooth: { type: "continuous" },
          }))
        );
      }

      if (networkRef.current) {
        networkRef.current.fit({ animation: true });
      }
    } catch (err) {
      console.error("Graph Load failed:", err);
      setNoData(true);
    } finally {
      setIsLoading(false);
    }
  };

  // INITIAL LOAD
  useEffect(() => {
    if (!authorId || !containerRef.current) return;

    const initGraph = async () => {
      nodesRef.current.clear();
      edgesRef.current.clear();

      // 1. IMMEDIATELY add the root node so the canvas is never empty
      nodesRef.current.add({
        id: authorId,
        label: selectedAuthorName || "Selected Entity",
        group: "author",
        shape: "dot",
        size: 25,
        font: { color: "#ffffff", size: 14, face: "Inter, sans-serif", bold: true },
        borderWidth: 3,
        color: {
          border: "#4ecdc4",
          background: "#0d1117",
          highlight: { background: "#ffffff", border: "#4ecdc4" },
        },
      });

      // 2. Initialize the Vis Network instance immediately
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

      networkRef.current = new Network(
        containerRef.current,
        { nodes: nodesRef.current, edges: edgesRef.current },
        options
      );

      networkRef.current.on("selectNode", (params) => {
        const nodeId = params.nodes[0];
        const nodeData = nodesRef.current.get(nodeId);
        if (onNodeSelect) onNodeSelect(nodeData);
      });

      // 3. Kick off the fetch for the rest of the network
      await loadNetworkData(authorId);
    };

    initGraph();
  }, [authorId, selectedAuthorName, onNodeSelect]);

  // EXPANSION LOAD
  useEffect(() => {
    if (expandTrigger) {
      loadNetworkData(expandTrigger);
    }
  }, [expandTrigger]);

  return (
    <div style={{ position: "relative", height: "100%", minHeight: "600px", width: "100%" }}>
      
      {/* Floating UI Elements */}
      <div className="absolute top-4 left-4 z-10 flex flex-col gap-2 pointer-events-none">
        {isLoading && (
          <div className="flex items-center gap-2 bg-slate-800/80 backdrop-blur-sm text-aegis-cyan text-xs px-4 py-2 rounded border border-slate-700 shadow-lg">
            <Loader2 size={14} className="animate-spin" />
            Analyzing Connections...
          </div>
        )}
        {noData && !isLoading && (
          <div className="flex items-center gap-2 bg-slate-800/80 backdrop-blur-sm text-yellow-500 text-xs px-4 py-2 rounded border border-yellow-500/30 shadow-lg">
            <AlertCircle size={14} />
            No external connections found.
          </div>
        )}
      </div>

      <div className="absolute top-4 right-4 z-10">
        <button
          onClick={handleExportGraphJSON}
          className="flex items-center gap-2 bg-slate-800 hover:bg-aegis-cyan hover:text-[#0d1117] text-slate-300 text-xs px-4 py-2 rounded transition-colors font-bold tracking-wider uppercase border border-slate-700 hover:border-aegis-cyan shadow-lg"
        >
          <Download size={14} />
          Export JSON
        </button>
      </div>

      {/* Vis Network Canvas */}
      <div
        data-testid="network-container"
        ref={containerRef}
        style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%" }}
        className="bg-[#0a0c10] cursor-grab active:cursor-grabbing"
      />
    </div>
  );
};

export default NetworkGraph;