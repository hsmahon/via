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
    const lower = css.toLowerCase();
    expect(lower).toMatch(/--bg:\s*#080808/);
    expect(lower).toMatch(/--panel:\s*#101010/);
    expect(lower).toMatch(/--accent:\s*#2ecc71/);
    expect(lower).toMatch(/--text:\s*#e8e8e3/);
    expect(lower).not.toMatch(/#f6f8fa/); // old light bg removed
  });
});
