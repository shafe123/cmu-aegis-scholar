import React, { useEffect, useRef } from 'react';
import { DataSet, Network } from 'vis-network/standalone';

const NetworkGraph = ({ authorId, onNodeSelect, expandTrigger }) => {
  const containerRef = useRef(null);
  const networkRef = useRef(null);
  
  // DataSets are reactive containers that allow adding data without a full refresh
  const nodesRef = useRef(new DataSet([]));
  const edgesRef = useRef(new DataSet([]));

  /**
   * Fetches data from the Graph API and updates the local DataSet.
   * Using .update() prevents duplicate ID errors.
   */
  const loadNetworkData = async (id) => {
    console.log("📡 Fetching network for ID:", id);
    try {
      const response = await fetch(`http://localhost:8000/viz/author-network/${id}`);
      if (!response.ok) throw new Error("Graph API error");
      
      const data = await response.json();
      console.log("📦 RAW DATA RECEIVED:", data);
      
      if (!data.nodes || data.nodes.length === 0) {
        console.warn("⚠️ No nodes found for this ID.");
        return;
      }

      // Update Nodes: Apply Aegis styling & Force Full Label
      nodesRef.current.update(data.nodes.map(n => ({
        ...n,
        label: n.full_title || n.label, // <-- FIX: Uses full title instead of truncated label
        shape: 'dot',
        size: n.group === 'work' ? 12 : 20,
        font: { color: '#f8fafc', size: 12, face: 'Inter, sans-serif' },
        borderWidth: 2,
        color: {
          border: n.group === 'work' ? '#2d7a74' : '#475569',
          background: n.group === 'work' ? '#4ecdc4' : '#94a3b8',
          highlight: { background: '#ffffff', border: '#4ecdc4' }
        }
      })));
      
      // Update Edges
      edgesRef.current.update(data.edges.map(e => ({
        ...e,
        font: { size: 9, color: '#475569', strokeWidth: 0, align: 'middle' }, 
        color: { color: '#334155', highlight: '#4ecdc4' },
        arrows: { to: { enabled: true, scaleFactor: 0.4 } },
        smooth: { type: 'continuous' }
      })));

      // Gently move the camera to show the new nodes
      if (networkRef.current) {
        networkRef.current.fit({ animation: true });
      }

    } catch (err) {
      console.error("❌ Graph Load failed:", err);
    }
  };

  // INITIAL LOAD: Runs when a user clicks a search result
  useEffect(() => {
    if (!authorId || !containerRef.current) return;

    const initGraph = async () => {
      console.log("🚀 Initializing Graph Instance");
      
      // Clear previous graph data for a fresh start
      nodesRef.current.clear();
      edgesRef.current.clear();
      
      await loadNetworkData(authorId);

      const options = {
        // <-- FIX: Add width constraints to force word-wrapping on long titles
        nodes: {
          widthConstraint: {
            maximum: 200 // Adjust this to make text wider or narrower before wrapping
          }
        },
        physics: {
          enabled: true,
          forceAtlas2Based: {
            gravitationalConstant: -100,
            springLength: 100,
            springConstant: 0.08,
          },
          solver: 'forceAtlas2Based',
          stabilization: { iterations: 150, updateInterval: 25 }
        },
        interaction: {
          hover: true,
          tooltipDelay: 200,
          hideEdgesOnDrag: true,
          selectable: true
        }
      };

      // Create the network instance
      if (networkRef.current) networkRef.current.destroy();
      
      networkRef.current = new Network(
        containerRef.current, 
        { nodes: nodesRef.current, edges: edgesRef.current }, 
        options
      );

      // Listener: Pass clicked node data back to App.jsx Inspector
      networkRef.current.on("selectNode", (params) => {
        const nodeId = params.nodes[0];
        const nodeData = nodesRef.current.get(nodeId);
        console.log("Selected Node Details:", nodeData);
        if (onNodeSelect) onNodeSelect(nodeData);
      });
    };

    initGraph();
  }, [authorId]);

  // EXPANSION LOAD: Runs when "Explore Connections" is clicked in App.jsx
  useEffect(() => {
    if (expandTrigger) {
      loadNetworkData(expandTrigger);
    }
  }, [expandTrigger]);

  return (
    <div 
      ref={containerRef} 
      style={{ height: '100%', minHeight: '600px', width: '100%' }}
      className="bg-[#0a0c10] cursor-grab active:cursor-grabbing" 
    />
  );
};

export default NetworkGraph;