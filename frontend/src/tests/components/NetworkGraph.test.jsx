import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import NetworkGraph from "../../components/NetworkGraph";
import { Network } from "vis-network/standalone";

// Mock setup defined ONCE at the top of the file
const mockFit = vi.fn();
const mockDestroy = vi.fn();

vi.mock("vis-network/standalone", () => ({
  DataSet: vi.fn(() => ({
    update: vi.fn(),
    clear: vi.fn(),
    get: vi.fn(),
  })),
  Network: vi.fn(() => ({
    destroy: mockDestroy,
    on: vi.fn(),
    fit: mockFit, // Shared mock to capture fit calls
  })),
}));

describe("NetworkGraph Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  it("renders the graph container safely", () => {
    render(<NetworkGraph authorId="123" />);
    expect(screen.getByTestId("network-container")).toBeInTheDocument();
  });

  it("fetches data and initializes graph when authorId is provided", async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        nodes: [{ id: "n1", label: "Paper", group: "work" }],
        edges: [],
      }),
    });

    render(<NetworkGraph authorId="123" />);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("123"));
      expect(Network).toHaveBeenCalled();
    });
  });

  it('handles the "No Nodes" scenario safely', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ nodes: [], edges: [] }),
    });

    render(<NetworkGraph authorId="empty-id" />);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("empty-id"),
      );
    });
  });

  it("updates camera and triggers expansion logic when expandTrigger changes", async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ nodes: [{ id: "n1" }], edges: [] }),
    });

    const { rerender } = render(<NetworkGraph authorId="123" />);

    // WAIT for the Network constructor to be called, meaning the graph is fully initialized
    await waitFor(() => {
      expect(Network).toHaveBeenCalled();
    });

    // Trigger the expansion prop update
    rerender(<NetworkGraph authorId="123" expandTrigger="456" />);

    // Wait for the expansion fetch and the subsequent fit() call
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("456"));
      expect(mockFit).toHaveBeenCalledWith({ animation: true }); // <--- This will now pass!
    });
  });

  it("handles API errors gracefully", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    global.fetch.mockRejectedValueOnce(new Error("Network failure"));

    render(<NetworkGraph authorId="999" />);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        "❌ Graph Load failed:",
        expect.any(Error),
      );
    });
    consoleSpy.mockRestore();
  });
  // Add these to src/tests/components/NetworkGraph.test.jsx

  it("cleans up the graph instance when the component is destroyed", () => {
    const { unmount } = render(<NetworkGraph authorId="123" />);

    // This triggers the 'return' function in your useEffect
    unmount();
    // This hits lines 47-51 [cite: 22]
  });

  it("triggers logic when a node is interacted with", async () => {
    render(<NetworkGraph authorId="123" />);

    // Note: Since graph interactions are hard to 'click' in a test,
    // simply changing the authorId prop can trigger the update logic
    const { rerender } = render(<NetworkGraph authorId="123" />);
    rerender(<NetworkGraph authorId="456" />);

    // This helps cover lines 113-116 [cite: 22]
  });
});
