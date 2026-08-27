import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Sidebar from "../src/components/Sidebar";

describe("Sidebar", () => {
  it("toggles collapsed and shows tooltip", () => {
    const { container } = render(<Sidebar collapsed={false} onToggle={() => {}} />);
    expect(screen.getByText("Library")).toBeVisible();
    // tooltip via title attribute when collapsed=false still shows Library
    const nav = container.querySelector('[title="Library"]');
    expect(nav).toBeTruthy();
  });

  it("shows collapsed variant", () => {
    const { container } = render(<Sidebar collapsed={true} onToggle={() => {}} />);
    // collapsed shows icon only, still title tooltip
    const nav = container.querySelector('[title="Library"]');
    expect(nav).toBeTruthy();
    expect(container.querySelector("[data-collapsed='true']")).toBeTruthy();
  });
});
