import path from "node:path";
import { fileURLToPath } from "node:url";

import js from "@eslint/js";
import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";
import reactPlugin from "eslint-plugin-react";
import reactHooksPlugin from "eslint-plugin-react-hooks";
import jsxA11yPlugin from "eslint-plugin-jsx-a11y";

const tsconfigRootDir = path.dirname(fileURLToPath(import.meta.url));

const jsxA11y = {
  ...jsxA11yPlugin,
  rules: {
    ...jsxA11yPlugin.rules,
    "aria-busy": {
      meta: {
        type: "problem",
        docs: { description: "Require literal aria-busy values to be true or false." },
        schema: [],
        messages: { invalid: "aria-busy must be true or false." },
      },
      create(context) {
        return {
          JSXAttribute(node) {
            if (node.name.name !== "aria-busy" || node.value === null) return;

            if (node.value.type === "Literal") {
              const value = String(node.value.value);
              if (value !== "true" && value !== "false") {
                context.report({ node, messageId: "invalid" });
              }
              return;
            }

            if (node.value.type === "JSXExpressionContainer") {
              const expression = node.value.expression;
              if (expression.type !== "Literal") return;
              if (typeof expression.value === "boolean") return;
              if (expression.value === "true" || expression.value === "false") return;

              context.report({ node, messageId: "invalid" });
            }
          },
        };
      },
    },
  },
};

export default [
  {
    ignores: ["dist/**", "node_modules/**"],
  },
  js.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaFeatures: { jsx: true },
        project: "./tsconfig.json",
        tsconfigRootDir,
      },
      sourceType: "module",
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
      react: reactPlugin,
      "react-hooks": reactHooksPlugin,
      "jsx-a11y": jsxA11y,
    },
    settings: {
      react: { version: "detect" },
    },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      ...reactPlugin.configs.flat.recommended.rules,
      ...reactPlugin.configs.flat["jsx-runtime"].rules,
      ...jsxA11yPlugin.configs.recommended.rules,
      "no-undef": "off",
      "react/prop-types": "off",
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "jsx-a11y/aria-busy": "error",
      "@typescript-eslint/no-unused-vars": "error",
      "@typescript-eslint/no-explicit-any": "warn",
      "react/jsx-key": "error",
    },
  },
  {
    files: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
];
