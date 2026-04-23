import React, { useState, useEffect } from "react";
import {
  Search,
  Settings,
  Loader2,
  X,
  ShieldCheck,
  Database,
  Activity,
  Calendar,
  Share2,
  Mail,
  Filter,
} from "lucide-react";
import { searchAuthors } from "./services/api";
import NetworkGraph from "./components/NetworkGraph";

const ResearcherRow = ({ author, onSelect }) => {
  const rawSpecialization =
    author?.specialization || "Unknown Domain | No Stats Available";
  const parts = rawSpecialization.split(" | ");
  const domain = parts[0] || "Unknown Domain";
  const stats = parts[1] || "";

  return (
    <div
      className="bg-[#1a1d21]/50 border-b border-slate-800 p-4 flex items-center gap-6 hover:bg-slate-800/50 transition-colors group cursor-pointer"
      onClick={() => onSelect(author)}
    >
      <div className="flex-1">
        <h3 className="text-aegis-cyan font-bold text-lg group-hover:underline">
          {author?.name || "Unknown Name"}
        </h3>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-aegis-cyan/70 text-[10px] font-black uppercase tracking-wider bg-aegis-cyan/5 px-2 py-0.5 rounded border border-aegis-cyan/10">
            {domain}
          </span>
          <span className="text-slate-500 text-xs font-mono">{stats}</span>
        </div>
      </div>
      <div className="flex flex-col items-end w-24 pr-4">
        <div className="text-xl font-mono text-aegis-cyan">
          {(author?.relevance_score || 0).toFixed(3)}
        </div>
        <div className="text-[9px] text-slate-500 font-bold tracking-widest uppercase">
          Match Index
        </div>
      </div>
    </div>
  );
};

export default function App() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const [selectedAuthor, setSelectedAuthor] = useState(null);
  const [inspectedNode, setInspectedNode] = useState(null);

  const [minWorks, setMinWorks] = useState(0);
  const [minCitations, setMinCitations] = useState(0);
  const [sortBy, setSortBy] = useState("relevance");

  const [activeGraphFilters, setActiveGraphFilters] = useState({
    year: 'all',
    organization: 'all'
  });
  const [rawGraphData, setRawGraphData] = useState({ nodes: [], edges: [] });

  useEffect(() => {
    if (selectedAuthor) {
      document.title = `${selectedAuthor.name} Network`;
    } else if (hasSearched) {
      document.title = "Author Search";
    } else {
      document.title = "Aegis Scholar";
    }
  }, [selectedAuthor, hasSearched]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const authorIdFromUrl = params.get('author');

    if (authorIdFromUrl && !selectedAuthor) {
      setSelectedAuthor({
        id: authorIdFromUrl,
        name: "Loading Subject...",
        specialization: "Identity Retrieval in Progress..."
      });
    }
  }, [selectedAuthor]);

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!query) return;
    setHasSearched(true);
    setLoading(true);
    try {
      const data = await searchAuthors(query);
      setResults(data);
    } catch (error) {
      console.error("Search error:", error);
    } finally {
      setLoading(false);
    }
  };

  const goHome = () => {
    setHasSearched(false);
    setQuery("");
    setResults([]);
    setMinWorks(0);
    setMinCitations(0);
    setSortBy("relevance");
    setSelectedAuthor(null);
    window.history.pushState({}, '', window.location.pathname);
  };

  const closeModal = () => {
    setSelectedAuthor(null);
    setInspectedNode(null);
    window.history.pushState({}, '', window.location.pathname);
  };

  const resetGraphFilters = () => {
    setActiveGraphFilters({ year: 'all', organization: 'all' });
  };

  const processedResults = results
    .filter((author) => author.works_count >= minWorks && author.citation_count >= minCitations)
    .sort((a, b) => {
      if (sortBy === "works") return b.works_count - a.works_count;
      if (sortBy === "citations") return b.citation_count - a.citation_count;
      return b.relevance_score - a.relevance_score;
    });

  const handleSelectAuthor = (author) => {
    setSelectedAuthor(author);
    const newUrl = `${window.location.protocol}//${window.location.host}${window.location.pathname}?author=${author.id}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
  };

  return (
    <div className="flex flex-col min-h-screen bg-[#0a0c10] text-slate-300 font-sans selection:bg-aegis-cyan selection:text-[#0a0c10]">
      {!hasSearched ? (
        <main className="flex-1 flex flex-col items-center justify-center p-6 animate-in fade-in duration-700">
          <img src="/favicon.svg" alt="Aegis Logo" className="w-48 h-48 object-cover rounded-2xl mb-8 shadow-2xl border border-slate-800 transition-all duration-500 cursor-pointer hover:-translate-y-2 hover:scale-105 hover:shadow-aegis-cyan/20 hover:border-aegis-cyan/50" />
          <form onSubmit={handleSearch} className="w-full max-w-2xl relative">
            <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search..." className="w-full bg-[#161b22] border-2 border-slate-800 rounded-full py-4 pl-14 pr-6 text-lg text-white focus:outline-none focus:border-aegis-cyan shadow-2xl" />
            <Search className="absolute left-5 top-4.5 text-slate-500" size={24} />
            <button type="submit" className="absolute right-2 top-2 bg-aegis-cyan text-[#0a0c10] font-black px-6 py-3 rounded-full hover:bg-white">SEARCH</button>
          </form>
        </main>
      ) : (
        <>
          <header className="border-b border-slate-800 bg-[#0d1117] sticky top-0 z-10">
            <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
              <div className="flex items-center gap-2 cursor-pointer group" onClick={goHome}>
                <ShieldCheck className="text-aegis-cyan group-hover:scale-110" size={24} />
                <h1 className="text-white font-bold text-lg uppercase group-hover:text-aegis-cyan">AEGIS Scholar</h1>
              </div>
              <form onSubmit={handleSearch} className="flex-1 max-w-xl mx-8 relative">
                <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search..." className="w-full bg-[#161b22] border border-slate-700 rounded-full py-2 pl-10 pr-4 text-sm text-white focus:outline-none" />
                <Search className="absolute left-3 top-2.5 text-slate-500" size={16} />
              </form>
            </div>
          </header>

          <main className="flex-1 max-w-4xl w-full mx-auto px-6 py-12">
            {loading ? (
              <div className="flex flex-col items-center py-20 gap-4">
                <Loader2 className="text-aegis-cyan animate-spin" size={40} />
                <p className="text-xs font-mono uppercase text-slate-500 tracking-widest">Querying Database...</p>
              </div>
            ) : (
              <div className="space-y-1">
                {processedResults.map((author) => (
                  <ResearcherRow key={author.id} author={author} onSelect={handleSelectAuthor} />
                ))}
              </div>
            )}
          </main>
        </>
      )}

      {/* --- NEW MINIMAL FOOTER --- */}
      <footer className="py-6 border-t border-slate-900 mt-auto bg-[#0d1117]">
        <div className="max-w-7xl mx-auto px-6 flex justify-between items-center text-[10px] uppercase tracking-[0.2em] font-bold text-slate-600">
          <span>© {new Date().getFullYear()} AEGIS Network Systems</span>
          <div className="flex gap-6">
            <a
              href="https://github.com/shafe123/cmu-aegis-scholar"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-aegis-cyan cursor-pointer transition-colors"
            >
              Documentation
            </a>
            <span className="hover:text-aegis-cyan cursor-pointer transition-colors">System Status: Nominal</span>
          </div>
        </div>
      </footer>

      {selectedAuthor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-[#0a0c10]/80 backdrop-blur-sm">
          <div className="bg-[#0d1117] w-full max-w-6xl h-full max-h-[800px] rounded-2xl border border-slate-800 shadow-2xl overflow-hidden flex flex-col">
            <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-[#161b22]">
              <h2 className="text-white font-black text-xl tracking-tighter uppercase flex items-center gap-3">
                <ShieldCheck className="text-aegis-cyan" size={24} />
                <span>
                  {selectedAuthor.name}
                  <span className="block text-[10px] text-slate-500 font-mono mt-0.5 opacity-70">System ID: {selectedAuthor.id}</span>
                </span>
              </h2>
              <button onClick={closeModal} className="text-slate-500 hover:text-white bg-slate-800/50 p-2 rounded-full"><X size={20} /></button>
            </div>

            <div className="flex-1 flex overflow-hidden">
              <div className="flex-1 relative">
                <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 flex gap-2 bg-[#161b22]/90 backdrop-blur-md p-2 rounded-lg border border-slate-700 shadow-2xl">
                  <select
                    value={activeGraphFilters.year}
                    onChange={(e) => setActiveGraphFilters(f => ({ ...f, year: e.target.value }))}
                    className="bg-slate-800 text-xs text-white rounded border border-slate-600 px-2 py-1 outline-none focus:border-aegis-cyan"
                  >
                    <option value="all">All Years</option>
                    {[...new Set(rawGraphData.nodes.filter(n => n.group === 'work').map(n => n.year))].sort().reverse().map(y => (
                      <option key={y} value={y}>{y}</option>
                    ))}
                  </select>

                  <select
                    value={activeGraphFilters.organization}
                    onChange={(e) => setActiveGraphFilters(f => ({ ...f, organization: e.target.value }))}
                    className="bg-slate-800 text-xs text-white rounded border border-slate-600 px-2 py-1 outline-none focus:border-aegis-cyan"
                  >
                    <option value="all">All Orgs</option>
                    {[...new Set(rawGraphData.nodes.filter(n => n.group === 'organization').map(n => n.label))].sort().map(o => (
                      <option key={o} value={o}>{o}</option>
                    ))}
                  </select>
                  <button onClick={resetGraphFilters} className="text-[10px] uppercase font-bold text-slate-500 hover:text-white px-2">Reset</button>
                </div>
                <NetworkGraph
                  authorId={selectedAuthor.id}
                  selectedAuthorName={selectedAuthor.name}
                  onNodeSelect={setInspectedNode}
                  activeFilters={activeGraphFilters}
                  onDataLoad={setRawGraphData}
                />
              </div>

              {inspectedNode && (
                <div className="w-80 bg-[#1a1d21] border-l border-slate-800 p-6 overflow-y-auto animate-in slide-in-from-right duration-300">
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="text-white font-bold flex items-center gap-2"><Activity size={18} className="text-aegis-cyan" />Inspector</h3>
                    <button onClick={() => setInspectedNode(null)} className="text-slate-500 hover:text-white p-1"><X size={16} /></button>
                  </div>

                  <div className="space-y-6">
                    <div className="p-4 bg-slate-800/30 rounded-xl border border-slate-800">
                      <p className="text-[10px] text-slate-500 uppercase font-black mb-1 tracking-widest">Selected Entity</p>
                      <p className="text-white font-bold text-sm leading-tight">{inspectedNode.full_title || inspectedNode.label}</p>
                      <span className="inline-block mt-2 text-[10px] px-2 py-0.5 rounded bg-aegis-cyan/10 text-aegis-cyan border border-aegis-cyan/20 font-mono uppercase">{inspectedNode.group}</span>
                    </div>

                    {inspectedNode.group === "work" ? (
                      <>
                        <div className="flex items-center gap-4 text-sm text-slate-300">
                          <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-aegis-cyan">
                            <Calendar size={20} />
                          </div>
                          <div>
                            <p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Publication Year</p>
                            <p className="font-mono text-white text-lg">{inspectedNode.year || "N/A"}</p>
                          </div>
                        </div>
                        <div className="pt-4 border-t border-slate-800">
                          <details className="group" open>
                            <summary className="text-[10px] text-slate-500 uppercase font-bold tracking-widest cursor-pointer list-none flex items-center justify-between">
                              Abstract Preview <Share2 size={12} className="group-open:rotate-180 transition-transform" />
                            </summary>
                            <p className="mt-3 text-[13px] leading-relaxed text-slate-400 italic font-serif">
                              "{inspectedNode.abstract || "No abstract available for this record."}"
                            </p>
                          </details>
                        </div>
                      </>
                    ) : inspectedNode.group === "organization" ? (
                      <>
                        <div className="flex items-center gap-4 text-sm text-slate-300">
                          {/* 1. Added shrink-0 to prevent the icon from squishing */}
                          <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-aegis-cyan shrink-0">
                            <Mail size={20} />
                          </div>
                          {/* 2. Added min-w-0 and flex-1 to allow the container to contain the text */}
                          <div className="min-w-0 flex-1">
                            <p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Contact</p>
                            {/* 3. Added break-all to force the long email to wrap */}
                            <p className="font-mono text-white text-[13px] break-all">
                              {`contact@${(inspectedNode.label || "").toLowerCase().replace(/[^a-z0-9]/g, "")}.org`}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-4 text-sm text-slate-300 mt-4">
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="flex items-center gap-4 text-sm text-slate-300">
                          <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-aegis-cyan">
                            <Mail size={20} />
                          </div>
                          <div>
                            <p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Contact</p>
                            <p className="font-mono text-white text-[13px]">{inspectedNode.email || "N/A"}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-4 text-sm text-slate-300 mt-4">
                          <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-aegis-cyan">
                            <Database size={20} />
                          </div>
                          <div>
                            <p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Total Works</p>
                            <p className="font-mono text-white text-lg">{inspectedNode.works_count || 0}</p>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}