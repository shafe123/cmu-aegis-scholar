import React, { useEffect, useRef, useState } from 'react';
import { DataSet, Network } from 'vis-network/standalone';
import { Loader2 } from 'lucide-react';

const NetworkGraph = ({ authorId }) => {
  const containerRef = useRef(null);
  const networkRef = useRef(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadGraph = async () => {
      setIsLoading(true);
      try {
        const response = await fetch(`http://localhost:8003/viz/author-network/${authorId}`);
        const graphData = await response.json();

        if (!graphData.nodes || graphData.nodes.length === 0) {
          console.warn("No graph data returned for this author.");
          setIsLoading(false);
          return;
        }

        const data = {
          nodes: new DataSet(graphData.nodes.map(n => ({
            ...n,
            color: n.id === authorId ? '#22d3ee' : '#94a3b8',
            font: { color: '#f8fafc', size: 14 }
          }))),
          edges: new DataSet(graphData.edges.map(e => ({
            ...e,
            color: '#334155',
            arrows: { to: { enabled: true, scaleFactor: 0.5 } }
          })))
        };

        const options = {
          autoResize: true,
          nodes: {
            shape: 'dot',
            size: 20,
            shadow: { enabled: true, color: 'rgba(34, 211, 238, 0.2)', size: 10 }
          },
          physics: {
            stabilization: { iterations: 150 },
            forceAtlas2Based: {
              gravitationalConstant: -50,
              centralGravity: 0.01,
              springLength: 100,
              springConstant: 0.08
            },
            solver: 'forceAtlas2Based',
            adaptiveTimestep: true
          },
          interaction: {
            hover: true,
            zoomView: true
          }
        };

        if (networkRef.current) {
          networkRef.current.destroy();
        }

        networkRef.current = new Network(containerRef.current, data, options);
        
      } catch (err) {
        console.error("Failed to load graph:", err);
      } finally {
        setIsLoading(false);
      }
    };

    if (authorId && containerRef.current) {
      loadGraph();
    }

    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
        networkRef.current = null;
      }
    };
  }, [authorId]);

  return (
    <div className="w-full h-full relative min-h-[500px]">
      {isLoading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900/20 z-10">
          <Loader2 className="animate-spin text-aegis-cyan mb-2" size={32} />
          <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">Constructing Neural Map...</span>
        </div>
      )}
      <div 
        ref={containerRef} 
        className="w-full h-full min-h-[600px]" 
        style={{ background: 'transparent' }} 
      />
    </div>
  );
};

export default NetworkGraph;