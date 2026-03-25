const VECTOR_API_URL = 'http://localhost:8002';
const BASE_API_URL = 'http://localhost:8003';


export const searchAuthors = async (query) => {
  try {
    const response = await fetch(`${VECTOR_API_URL}/search/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query_text: query,
        collection_name: "aegis_vectors", 
        limit: 10,
        output_fields: ["*"] 
      }),
    });

    if (!response.ok) throw new Error('Search failed');
    const data = await response.json();

    return (data.results || []).map(item => {
      const e = item.entity || item || {};
      
      const rawName = e.author_name || e.name || e.display_name || e.author_id;
      
      let finalName = "Unknown Researcher";

      if (rawName && typeof rawName === 'string') {
        if (rawName.startsWith('author_') && !e.author_name) {
             finalName = `Researcher ${rawName.split('-')[0].replace('author_', '').toUpperCase()}`;
        } else {
             finalName = rawName;
        }
      }

      const meta = e.metadata || {};

      return {
        id: e.author_id || e.id || item.id,
        name: finalName,
        specialization: e.specialization || "Domain Expert",
        date: e.last_updated || "2024-03-23",
        h_index: meta.h_index || e.h_index || 0,
        works_count: meta.works_count || e.works_count || e.num_abstracts || 0,
        score: item.distance ? (1 - item.distance).toFixed(2) : "0.00"
      };
    });
  } catch (err) {
    console.error("Search Error:", err);
    return [];
  }
};

export const getAuthorNetwork = async (authorId) => {
  if (!authorId) return { nodes: [], edges: [] };

  try {
    const response = await fetch(`${BASE_API_URL}/viz/author-network/${authorId}`);
    
    if (!response.ok) {
      console.warn(`Network API returned ${response.status}. Using empty graph.`);
      return { nodes: [], edges: [] };
    }
    
    return await response.json();
  } catch (err) {
    console.error("Network Fetch Error:", err);
    return { nodes: [], edges: [] };
  }
};