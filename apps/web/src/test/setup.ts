import "@testing-library/jest-dom/vitest";
import { expect } from "vitest";
import type { AxeResults } from "axe-core";

declare module "vitest" {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  interface Assertion<T = any> {
    toHaveNoViolations(): T;
  }
  interface AsymmetricMatchersContaining {
    toHaveNoViolations(): unknown;
  }
}

expect.extend({
  toHaveNoViolations(received: AxeResults) {
    const violations = received.violations ?? [];
    const pass = violations.length === 0;
    return {
      pass,
      message: () =>
        pass
          ? "expected axe results to include violations"
          : `expected no axe violations:\n${violations.map((v) => `${v.id}: ${v.help}`).join("\n")}`,
    };
  },
});
