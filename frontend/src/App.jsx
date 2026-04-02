import React, { useState } from 'react';
import { Search, Settings, Loader2, X, ShieldCheck, Database, Activity, Target, Calendar, Share2, User, Mail } from 'lucide-react';
import { searchAuthors } from './services/api';
import NetworkGraph from './components/NetworkGraph';

const ResearcherRow = ({ author, onSelect }) => {
  const rawSpecialization = author?.specialization || "Unknown Domain | No Stats Available";
  const parts = rawSpecialization.split(' | ');
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
          {/* USE THE REAL SCORE FROM THE BACKEND */}
          {author.relevance_score ? author.relevance_score.toFixed(3) : '0.000'}
        </div>
        <div className="text-[8px] font-black text-slate-600 uppercase tracking-widest">SIMILARITY</div>
      </div>
    </div>
  );
};

export default function App() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  
  // Modal & Graph State
  const [selectedAuthor, setSelectedAuthor] = useState(null);
  const [modalView, setModalView] = useState('profile'); // 'profile' | 'graph'
  const [inspectedNode, setInspectedNode] = useState(null);

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!query) return;
    
    setLoading(true);
    setHasSearched(true);
    setResults([]); 
    
    try {
      const data = await searchAuthors(query, 'Authors'); // Hardcoded to Authors now
      if (Array.isArray(data)) {
        setResults(data);
      } else {
        setResults([]);
      }
    } catch (error) {
      console.error("Search failed:", error);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const openAuthorModal = (author) => {
    setSelectedAuthor(author);
    setModalView('profile'); // Always start on the profile tab
    setInspectedNode(null);
  };

  const closeModal = () => {
    setSelectedAuthor(null);
    setInspectedNode(null);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#0a0c10] text-white font-sans">
      <header className="p-4 flex justify-between items-center border-b border-slate-800 bg-[#0a0c10]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <ShieldCheck className="text-aegis-cyan" size={24} />
          <span className="font-bold tracking-[0.2em] text-[12px] uppercase text-slate-200">Scholar Search</span>
        </div>
        <div className="flex items-center gap-4 text-slate-500">
          <Settings size={18}/><div className="w-8 h-8 bg-slate-800 rounded-full"></div>
        </div>
      </header>

      <main className={`flex-1 max-w-5xl mx-auto w-full px-6 transition-all duration-700 ${hasSearched ? 'pt-8' : 'pt-32'}`}>
        {!hasSearched && (
          <div className="text-center mb-10">
            <img 
              src="/favicon.svg" 
              alt="Aegis Scholar Logo" 
              className="mx-auto mb-8 w-64 bg-white p-6 rounded-2xl shadow-[0_10px_25px_rgba(0,0,0,0.5)] transition-transform duration-200 ease-in-out hover:-translate-y-1.5" 
            />
            
            <p className="text-slate-500 mb-10 text-lg font-light tracking-wide">
              Semantic Researcher & Network Discovery
            </p>
          </div>
        )}
        
        <form onSubmit={handleSearch} className="relative max-w-2xl mx-auto mb-10">
          <input 
            type="text" 
            className="w-full bg-white text-slate-900 py-4 pl-14 pr-32 rounded-full text-lg shadow-2xl outline-none focus:ring-4 focus:ring-aegis-cyan/20 font-medium transition-all"
            placeholder="Search the Aegis database..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Search className="absolute left-5 top-4 text-slate-400" size={22} />
          <button type="submit" className="absolute right-2 top-2 bg-slate-900 text-aegis-cyan hover:bg-slate-800 px-8 py-2.5 rounded-full font-bold">
            {loading ? <Loader2 className="animate-spin" size={20}/> : 'SEARCH'}
          </button>
        </form>

        {/* RESULTS WRAPPER */}
        {results && results.length > 0 && (
          <div className="bg-[#1a1d21] rounded-2xl border border-slate-800 overflow-hidden shadow-2xl relative z-10">
            {results.map((author, idx) => (
              <ResearcherRow key={author?.id || idx} author={author} onSelect={openAuthorModal} />
            ))}
          </div>
        )}
      </main>

      <footer className="border-t border-slate-800 py-4 text-center text-slate-500 text-sm mt-8">
        <div className="max-w-5xl mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-4">
          <p>© {new Date().getFullYear()} Aegis Scholar. Capstone Project.</p>
          
          <div className="flex gap-6">
            <a href="#" className="hover:text-aegis-cyan transition-colors">Documentation</a>
            <a href="#" className="hover:text-aegis-cyan transition-colors">GitHub Repository</a>
            <a href="#" className="hover:text-aegis-cyan transition-colors">About</a>
          </div>
        </div>
      </footer>
      {/* ------------------------------- */}

      {/* DUAL-VIEW MODAL (Profile OR Graph) */}
      {selectedAuthor && (
        <div className="fixed inset-0 bg-black/95 backdrop-blur-xl z-[100] flex items-center justify-center p-6">
          <div className="bg-[#0f1115] border border-slate-800 w-full max-w-7xl h-[90vh] rounded-3xl overflow-hidden flex flex-col relative">
            
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-800 flex justify-between items-center bg-[#0f1115]">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <User className="text-aegis-cyan" size={18}/> {selectedAuthor.name}
                </h2>
                <p className="text-[10px] text-slate-500 font-mono tracking-tighter uppercase">
                  {modalView === 'profile' ? 'Subject Profile' : 'Network Explorer'} // {selectedAuthor.id}
                </p>
              </div>
              
              <div className="flex items-center gap-4">
                {/* Back to profile button */}
                {modalView === 'graph' && (
                   <button 
                     onClick={() => setModalView('profile')} 
                     className="text-xs font-bold text-aegis-cyan uppercase tracking-wider hover:text-white transition-colors"
                   >
                     ← Back to Profile
                   </button>
                )}
                <button onClick={closeModal} className="text-slate-500 hover:text-white bg-slate-800/50 p-2 rounded-full"><X size={20} /></button>
              </div>
            </div>
            
            {/* Modal Body: Conditionally renders Profile or Graph */}
            <div className="flex-1 relative flex bg-[#0a0c10]">
               
               {modalView === 'profile' ? (
                 
                 // --- PROFILE VIEW ---
                 <div className="flex-1 flex flex-col items-center justify-center p-10 relative overflow-hidden">
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-aegis-cyan/5 rounded-full blur-[100px] pointer-events-none" />
                    
                    <div className="w-24 h-24 bg-slate-800 border border-slate-700 rounded-2xl flex items-center justify-center mb-6 shadow-2xl">
                      <User size={40} className="text-aegis-cyan" />
                    </div>
                    
                    <h2 className="text-5xl font-black text-white mb-4 tracking-tight">{selectedAuthor.name}</h2>
                    
                    <div className="flex gap-4 mb-12">
                      <div className="bg-[#1a1d21] border border-slate-800 px-6 py-3 rounded-xl flex items-center gap-3">
                         <Database className="text-slate-400" size={18} />
                         <span className="text-slate-300 font-mono text-sm">{selectedAuthor.specialization.split(' | ')[1] || "No Data"}</span>
                      </div>
                      <div className="bg-[#1a1d21] border border-slate-800 px-6 py-3 rounded-xl flex items-center gap-3">
                         <Mail className="text-slate-400" size={18} />
                         <span className="text-slate-300 font-mono text-sm">
                           {selectedAuthor.name ? `${selectedAuthor.name.split(' ')[0].toLowerCase()}.${selectedAuthor.name.split(' ').pop().toLowerCase()}@university.edu` : 'contact@university.edu'}
                         </span>
                      </div>
                    </div>

                    <button 
                      onClick={() => setModalView('graph')}
                      className="group relative px-8 py-4 bg-aegis-cyan text-black rounded-full font-black text-sm uppercase tracking-widest overflow-hidden shadow-[0_0_40px_rgba(78,205,196,0.2)] hover:shadow-[0_0_60px_rgba(78,205,196,0.4)] transition-all active:scale-95 flex items-center gap-3"
                    >
                      <Share2 size={20} />
                      Explore Connections
                      <div className="absolute inset-0 h-full w-full bg-white/20 scale-x-0 group-hover:scale-x-100 origin-left transition-transform duration-300" />
                    </button>
                 </div>

               ) : (

                 // --- GRAPH VIEW ---
                 <>
                   <div className="absolute inset-0 z-0">
                     <NetworkGraph 
                        authorId={selectedAuthor.id} 
                        onNodeSelect={setInspectedNode} 
                        // expandTrigger removed since we deleted the button
                     />
                   </div>
                   
                   {/* NODE INSPECTOR SIDEBAR */}
                   {inspectedNode && (
                     <div className="w-80 border-l border-slate-800 bg-[#0a0c10]/90 p-6 backdrop-blur-md z-10 overflow-y-auto">
                        <div className="flex justify-between items-center mb-6">
                          <span className="bg-aegis-cyan/10 text-aegis-cyan text-[10px] font-black px-2 py-1 rounded border border-aegis-cyan/20 uppercase tracking-widest">
                            {inspectedNode.group} Details
                          </span>
                          <button onClick={() => setInspectedNode(null)} className="text-slate-600 hover:text-white"><X size={16}/></button>
                        </div>

                        <h3 className="text-white font-bold text-xl mb-6 leading-tight">
                          {inspectedNode.full_title || inspectedNode.label}
                        </h3>

                        <div className="space-y-6 border-t border-slate-800 pt-6">
                          {inspectedNode.group === 'work' ? (
                            <>
                              <div className="flex items-center gap-4 text-sm text-slate-300">
                                <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-aegis-cyan"><Calendar size={20}/></div>
                                <div><p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Year</p><p className="font-mono text-white text-lg">{inspectedNode.details?.year || 'N/A'}</p></div>
                              </div>
                              <div className="w-full text-sm text-slate-300 bg-slate-800/50 p-3 rounded-xl border border-slate-700">
                                <p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest mb-2">Abstract</p>
                                <details className="group cursor-pointer">
                                  <summary className="font-medium text-aegis-cyan hover:text-white transition-colors outline-none list-none text-xs">
                                    <span className="group-open:hidden">▶ Read Abstract...</span>
                                    <span className="hidden group-open:inline">▼ Hide Abstract</span>
                                  </summary>
                                  <p className="mt-3 text-xs leading-relaxed max-h-48 overflow-y-auto pr-2 text-slate-400">
                                    {inspectedNode.details?.abstract}
                                  </p>
                                </details>
                              </div>
                            </>
                          ) : (
                            <>
                              <div className="flex items-center gap-4 text-sm text-slate-300">
                                <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-aegis-cyan"><Mail size={20}/></div>
                                <div><p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Contact</p><p className="font-mono text-white text-[13px]">{inspectedNode.details?.email || 'N/A'}</p></div>
                              </div>
                              <div className="flex items-center gap-4 text-sm text-slate-300">
                                <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-aegis-cyan"><Database size={20}/></div>
                                <div><p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Total Works</p><p className="font-mono text-white text-lg">{inspectedNode.details?.works || 0}</p></div>
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