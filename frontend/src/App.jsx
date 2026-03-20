import React, { useState } from 'react';
import { Search, Users, FileText, Globe, Calendar, Settings, Loader2, AlertCircle } from 'lucide-react';
import { searchAuthors } from './services/api';

// Sub-component for the Individual Researcher Rows
const ResearcherRow = ({ author }) => {
  // Mapping dept codes to the specific wireframe colors
  const deptStyles = {
    USA: 'bg-black text-yellow-500 border-yellow-500/50',
    USN: 'bg-[#003147] text-white border-cyan-500/30',
    USAF: 'bg-blue-900 text-white border-blue-400/30',
    USMC: 'bg-[#544d2e] text-red-700 border-red-900/50'
  };

  return (
    <div className="bg-[#2a2f35]/50 border-b border-slate-800 p-4 flex items-center gap-6 hover:bg-slate-800/50 transition-colors group">
      <div className={`w-12 h-12 rounded-full border flex items-center justify-center font-bold text-xs shadow-lg ${deptStyles[author.dept] || 'bg-slate-700 text-slate-300'}`}>
        {author.dept || 'CIV'}
      </div>

      <div className="flex-1">
        <h3 className="text-aegis-cyan font-bold text-lg group-hover:underline cursor-pointer">
          {author.name || "Unknown Researcher"}
        </h3>
        <p className="text-slate-400 text-sm truncate max-w-md">
          {author.specialty || "Specialization and expertise summary goes here..."}
        </p>
      </div>

      <div className="text-slate-400 text-sm w-32 text-center font-mono">
        {author.last_published || '2024-03-12'}
      </div>

      {/* Mini Bar Chart Placeholder from Wireframe */}
      <div className="w-24 flex items-end gap-1 h-8 px-2">
        <div className="bg-slate-600 w-2 h-3 rounded-t-sm group-hover:bg-green-400 transition-colors"></div>
        <div className="bg-slate-600 w-2 h-6 rounded-t-sm group-hover:bg-aegis-cyan transition-colors"></div>
        <div className="bg-slate-600 w-2 h-4 rounded-t-sm group-hover:bg-blue-400 transition-colors"></div>
        <div className="bg-slate-600 w-2 h-7 rounded-t-sm group-hover:bg-aegis-cyan transition-colors"></div>
      </div>

      <div className="w-20 text-right font-mono text-xl text-slate-200 pr-4">
        {author.score || author.h_index || '0.0'}
      </div>
    </div>
  );
};

export default function App() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('Authors');

  const onSearch = async (e) => {
    e.preventDefault();
    if (!query) return;
    setLoading(true);
    try {
      const data = await searchAuthors(query);
      // Backend mapping safety net
      const finalResults = data.results || data.authors || (Array.isArray(data) ? data : []);
      setResults(finalResults);
    } catch (err) {
      console.error("Search failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-aegis-dark text-white font-sans selection:bg-aegis-cyan selection:text-navy-900">
      {/* Header */}
      <header className="p-4 flex justify-between items-center border-b border-slate-800 bg-aegis-dark/80 backdrop-blur-md sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <img src="/logo.jpg" alt="Logo" className="w-10 h-10 rounded-lg border border-aegis-cyan/30 shadow-cyan-glow" />
          <span className="font-bold tracking-[0.2em] text-sm uppercase text-slate-400">Aegis Scholar</span>
        </div>
        <div className="flex items-center gap-4">
           <button className="text-slate-500 hover:text-aegis-cyan transition-colors"><Settings size={20}/></button>
           <div className="w-8 h-8 bg-gradient-to-br from-slate-700 to-slate-900 rounded-full border border-slate-700"></div>
        </div>
      </header>

      <main className={`max-w-6xl mx-auto px-6 transition-all duration-700 ${results.length > 0 ? 'pt-8' : 'pt-32'}`}>
        <div className="text-center mb-10">
          {results.length === 0 && (
            <div className="animate-in fade-in zoom-in duration-700">
              <h2 className="text-4xl font-extrabold mb-3 tracking-tight text-slate-200">Precision Discovery</h2>
              <p className="text-slate-500 mb-10 text-lg">Milvus-backed expertise retrieval for the Department of Defense</p>
            </div>
          )}
          
          {/* Search Box */}
          <form onSubmit={onSearch} className="relative max-w-3xl mx-auto group">
            <input 
              type="text" 
              className="w-full bg-white text-slate-900 py-4 pl-14 pr-32 rounded-full text-lg shadow-2xl outline-none focus:ring-4 focus:ring-aegis-cyan/20 transition-all"
              placeholder="Search researchers, topics, or IDs..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <Search className="absolute left-5 top-4.5 text-slate-400" size={24} />
            <button 
              type="submit"
              className="absolute right-2 top-2 bg-aegis-navy hover:bg-slate-800 text-aegis-cyan px-8 py-2.5 rounded-full font-bold transition-all flex items-center gap-2"
            >
              {loading ? <Loader2 className="animate-spin" size={20} /> : "SEARCH"}
            </button>
          </form>

          {/* Wireframe Toggles */}
          <div className="flex justify-center gap-2 mt-8">
            {['Authors', 'Works', 'Orgs', 'Year'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-5 py-1.5 rounded-md text-xs font-bold uppercase tracking-wider border transition-all ${
                  activeTab === tab 
                  ? 'bg-aegis-cyan border-aegis-cyan text-aegis-dark shadow-cyan-glow' 
                  : 'border-slate-700 text-slate-500 hover:border-slate-500'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        {/* Results View */}
        {results.length > 0 && (
          <div className="bg-[#1a1d21] rounded-xl border border-slate-800 overflow-hidden shadow-2xl animate-in slide-in-from-bottom-8 duration-700">
            <div className="flex p-4 text-[10px] font-black text-slate-500 uppercase tracking-widest border-b border-slate-800 bg-slate-900/50">
              <div className="w-12 ml-4">Dept</div>
              <div className="flex-1 ml-6">Researcher / Specialization</div>
              <div className="w-32 text-center">Last Pub</div>
              <div className="w-24 text-center">Output</div>
              <div className="w-20 text-right mr-4">Expert Score</div>
            </div>
            
            {results.map((author, idx) => (
              <ResearcherRow key={author.id || idx} author={author} />
            ))}
          </div>
        )}

        {results.length > 0 && (
          <div className="mt-4 flex justify-between items-center text-[10px] font-mono text-slate-600 uppercase tracking-widest px-2">
            <div>Vector DB: Milvus 2.3</div>
            <div>Showing {results.length} of 240.2M Records</div>
          </div>
        )}
      </main>
    </div>
  );
}