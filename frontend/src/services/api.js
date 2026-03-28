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

    const formattedResults = rawResults.map(e => ({
        id: e.author_id || "unknown_id",
        name: e.author_name || "Unknown Author",
        specialization: `Expertise Discovery | Works: ${e.num_abstracts || 0} • Citations: ${e.citation_count || 0}`,
        works_count: e.num_abstracts || 0,
        citation_count: e.citation_count || 0
      }));

      return formattedResults.sort((a, b) => {
        const impactA = a.works_count > 0 ? a.citation_count / a.works_count : 0;
        const impactB = b.works_count > 0 ? b.citation_count / b.works_count : 0;
        return impactB - impactA; // Sorts descending
      });
    
  } catch (err) {
    console.error("❌ Vector Search Error:", err);
    return [];
  }
};