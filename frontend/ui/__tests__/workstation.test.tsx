/**
 * Workstation integration test — verifies the 3-pane composition renders.
 * Renders `HomePage` with mocked `fetch` returning an empty library, then asserts the `VIA` sidebar logo and the `Ask VIA...` agent input are visible.
 * Depends on `page.tsx` orchestration via `Shell`/`Sidebar`/`Library`/`VideoWorkspace`/`AgentPane` and `useVideos` polling `GET /videos`.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import HomePage from "../src/app/page";

describe("workstation", () => {
  it("renders 3 panes", async () => {
    global.fetch = vi.fn(
      async () =>
        ({ ok: true, json: async () => ({ items: [] }) }) as unknown as Response,
    );
    render(<HomePage />);
    expect(await screen.findByText("VIA")).toBeVisible();
    expect(screen.getByPlaceholderText("Ask VIA...")).toBeVisible();
  });
});
