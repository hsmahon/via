import { defineConfig } from "vitest/config";

/**
 * Vitest configuration for UI unit tests (pure logic + docstring checks).
 */
export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    include: ["__tests__/**/*.test.{ts,tsx}"],
    setupFiles: ["./vitest.setup.ts"],
  },
});
