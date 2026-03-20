const API_BASE_URL = 'http://localhost:8002';

export const searchAuthors = async (query) => {
  const response = await fetch(`${API_BASE_URL}/search/text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query_text: query,
      collection_name: "aegis_vectors", 
      limit: 10,
      offset: 0,
      // We explicitly ask for ALL fields to be returned
      output_fields: ["*"] 
    }),
  });

  const data = await response.json();

  return data.results.map(item => {
    const e = item.entity || {};
    
    // DEBUG: Look at your browser console (F12) to see what's actually in here!
    console.log("Full Author Entity from DB:", e);

    return {
      id: e.author_id || item.id,
      // We try every possible name field the database might use
      name: e.name || e.author_name || e.display_name || `Researcher ${e.author_id}`,
      
      // We try to find the summary/specialization
      specialization: e.specialization || e.summary || e.expertise || "Specialization info not found in DB",
      
      // We try to find the date/year
      date: e.last_updated || e.publication_year || "Unknown Date",
      
      // Pass the raw object so the UI can use anything else it finds
      ...e 
    };
  });
};