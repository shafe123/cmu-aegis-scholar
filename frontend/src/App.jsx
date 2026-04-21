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
  const [modalView, setModalView] = useState("profile");
  const [inspectedNode, setInspectedNode] = useState(null);

  // Filter & Sort States
  const [minWorks, setMinWorks] = useState(0);
  const [minCitations, setMinCitations] = useState(0);
  const [sortBy, setSortBy] = useState("relevance");

  const [activeGraphFilters, setActiveGraphFilters] = useState({
    year: 'all',
    organization: 'all'
  });
  const [rawGraphData, setRawGraphData] = useState({ nodes: [], edges: [] });

  // --- ADDED: Dynamic Page Title ---
  useEffect(() => {
    if (selectedAuthor) {
      if (modalView === "profile") {
        document.title = selectedAuthor.name;
      } else if (modalView === "graph") {
        document.title = `${selectedAuthor.name} Network`;
      }
    } else if (hasSearched) {
      document.title = "Author Search";
    } else {
      document.title = "Aegis Scholar";
    }
  }, [selectedAuthor, modalView, hasSearched]);
  // ---------------------------------

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
  };

  const closeModal = () => {
    setSelectedAuthor(null);
    setInspectedNode(null);
    setModalView("profile");
  };

  const resetGraphFilters = () => {
    setActiveGraphFilters({ year: 'all', organization: 'all' });
  };

  const processedResults = results
    .filter(
      (author) =>
        author.works_count >= minWorks && author.citation_count >= minCitations,
    )
    .sort((a, b) => {
      if (sortBy === "works") return b.works_count - a.works_count;
      if (sortBy === "citations") return b.citation_count - a.citation_count;
      return b.relevance_score - a.relevance_score;
    });

  return (
    <div className="flex flex-col min-h-screen bg-[#0a0c10] text-slate-300 font-sans selection:bg-aegis-cyan selection:text-[#0a0c10]">
      {!hasSearched ? (
        <main className="flex-1 flex flex-col items-center justify-center p-6 animate-in fade-in duration-700">
          <img
            src="/favicon.svg"
            alt="Aegis Logo"
            className="w-48 h-48 object-cover rounded-2xl mb-8 shadow-2xl border border-slate-800 hover:scale-110 hover:-translate-y-2 transition-all duration-300 cursor-pointer"
          />

          <form onSubmit={handleSearch} className="w-full max-w-2xl relative">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search researchers, papers, or expertise domains..."
              className="w-full bg-[#161b22] border-2 border-slate-800 rounded-full py-4 pl-14 pr-6 text-lg text-white focus:outline-none focus:border-aegis-cyan transition-all shadow-2xl"
            />
            <Search
              className="absolute left-5 top-4.5 text-slate-500"
              size={24}
            />
            <button
              type="submit"
              className="absolute right-2 top-2 bg-aegis-cyan text-[#0a0c10] font-black px-6 py-3 rounded-full hover:bg-white transition-colors"
            >
              SEARCH
            </button>
          </form>
        </main>
      ) : (
        /* --- RESULTS SCREEN WITH TOP BAR --- */
        <>
          <header className="border-b border-slate-800 bg-[#0d1117] sticky top-0 z-10 animate-in slide-in-from-top duration-300">
            <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
              <div
                className="flex items-center gap-2 cursor-pointer group"
                onClick={goHome}
              >
                <ShieldCheck
                  className="text-aegis-cyan group-hover:scale-110 transition-transform"
                  size={24}
                />
                <h1 className="text-white font-bold tracking-tighter text-lg uppercase group-hover:text-aegis-cyan transition-colors hidden md:block">
                  AEGIS Scholar
                </h1>
              </div>

              <form
                onSubmit={handleSearch}
                className="flex-1 max-w-xl mx-4 md:mx-8 relative"
              >
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search researchers, papers, or expertise domains..."
                  className="w-full bg-[#161b22] border border-slate-700 rounded-full py-2 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-aegis-cyan transition-all"
                />
                <Search
                  className="absolute left-3 top-2.5 text-slate-500"
                  size={16}
                />
                <button
                  type="submit"
                  className="absolute right-2 top-1.5 bg-aegis-cyan text-[#0a0c10] text-[10px] font-black px-3 py-1 rounded-full hover:bg-white transition-colors"
                >
                  SEARCH
                </button>
              </form>
              <div className="flex items-center gap-4 text-slate-500">
                <Settings
                  size={20}
                  className="cursor-pointer hover:text-white transition-colors"
                />
              </div>
            </div>
          </header>

          <main className="flex-1 max-w-4xl w-full mx-auto px-6 py-12">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-20 gap-4">
                <Loader2 className="text-aegis-cyan animate-spin" size={40} />
                <p className="text-xs font-mono uppercase tracking-widest text-slate-500">
                  Querying Database...
                </p>
              </div>
            ) : (
              <>
                {results.length > 0 && (
                  <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-800">
                      <h3 className="text-white font-bold text-sm tracking-widest uppercase flex items-center gap-2">
                        <Database size={16} className="text-aegis-cyan" />
                        Search Results ({processedResults.length})
                      </h3>
                    </div>

                    <div className="flex flex-wrap items-center gap-4 mb-6 p-4 bg-[#161b22] border border-slate-800 rounded-xl shadow-lg">
                      <div className="flex items-center gap-2 text-slate-400">
                        <Filter size={16} />
                        <span className="text-xs font-bold uppercase tracking-widest">
                          Filters:
                        </span>
                      </div>

                      <select
                        value={minWorks}
                        onChange={(e) => setMinWorks(Number(e.target.value))}
                        className="bg-[#0d1117] border border-slate-700 text-sm text-slate-300 rounded px-3 py-1.5 focus:border-aegis-cyan focus:outline-none cursor-pointer"
                      >
                        <option value="0">Any Works</option>
                        <option value="5">5+ Works</option>
                        <option value="20">20+ Works</option>
                        <option value="50">50+ Works</option>
                      </select>

                      <select
                        value={minCitations}
                        onChange={(e) =>
                          setMinCitations(Number(e.target.value))
                        }
                        className="bg-[#0d1117] border border-slate-700 text-sm text-slate-300 rounded px-3 py-1.5 focus:border-aegis-cyan focus:outline-none cursor-pointer"
                      >
                        <option value="0">Any Citations</option>
                        <option value="50">50+ Citations</option>
                        <option value="500">500+ Citations</option>
                        <option value="1000">1000+ Citations</option>
                      </select>

                      <div className="ml-auto flex items-center gap-3">
                        <span className="text-xs font-bold uppercase tracking-widest text-slate-400">
                          Sort:
                        </span>
                        <select
                          value={sortBy}
                          onChange={(e) => setSortBy(e.target.value)}
                          className="bg-[#0d1117] border border-slate-700 text-sm text-slate-300 rounded px-3 py-1.5 focus:border-aegis-cyan focus:outline-none cursor-pointer"
                        >
                          <option value="relevance">Highest Match</option>
                          <option value="works">Most Works</option>
                          <option value="citations">Most Citations</option>
                        </select>
                      </div>
                    </div>

                    <div className="space-y-1">
                      {processedResults.length > 0 ? (
                        processedResults.map((author) => (
                          <ResearcherRow
                            key={author.id}
                            author={author}
                            onSelect={setSelectedAuthor}
                          />
                        ))
                      ) : (
                        <div className="text-center py-12 text-slate-500 italic">
                          No results match your current filters.
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
          </main>
        </>
      )}

      {/* --- NEW MINIMAL FOOTER --- */}
      <footer className="py-6 border-t border-slate-900 mt-auto bg-[#0d1117]">
        <div className="max-w-7xl mx-auto px-6 flex justify-between items-center text-[10px] uppercase tracking-[0.2em] font-bold text-slate-600">
          <span>© {new Date().getFullYear()} AEGIS Network Systems</span>
          <div className="flex gap-6">
            <span className="hover:text-aegis-cyan cursor-pointer transition-colors">Documentation</span>
            <span className="hover:text-aegis-cyan cursor-pointer transition-colors">System Status: Nominal</span>
          </div>
        </div>
      </footer>

      {/* Profile Modal */}
      {selectedAuthor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-[#0a0c10]/80 backdrop-blur-sm">
          <div className="bg-[#0d1117] w-full max-w-6xl h-full max-h-[800px] rounded-2xl border border-slate-800 shadow-2xl overflow-hidden flex flex-col">
            <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-[#161b22]">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-aegis-cyan/10 rounded-lg text-aegis-cyan">
                </div>
                <div>
                  <h2 className="text-white font-black text-xl tracking-tighter uppercase flex items-center gap-3">
                    <ShieldCheck className="text-aegis-cyan" size={24} />
                    <span>
                      {selectedAuthor.name}
                      <span className="block text-[10px] text-slate-500 font-mono mt-0.5 tracking-normal normal-case opacity-70">
                        System ID: {selectedAuthor.id}
                      </span>
                    </span>
                  </h2>
                </div>
              </div>
              <button
                onClick={closeModal}
                data-testid="close-modal"
                className="text-slate-500 hover:text-white bg-slate-800/50 p-2 rounded-full transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            <div className="flex bg-[#0d1117] border-b border-slate-800 px-6">
              <button
                onClick={() => setModalView("profile")}
                className={`px-6 py-4 text-xs font-bold uppercase tracking-widest border-b-2 transition-all ${modalView === "profile" ? "border-aegis-cyan text-aegis-cyan bg-aegis-cyan/5" : "border-transparent text-slate-500 hover:text-white"}`}
              >
                Overview
              </button>
              <button
                onClick={() => setModalView("graph")}
                className={`px-6 py-4 text-xs font-bold uppercase tracking-widest border-b-2 transition-all ${modalView === "graph" ? "border-aegis-cyan text-aegis-cyan bg-aegis-cyan/5" : "border-transparent text-slate-500 hover:text-white"}`}
              >
                Explore Connections
              </button>
            </div>

            <div className="flex-1 flex overflow-hidden">
              {modalView === "profile" ? (
                <div className="flex-1 p-12 overflow-y-auto">
                  <div className="max-w-2xl">
                    <h1 className="text-5xl font-black text-white mb-4 tracking-tighter">
                      {selectedAuthor.name}
                    </h1>
                    <p className="text-aegis-cyan font-mono text-sm mb-8">
                      {selectedAuthor.specialization}
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex-1 relative">
                    {/* --- ADDED: Filter UI Bar --- */}
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

                      <button
                        onClick={resetGraphFilters}
                        className="text-[10px] uppercase font-bold text-slate-500 hover:text-white px-2"
                      >
                        Reset
                      </button>
                    </div>
                    <NetworkGraph
                      authorId={selectedAuthor.id}
                      selectedAuthorName={selectedAuthor.name}
                      onNodeSelect={setInspectedNode}
                      // Added Props
                      activeFilters={activeGraphFilters}
                      onDataLoad={setRawGraphData}
                    />
                  </div>

                  {inspectedNode && (
                    <div className="w-80 bg-[#1a1d21] border-l border-slate-800 p-6 overflow-y-auto animate-in slide-in-from-right duration-300">
                      <div className="flex items-center justify-between mb-6">
                        <h3 className="text-white font-bold flex items-center gap-2">
                          <Activity size={18} className="text-aegis-cyan" />
                          Inspector
                        </h3>
                        <button
                          onClick={() => setInspectedNode(null)}
                          data-testid="close-inspector"
                          className="text-slate-500 hover:text-white p-1"
                        >
                          <X size={16} />
                        </button>
                      </div>

                      <div className="space-y-6">
                        <div className="p-4 bg-slate-800/30 rounded-xl border border-slate-800">
                          <p className="text-[10px] text-slate-500 uppercase font-black mb-1 tracking-widest">
                            Selected Entity
                          </p>
                          <p className="text-white font-bold text-sm leading-tight">
                            {inspectedNode.full_title || inspectedNode.label}
                          </p>
                          <span className="inline-block mt-2 text-[10px] px-2 py-0.5 rounded bg-aegis-cyan/10 text-aegis-cyan border border-aegis-cyan/20 font-mono uppercase">
                            {inspectedNode.group}
                          </span>
                        </div>

                        {inspectedNode.group === "work" ? (
                          <>
                            <div className="flex items-center gap-4 text-sm text-slate-300">
                              <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-aegis-cyan">
                                <Calendar size={20} />
                              </div>
                              <div>
                                <p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">
                                  Publication Year
                                </p>
                                <p className="font-mono text-white text-lg">
                                  {inspectedNode.year || "N/A"}
                                </p>
                              </div>
                            </div>
                            <div className="pt-4 border-t border-slate-800">
                              <details className="group" open>
                                <summary className="text-[10px] text-slate-500 uppercase font-bold tracking-widest cursor-pointer list-none flex items-center justify-between">
                                  Abstract Preview{" "}
                                  <Share2
                                    size={12}
                                    className="group-open:rotate-180 transition-transform"
                                  />
                                </summary>
                                <p className="mt-3 text-[13px] leading-relaxed text-slate-400 italic font-serif">
                                  "
                                  {inspectedNode.abstract ||
                                    "No abstract available for this record."}
                                  "
                                </p>
                              </details>
                            </div>
                          </>
                        ) : inspectedNode.group === "organization" ? (
                          /* --- NEW: Organization Specific View --- */
                          <div className="flex items-center gap-4 text-sm text-slate-300">
                            <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-aegis-cyan">
                              <Mail size={20} />
                            </div>
                            <div>
                              <p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">
                                Contact
                              </p>
                              <p className="font-mono text-white text-[13px]">
                                {`contact@${inspectedNode.label
                                  .toLowerCase()
                                  .replace(/[^a-z0-9]/g, "")}.org`}
                              </p>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="flex items-center gap-4 text-sm text-slate-300">
                              <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-aegis-cyan">
                                <Mail size={20} />
                              </div>
                              <div>
                                <p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">
                                  Contact
                                </p>
                                <p className="font-mono text-white text-[13px]">
                                  {inspectedNode.email || "N/A"}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-4 text-sm text-slate-300">
                              <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-aegis-cyan">
                                <Database size={20} />
                              </div>
                              <div>
                                <p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">
                                  Total Works
                                </p>
                                <p className="font-mono text-white text-lg">
                                  {inspectedNode.works_count || 0}
                                </p>
                              </div>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
