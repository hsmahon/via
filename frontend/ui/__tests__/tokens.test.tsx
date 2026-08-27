import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";
describe("tokens", () => {
  it("globals.css defines dark workstation tokens", () => {
    const candidates = [
      "src/app/globals.css",
      "frontend/ui/src/app/globals.css",
      path.join(__dirname, "../src/app/globals.css"),
    ];
    let css = "";
    for (const p of candidates) {
      try {
        css = fs.readFileSync(p, "utf8");
        break;
      } catch {
        // try next
      }
    }
    if (!css) css = fs.readFileSync("src/app/globals.css", "utf8");
    expect(css).toMatch(/--bg:\s*#080808/);
    expect(css).toMatch(/--panel:\s*#101010/);
    expect(css).toMatch(/--accent:\s*#2ECC71/);
    expect(css).toMatch(/--text:\s*#E8E8E3/);
    expect(css).not.toMatch(/#f6f8fa/); // old light bg removed
  });
});
