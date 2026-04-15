# Frontend Tests

## Running Tests

```bash
# Run all tests
npm test

# Run tests with coverage
npm run test:coverage

# Run tests in watch mode (for development)
npm run test:watch

# Run tests with UI
npm run test:ui
```

## Test Structure

```
src/tests/
├── setup.js              # Test setup and global configuration
├── components/           # Component tests
│   └── *.test.jsx
├── services/            # Service/API tests
│   └── *.test.js
└── utils/               # Utility function tests
    └── *.test.js
```

## Writing Tests

### Component Tests

Use React Testing Library for component tests:

```jsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MyComponent from "../../components/MyComponent";

describe("MyComponent", () => {
  it("renders correctly", () => {
    render(<MyComponent />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("handles user interaction", async () => {
    const user = userEvent.setup();
    render(<MyComponent />);

    await user.click(screen.getByRole("button"));
    expect(screen.getByText("Clicked")).toBeInTheDocument();
  });
});
```

### Service Tests

Mock API calls and external dependencies:

```js
import { vi } from "vitest";
import { fetchData } from "../../services/api";

describe("API Service", () => {
  it("fetches data", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ data: "test" }),
      }),
    );

    const result = await fetchData("/api/endpoint");
    expect(result).toEqual({ data: "test" });
  });
});
```

## Coverage Requirements

- Target: 80% coverage
- Thresholds configured in vitest.config.js
- View coverage report: `npm run test:coverage` then open `coverage/index.html`

## Best Practices

1. **One test, one assertion**: Keep tests focused
2. **Use semantic queries**: Prefer `getByRole`, `getByLabelText` over `getByTestId`
3. **Test behavior, not implementation**: Focus on what the user sees
4. **Mock external dependencies**: Don't make real API calls in tests
5. **Keep tests fast**: Unit tests should run in milliseconds
