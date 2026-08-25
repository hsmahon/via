import { defineConfig } from "vitest/config";

/**
 * Vitest configuration for UI unit tests (pure logic + docstring checks).
 */
export default defineConfig({
  test: {
    environment: "node",
    include: ["__tests__/**/*.test.ts"],
  },
});
