import { describe, it, expect, vi, beforeEach } from "vitest";
import { searchAuthors } from "../../services/api";

describe("api service", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it("successfully formats author search results", async () => {
    const mockData = {
      results: [
        { id: "auth1", name: "Dr. Smith", works_count: 5, citation_count: 10 },
      ],
    };

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    });

    const results = await searchAuthors("Smith", "Authors");

    expect(results[0].name).toBe("Dr. Smith");
    expect(results[0].specialization).toContain("Works: 5");
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("q=Smith"),
    );
  });

  it("returns empty array on network error", async () => {
    global.fetch.mockRejectedValueOnce(new Error("API Down"));
    const results = await searchAuthors("Smith", "Authors");
    expect(results).toEqual([]);
  });

  it("returns empty array if tab is not Authors or Year", async () => {
    const results = await searchAuthors("Smith", "InvalidTab");
    expect(results).toEqual([]);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("handles non-OK responses (e.g., 500 error)", async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    const results = await searchAuthors("Smith", "Authors");
    expect(results).toEqual([]); // Should trigger the catch block via the throw
  });

  it("handles missing data fields by using defaults", async () => {
    const messyData = {
      results: [
        { id: null, name: null }, // Missing everything
      ],
    };

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => messyData,
    });

    const results = await searchAuthors("test");

    // This hits the "||" branches in your mapping logic
    expect(results[0].id).toBe("unknown_id");
    expect(results[0].name).toBe("Unknown Author");
    expect(results[0].works_count).toBe(0);
  });

  it("handles completely missing results key", async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({}), // No results key at all
    });

    const results = await searchAuthors("test");
    expect(results).toEqual([]); // Hits line 20: data.results || []
  });
});
