// Browser calls same-origin path; Nginx proxies /api to the backend service.
const MAIN_API_URL = "/api";

export const searchAuthors = async (query, activeTab = "Authors") => {
  if (activeTab !== "Authors" && activeTab !== "Year") {
    return [];
  }

  try {
    // Send a standard GET request to the Main API with search query
    const response = await fetch(
      `${MAIN_API_URL}/search/authors?q=${encodeURIComponent(query)}`,
    );

    if (!response.ok) {
      throw new Error(`HTTP Error! Status: ${response.status}`);
    }

    const data = await response.json();
    console.log("Main API Response:", data);

    const rawResults = data.results || [];

    // Map the clean data returned by Main API's Pydantic schema
    const formattedResults = rawResults.map((author) => ({
      id: author.id || "unknown_id",
      name: author.name || "Unknown Author",
      specialization: `Expertise Discovery | Works: ${author.works_count || 0} • Citations: ${author.citation_count || 0}`,
      works_count: author.works_count || 0,
      citation_count: author.citation_count || 0,
      relevance_score: author.relevance_score || 0,
    }));

    return formattedResults;
  } catch (err) {
    console.error("Main API Search Error:", err);
    return [];
  }
};
