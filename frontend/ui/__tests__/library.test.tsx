import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Library from "../src/components/Library";

const v = [
  {
    video_id: "1",
    filename: "indycar_dc_250.mp4",
    status: "PROCESSED",
    duration: 83.5,
    user_id: "dev-user",
  },
];

describe("Library", () => {
  it("renders selected green edge", () => {
    render(<Library videos={v} selectedId="1" onSelect={() => {}} />);
    expect(screen.getByText("indycar_dc_250.mp4")).toBeVisible();
    expect(document.querySelector(".row-selected")).toBeTruthy();
  });
});
