import "@testing-library/jest-dom";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Automatically clean up the virtual DOM after each test to prevent memory leaks
afterEach(() => {
  cleanup();
});
