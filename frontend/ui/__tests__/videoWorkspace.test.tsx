import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import VideoWorkspace from "../src/components/VideoWorkspace";

describe("VideoWorkspace", () => {
  it("shows filename and video element when src", () => {
    render(
      <VideoWorkspace
        video={{ filename: "indycar_dc_250.mp4", video_id: "1" }}
        src="https://example.com/a.mp4"
        onTimeUpdate={() => {}}
      />,
    );
    expect(screen.getByText("indycar_dc_250.mp4")).toBeVisible();
    expect(document.querySelector("video")).toBeTruthy();
  });
});
