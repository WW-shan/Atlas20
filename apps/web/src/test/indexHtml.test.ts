import { describe, expect, it } from "vitest";

import indexHtml from "../../index.html?raw";
import faviconSvg from "../../public/favicon.svg?raw";

describe("index.html metadata", () => {
  it("declares an existing favicon asset", () => {
    expect(indexHtml).toContain('rel="icon"');
    expect(indexHtml).toContain('href="/favicon.svg"');
    expect(faviconSvg).toContain("<svg");
  });
});
