const VECTOR_API_URL = 'http://localhost:8002';

export const searchAuthors = async (query, activeTab = 'Authors') => {
  if (activeTab !== 'Authors' && activeTab !== 'Year') {
    return [];
  }

  try {
    const body = {
      query_text: query,
      collection_name: "aegis_vectors", 
      limit: 10,
      output_fields: ["author_id", "author_name", "num_abstracts", "citation_count"]
    };

    const response = await fetch(`${VECTOR_API_URL}/search/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    const data = await response.json();
    console.log("🔍 Vector DB Raw Response:", data);

    // If data.results doesn't exist, return empty array safely
    const rawResults = data.results || [];

    return rawResults.map(item => {
      // THE FIX: If Milvus wrapped it in 'entity', use that. Otherwise, use the item itself.
      const e = item.entity ? item.entity : item;
      
      return {
        id: e.author_id || "unknown_id",
        name: e.author_name || "Unknown Author",
        specialization: `Expertise Discovery | ${e.num_abstracts || 0} Abstracts • ${e.citation_count || 0} Citations`,
        h_index: "N/A" 
      };
    });
    
  } catch (err) {
    console.error("❌ Vector Search Error:", err);
    return [];
  }
};