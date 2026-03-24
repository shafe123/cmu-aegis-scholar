import React, { useState } from 'react';
import { Search, Users, Settings, Loader2, X, ShieldCheck, Database, Activity, BarChart3 } from 'lucide-react';
import { searchAuthors } from './services/api';
import NetworkGraph from './components/NetworkGraph';

const ResearcherRow = ({ author, onSelect }) => {
  const deptStyles = {
    USA: 'bg-black text-yellow-500 border-yellow-500/50',
    USN: 'bg-[#003147] text-white border-cyan-500/30',
    USAF: 'bg-blue-900 text-white border-blue-400/30',
    USMC: 'bg-[#544d2e] text-red-700 border-red-900/50'
  };

  return (
    <div className="bg-[#2a2f35]/50 border-b border-slate-800 p-4 flex items-center gap-6 hover:bg-slate-800/50 transition-colors group">
      <div className={`w-12 h-12 rounded-full border flex items-center justify-center font-bold text-[10px] shadow-lg ${deptStyles[author.dept] || 'bg-slate-700 text-slate-300'}`}>
        {author.dept || 'CIV'}
      </div>

      <div className="flex-1">
        <h3 
          className="text-aegis-cyan font-bold text-lg group-hover:underline cursor-pointer"
          onClick={() => onSelect(author)}
        >
          {author.name}
        </h3>
        <p className="text-slate-400 text-sm truncate max-w-md italic">
          {author.specialization || "Technical Lead • Cyber Systems"}
        </p>
      </div>

      <div className="text-slate-500 text-[10px] font-mono w-32 text-center uppercase tracking-tighter">
        {author.date || 'MAR 2026'}
      </div>

      {/* Mini Visual Metric */}
      <div className="w-24 flex items-end gap-1 h-8 px-2 opacity-60 group-hover:opacity-100 transition-opacity">
        {[30, 60, 45, 80].map((h, i) => (
          <div key={i} className={`bg-slate-600 w-1.5 rounded-t-sm group-hover:bg-aegis-cyan`} style={{ height: `${h}%` }}></div>
        ))}
      </div>

      <div className="w-20 text-right font-mono text-xl text-aegis-cyan pr-4 drop-shadow-[0_0_8px_rgba(34,211,238,0.3)]">
        {author.h_index || '0'}
      </div>
    </div>
  );
};

export default function App() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [activeTab, setActiveTab] = useState('Authors');
  const [selectedAuthor, setSelectedAuthor] = useState(null);

  const tabs = ['Authors', 'Works', 'Orgs', 'Year'];

  const onSearch = async (e) => {
    e.preventDefault();
    if (!query) return;
    setLoading(true);
    setHasSearched(true);
    try {
      const data = await searchAuthors(query);
      setResults(data);
    } catch (err) {
      console.error("Search failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-aegis-dark text-white font-sans selection:bg-aegis-cyan selection:text-navy-900">
      
      {/* 1. NAV BAR */}
      <header className="p-4 flex justify-between items-center border-b border-slate-800 bg-aegis-dark/80 backdrop-blur-md sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-aegis-cyan rounded flex items-center justify-center shadow-cyan-glow">
            <ShieldCheck className="text-aegis-dark" size={20} />
          </div>
          <span className="font-bold tracking-[0.3em] text-[11px] uppercase text-slate-200">Aegis Scholar</span>
        </div>
        <div className="flex items-center gap-4">
           <button className="text-slate-500 hover:text-aegis-cyan transition-colors"><Settings size={18}/></button>
           <div className="w-8 h-8 bg-gradient-to-br from-slate-700 to-slate-900 rounded-full border border-slate-700 flex items-center justify-center text-[10px] font-bold text-slate-300">ADMIN</div>
        </div>
      </header>

      {/* 2. CONTENT AREA */}
      <main className={`flex-1 max-w-5xl mx-auto w-full px-6 transition-all duration-700 ${hasSearched ? 'pt-8' : 'pt-32'}`}>
        
        {/* Hero & Search */}
        <div className="text-center mb-10">
          {!hasSearched && (
            <div className="animate-in fade-in slide-in-from-top-4 duration-1000">
              <h2 className="text-5xl font-black mb-3 tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-white to-slate-500">
                Precision Discovery
              </h2>
              <p className="text-slate-500 mb-10 text-lg font-light tracking-wide">Milvus-backed expertise retrieval for the Department of Defense</p>
            </div>
          )}
          
          <form onSubmit={onSearch} className="relative max-w-2xl mx-auto mb-8">
            <input 
              type="text" 
              className="w-full bg-white text-slate-900 py-4 pl-14 pr-32 rounded-full text-lg shadow-[0_0_40px_rgba(0,0,0,0.5)] outline-none focus:ring-4 focus:ring-aegis-cyan/20 transition-all font-medium"
              placeholder="Search researchers, topics, or IDs..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <Search className="absolute left-5 top-4.5 text-slate-400" size={22} />
            <button 
              type="submit"
              disabled={loading}
              className="absolute right-2 top-2 bg-slate-900 hover:bg-black text-aegis-cyan px-8 py-2.5 rounded-full font-bold transition-all flex items-center gap-2 border border-slate-700"
            >
              {loading ? <Loader2 className="animate-spin" size={18} /> : "SEARCH"}
            </button>
          </form>

          {/* TAB SYSTEM - Retained here */}
          <div className="flex justify-center gap-3">
            {tabs.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-6 py-1.5 rounded-full text-[10px] font-black uppercase tracking-[0.15em] border transition-all ${
                  activeTab === tab 
                  ? 'bg-aegis-cyan border-aegis-cyan text-aegis-dark shadow-cyan-glow' 
                  : 'border-slate-800 text-slate-600 hover:border-slate-600 hover:text-slate-400'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        {/* Results View */}
        {hasSearched && !loading && results.length === 0 ? (
          <div className="text-center py-24 bg-slate-900/10 rounded-2xl border border-dashed border-slate-800/50">
            <Activity className="mx-auto text-slate-700 mb-4" size={48} />
            <p className="text-slate-600 font-mono text-xs uppercase tracking-[0.2em]">Zero intersection matches in current vector space</p>
          </div>
        ) : results.length > 0 && (
          <div className="bg-[#1a1d21]/80 backdrop-blur-sm rounded-2xl border border-slate-800 overflow-hidden shadow-2xl animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Results Header */}
            <div className="flex p-4 text-[9px] font-black text-slate-500 uppercase tracking-[0.2em] border-b border-slate-800 bg-slate-900/80">
              <div className="w-12 ml-4">Org</div>
              <div className="flex-1 ml-6">Principal Investigator / Domain</div>
              <div className="w-32 text-center">Reference Date</div>
              <div className="w-24 text-center">Metrics</div>
              <div className="w-20 text-right mr-4">H-Index</div>
            </div>
            
            {results.map((author, idx) => (
              <ResearcherRow 
                key={author.id || idx} 
                author={author} 
                onSelect={(a) => setSelectedAuthor(a)}
              />
            ))}
          </div>
        )}
      </main>

      {/* 3. FOOTER */}
      <footer className="mt-16 border-t border-slate-800/50 bg-[#0a0c10] py-8 px-6">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row justify-between items-center gap-6 opacity-40 hover:opacity-100 transition-opacity">
          <div className="flex items-center gap-6 text-[9px] font-mono uppercase tracking-widest text-slate-400">
            <div className="flex items-center gap-2"><Database size={12}/> Milvus v2.6.13</div>
            <div className="flex items-center gap-2 border-l border-slate-800 pl-6"><Activity size={12}/> Neo4j Graph Ready</div>
            <div className="flex items-center gap-2 border-l border-slate-800 pl-6 text-aegis-cyan"><BarChart3 size={12}/> System Nominal</div>
          </div>
          <div className="text-[9px] text-slate-600 font-mono tracking-[0.3em] uppercase">
            Aegis Scholar • Department of Defense Capstone • 2026
          </div>
        </div>
      </footer>

      {/* GRAPH MODAL */}
      {selectedAuthor && (
        <div className="fixed inset-0 bg-black/95 backdrop-blur-xl z-[100] flex items-center justify-center p-6 transition-all animate-in fade-in duration-300">
          <div className="bg-[#0f1115] border border-slate-800 w-full max-w-6xl h-full max-h-[85vh] rounded-3xl overflow-hidden flex flex-col shadow-[0_0_100px_rgba(0,0,0,1)]">
            <div className="p-5 border-b border-slate-800 flex justify-between items-center bg-slate-900/30">
              <div className="flex items-center gap-5">
                <div className="p-3 bg-aegis-cyan/5 rounded-xl border border-aegis-cyan/20">
                  <Users className="text-aegis-cyan" size={20} />
                </div>
                <div>
                  <h2 className="text-xl font-bold tracking-tight text-white">{selectedAuthor.name}</h2>
                  <p className="text-[10px] text-slate-600 font-mono uppercase tracking-widest">Global Graph ID: {selectedAuthor.id}</p>
                </div>
              </div>
              <button 
                onClick={() => setSelectedAuthor(null)} 
                className="p-2 hover:bg-white/5 rounded-full text-slate-500 hover:text-white transition-colors"
              >
                <X size={24} />
              </button>
            </div>
            <div className="flex-1 relative bg-black/20">
               <NetworkGraph authorId={selectedAuthor.id} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}