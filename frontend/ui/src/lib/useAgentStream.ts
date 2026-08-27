/**
 * Streaming agent hook for video-grounded chat — chunked word render with citations.
 * Exports `useAgentStream(videoId)` (`messages`, `streaming`, `send`) and supporting `AgentCitation`/`AgentMessage` types; posts to `${AGENT_URL}/agent/invoke` with `X-User-Id: dev-user` and simulates streaming by splitting `answer` into words with 30ms delays.
 * Depends on `API_URL`-style `AGENT_URL` (`NEXT_PUBLIC_AGENT_URL` or `http://localhost:8081`) and is consumed by `AgentPane` inside `page.tsx` for the right-rail workstation.
 */

"use client";

import { useState } from "react";

/** Base URL of the Via agent service. */
export const AGENT_URL: string =
  process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8081";

/** Citation returned by the agent — timestamp in seconds and quoted text. */
export interface AgentCitation {
  /** Timestamp in seconds that the citation refers to. */
  ts: number;
  /** Quoted transcript text for the citation span. */
  text: string;
}

/** Chat message stored in the `useAgentStream` history. */
export interface AgentMessage {
  /** Message role — user prompt or assistant answer. */
  role: "user" | "assistant";
  /** Text content; assistant content is progressively streamed word-by-word. */
  content: string;
  /** Optional citations attached to assistant messages. */
  citations?: AgentCitation[];
}

/**
 * Hook managing agent chat history and streaming state for a single video.
 *
 * Posts `message` + `video_id` to `POST /agent/invoke`, then renders the
 * returned `answer` word-by-word (30ms per word) into an assistant message
 * so the UI shows a streaming effect. `streaming` is `true` while the fetch
 * and chunked updates are in flight.
 *
 * @param videoId - Selected video id or `null` when none is selected.
 * @returns Messages list, streaming flag, and `send` handler.
 */
export function useAgentStream(videoId: string | null): {
  messages: AgentMessage[];
  streaming: boolean;
  send: (text: string) => Promise<void>;
} {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [streaming, setStreaming] = useState(false);

  async function send(text: string): Promise<void> {
    if (!videoId) return;
    const trimmed = text.trim();
    if (!trimmed) return;
    setMessages((m) => [...m, { role: "user", content: trimmed }]);
    setStreaming(true);
    try {
      const res = await fetch(`${AGENT_URL}/agent/invoke`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-Id": "dev-user",
        },
        body: JSON.stringify({ message: trimmed, video_id: videoId }),
      });
      const data = (await res.json()) as {
        answer: string;
        citations?: AgentCitation[];
      };
      const words = (data.answer ?? "").split(" ");
      let cur = "";
      for (const w of words) {
        cur += w + " ";
        const snapshot = cur;
        const citations = data.citations;
        setMessages((m) => {
          const copy = [...m];
          const last = copy[copy.length - 1];
          if (last?.role === "assistant") {
            last.content = snapshot;
            return [...copy];
          }
          copy.push({
            role: "assistant",
            content: snapshot,
            citations,
          });
          return [...copy];
        });
        await new Promise<void>((r) => setTimeout(r, 30));
      }
    } catch {
      // Leave history as-is on network error; streaming still resets.
    } finally {
      setStreaming(false);
    }
  }

  return { messages, streaming, send };
}
