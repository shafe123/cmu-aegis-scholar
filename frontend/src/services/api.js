const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "/api").replace(
  /\/$/,
  "",
);

export const buildApiUrl = (path) => {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
};

export const searchAuthors = async (query, activeTab = "Authors") => {
  if (activeTab !== "Authors" && activeTab !== "Year") {
    return [];
  }

  try {
    const response = await fetch(
      buildApiUrl(`/search/authors?q=${encodeURIComponent(query)}`),
    );

    if (!response.ok) {
      throw new Error(`HTTP Error! Status: ${response.status}`);
    }

    const data = await response.json();
    console.log("Main API Response:", data);

    const rawResults = data.results || [];

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
