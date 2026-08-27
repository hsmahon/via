import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import AgentPane from "../src/components/AgentPane";

describe("AgentPane", () => {
  it("sends message on Enter", async () => {
    const send = vi.fn(async () => {});
    render(<AgentPane messages={[]} isStreaming={false} onSend={send} />);
    fireEvent.change(screen.getByPlaceholderText("Ask VIA..."), {
      target: { value: "What is this?" },
    });
    fireEvent.keyDown(screen.getByPlaceholderText("Ask VIA..."), {
      key: "Enter",
    });
    expect(send).toHaveBeenCalled();
  });
});
