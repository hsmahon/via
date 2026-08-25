// @ts-check
import eslint from "@eslint/js";
import tseslint from "typescript-eslint";
import jsdoc from "eslint-plugin-jsdoc";

/**
 * Root ESLint flat config for the Via monorepo.
 *
 * Enforces TypeScript best practices and JSDoc presence on exported
 * symbols (docstrings are a hard requirement across Via).
 */
export default tseslint.config(
  {
    ignores: [
      "**/node_modules/**",
      "**/.next/**",
      "**/dist/**",
      "**/coverage/**",
      "**/.venv/**",
    ],
  },
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
    },
    plugins: { jsdoc },
    rules: {
      // --- Docstring enforcement (JS equivalent of ruff's D rules) ---
      "jsdoc/require-jsdoc": [
        "error",
        {
          publicOnly: true,
          require: {
            FunctionDeclaration: true,
            ClassDeclaration: true,
            MethodDefinition: true,
          },
        },
      ],
      "jsdoc/require-description": "error",
      "jsdoc/require-param": "warn",
      "jsdoc/require-returns": "warn",
      "jsdoc/check-types": "error",
      // --- TS hygiene ---
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/consistent-type-imports": "error",
    },
  },
  {
    files: ["**/__tests__/**", "**/*.test.ts"],
    rules: {
      // Tests describe themselves with docstrings too, but we relax
      // param/return docs there.
      "jsdoc/require-param": "off",
      "jsdoc/require-returns": "off",
    },
  },
);
