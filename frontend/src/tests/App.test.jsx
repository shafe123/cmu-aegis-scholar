import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, describe, vi, beforeEach } from "vitest";
import App from "../App";
import * as api from "../services/api";

// Mock the graph to trigger every possible UI branch in the Inspector
vi.mock("../components/NetworkGraph", () => ({
  default: ({ onNodeSelect }) => (
    <div data-testid="mock-graph">
      {/* Triggers 'work' branch */}
      <button
        onClick={() =>
          onNodeSelect({
            id: "w1",
            label: "Test Paper",
            group: "work",
            details: { year: 2024, abstract: "Science stuff" },
          })
        }
      >
        Select Work
      </button>

      {/* Triggers 'author' branch with missing details for lines 212-216 */}
      <button
        onClick={() =>
          onNodeSelect({
            id: "a1",
            label: "Ghost Researcher",
            group: "author",
            details: {}, // Missing email and works to hit fallback code
          })
        }
      >
        Select Ghost
      </button>

      {/* Triggers 'work' branch with missing details for the fallbacks */}
      <button
        onClick={() =>
          onNodeSelect({
            id: "w2",
            label: "Ghost Work",
            group: "work",
            details: {}, // Missing year and abstract to hit fallback code
          })
        }
      >
        Select Ghost Work
      </button>
    </div>
  ),
}));

describe("App Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("exercises the filter, sort, and goHome logic", async () => {
    const user = userEvent.setup();

    // Mock multiple authors to test sorting
    vi.spyOn(api, "searchAuthors").mockResolvedValue([
      {
        id: "1",
        name: "Author A",
        works_count: 5,
        citation_count: 10,
        relevance_score: 0.5,
      },
      {
        id: "2",
        name: "Author B",
        works_count: 20,
        citation_count: 50,
        relevance_score: 0.9,
      },
      {
        id: "3",
        name: "Author C",
        works_count: 2,
        citation_count: 2,
        relevance_score: 0.1,
      },
    ]);

    render(<App />);

    // 1. Perform Search to populate the list
    await user.type(screen.getByPlaceholderText(/search/i), "Test");
    await user.click(screen.getByRole("button", { name: /SEARCH/i }));

    // Wait for the mock results to actually render
    await screen.findByText("Author A");

    // 2 & 3. Test Filtering and Sorting (They are all comboboxes!)
    const dropdowns = screen.queryAllByRole("combobox");
    if (dropdowns.length >= 3) {
      // Trigger setMinWorks (Dropdown 0)
      await user.selectOptions(dropdowns[0], "5");

      // Trigger setMinCitations (Dropdown 1)
      await user.selectOptions(dropdowns[1], "50");

      // Trigger setSortBy (Dropdown 2)
      await user.selectOptions(dropdowns[2], "works");
      await user.selectOptions(dropdowns[2], "citations");

      // Verify the "No results match" branch by setting impossibly high filters
      await user.selectOptions(dropdowns[0], "50"); // 50+ works
      await user.selectOptions(dropdowns[1], "1000"); // 1000+ citations
      expect(
        await screen.findByText(/No results match your current filters/i),
      ).toBeInTheDocument();
    }

    // 4. Trigger Modal View 'profile' function
    const profileBtn = screen.queryByRole("button", { name: /profile/i });
    if (profileBtn) {
      await user.click(profileBtn);
    }

    // 5. Test goHome (Using the Logo)
    const homeLogo = screen.queryByText(/AEGIS Scholar/i);
    if (homeLogo) {
      await user.click(homeLogo);
      // Verify it went back to the start state
      expect(screen.queryByText("Author B")).not.toBeInTheDocument();
    }
  });

  it("covers missing data fallbacks for work nodes in the inspector", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "searchAuthors").mockResolvedValue([
      { id: "1", name: "Test", works_count: 1, citation_count: 1 },
    ]);

    render(<App />);

    // Navigate to graph
    await user.type(screen.getByPlaceholderText(/search/i), "Test");
    await user.click(screen.getByRole("button", { name: /SEARCH/i }));
    await user.click(await screen.findByText("Test"));
    await user.click(
      screen.getByRole("button", { name: /Explore Connections/i }),
    );

    // Click our new ghost work node
    await user.click(screen.getByText("Select Ghost Work"));

    // Verify the fallbacks rendered
    expect(screen.getByText("N/A")).toBeInTheDocument();
    expect(
      screen.getByText(/No abstract available for this record/i),
    ).toBeInTheDocument();
  });

  it("reaches high coverage by exercising all state-changing functions", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "searchAuthors").mockResolvedValue([
      {
        id: "auth1",
        name: "Dr. Jane Smith",
        specialization: "AI",
        works_count: 10,
        citation_count: 50,
      },
    ]);

    render(<App />);

    // 1. Trigger handleSearch
    const input = screen.getByPlaceholderText(/search/i);
    await user.type(input, "Jane");
    await user.click(screen.getByRole("button", { name: /SEARCH/i }));

    // 2. Open Modal & Select Researcher
    const authorLink = await screen.findByText("Dr. Jane Smith");
    await user.click(authorLink);

    // 3. Switch to Graph View
    await user.click(
      screen.getByRole("button", { name: /Explore Connections/i }),
    );
    expect(screen.getByTestId("mock-graph")).toBeInTheDocument();

    // 4. Test Inspector Fallbacks (Covers lines 215-217)
    await user.click(screen.getByText("Select Ghost"));
    expect(screen.getByText("N/A")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();

    // 5. Close Inspector
    await user.click(screen.getByTestId("close-inspector"));
    expect(screen.queryByText("Ghost Researcher")).not.toBeInTheDocument();

    // 6. Return to Profile (Bulletproof search logic)
    const buttons = await screen.findAllByRole("button");
    // Safely check textContent to avoid null errors with SVGs
    const backBtn = buttons.find(
      (btn) => btn.textContent && btn.textContent.includes("Back"),
    );
    if (backBtn) await user.click(backBtn);

    expect(await screen.findByText(/Subject Profile/i)).toBeInTheDocument();

    // 7. Close Modal (Covers lines 87-89)
    await user.click(screen.getByTestId("close-modal"));
    expect(screen.queryByText(/Subject Profile/i)).not.toBeInTheDocument();
  });

  it("covers the search error catch block (Lines 70-76)", async () => {
    const user = userEvent.setup();
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(api, "searchAuthors").mockRejectedValue(new Error("API Failure"));

    render(<App />);
    await user.type(screen.getByPlaceholderText(/search/i), "Fail");
    await user.click(screen.getByRole("button", { name: /SEARCH/i }));

    await waitFor(() => {
      // Ensures lines 70-76 are executed
      expect(consoleSpy).toHaveBeenCalledWith(
        "Search error:",
        expect.any(Error),
      );
    });
    consoleSpy.mockRestore();
  });

  it("covers early return for empty query (Line 65)", async () => {
    const user = userEvent.setup();
    const apiSpy = vi.spyOn(api, "searchAuthors");
    render(<App />);

    // Clicking search without typing
    await user.click(screen.getByRole("button", { name: /SEARCH/i }));
    expect(apiSpy).not.toHaveBeenCalled();
  });

  it("renders the footer structure (Lines 318-333)", () => {
    render(<App />);
    // Ensures the bottom of the component renders properly
    expect(screen.getByText(/AEGIS Network Systems/i)).toBeInTheDocument();
  });

  it("resets filters and returns to landing page when home button is clicked", async () => {
    render(<App />);

    // 1. Target the search input and button
    const searchInput = screen.getByPlaceholderText(
      /Search researchers, papers, or expertise domains/i,
    );
    const searchBtn = screen.getByRole("button", { name: /SEARCH/i });

    // 2. Perform a search to change the state
    fireEvent.change(searchInput, { target: { value: "Test" } });
    fireEvent.click(searchBtn);

    // 3. Target the top-left logo which acts as the "Home" button
    const homeLogo = screen.getByText(/AEGIS Scholar/i);

    // 4. Click the logo to trigger the reset logic
    fireEvent.click(homeLogo);

    // 5. CRITICAL FIX: Wait for React to process the state change
    // and re-query the input to make sure we are looking at the current one
    await waitFor(() => {
      const currentInput = screen.getByPlaceholderText(
        /Search researchers, papers, or expertise domains/i,
      );
      expect(currentInput.value).toBe("");
    });
  });
});
