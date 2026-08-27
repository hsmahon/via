/**
 * Right-rail agent chat pane with streaming indicator and citation seek pills.
 * Exports `AgentPane` and supporting `AgentPaneProps`/`AgentPaneMessage` types; renders header `VIA Agent` plus `span.dot.streaming` green pulse, message list with `role-user` (right-aligned dark) vs `role-assistant` (panel), green `<button className="cite">[00:42]</button>` pills, and `Ask VIA...` textarea where `Enter` sends and `Shift+Enter` inserts newline.
 * Depends on `AgentPane.css` for boxy dark tokens and pulsing dot, `lib/useAgentStream.ts` types upstream, and optional `onSeek` to jump the video player; input is disabled when `disabled` is true (no video or not PROCESSED).
 */

"use client";

import React, { useState } from "react";
import "./AgentPane.css";

/**
 * Message displayed inside the agent pane.
 *
 * `role` distinguishes user vs assistant, `content` holds the text, and
 * `citations` are optional timestamped transcript spans rendered as seek pills.
 */
export interface AgentPaneMessage {
  /** Message role — user or assistant. */
  role: "user" | "assistant";
  /** Text content of the message. */
  content: string;
  /** Optional citations attached to assistant messages. */
  citations?: { ts: number; text: string }[];
}

/**
 * Props for the right-rail agent pane.
 *
 * `messages` and `isStreaming` drive the log and pulsing dot, `onSend` handles
 * trimmed `Enter` submission, and `disabled`/`onSeek` control input enablement
 * and citation seek jumps. Styled by `AgentPane.css`.
 */
export interface AgentPaneProps {
  /** Ordered chat history to render. */
  messages: AgentPaneMessage[];
  /** Whether the assistant is currently streaming a response. */
  isStreaming: boolean;
  /** Send handler invoked with trimmed user text on Enter. */
  onSend: (text: string) => Promise<void> | void;
  /** When true, the input is disabled (e.g. no video or status !== PROCESSED). */
  disabled?: boolean;
  /** Seek handler invoked when a citation pill is clicked with timestamp seconds. */
  onSeek?: (ts: number) => void;
}

/**
 * Format seconds as mm:ss for citation pills like [00:42].
 *
 * @param seconds - Timestamp in seconds.
 * @returns Formatted string `mm:ss` with zero padding.
 */
function formatTs(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/**
 * Workstation right-rail agent pane with streaming and citation seek.
 *
 * Renders a `VIA Agent` header with a pulsing green `span.dot.streaming`
 * when `isStreaming` is true, a scrollable message list where `role-user`
 * is right-aligned dark (`var(--panel-2)`) and `role-assistant` is a
 * `var(--panel)` block with green citation pills
 * `<button className="cite">[00:42]</button>`, and a `Ask VIA...`
 * textarea where `Enter` sends and `Shift+Enter` inserts a newline.
 * The input and send button are disabled when `disabled` is true.
 *
 * @param root0 - Component props.
 * @param root0.messages - Chat history.
 * @param root0.isStreaming - Streaming flag.
 * @param root0.onSend - Send callback.
 * @param root0.disabled - Disable flag.
 * @param root0.onSeek - Citation seek callback.
 * @returns The agent pane element.
 */
export default function AgentPane({
  messages,
  isStreaming,
  onSend,
  disabled = false,
  onSeek,
}: AgentPaneProps) {
  const [text, setText] = useState("");

  function handleSend(): void {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    void onSend(trimmed);
    setText("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <aside className="agent-pane" data-testid="agent-pane">
      <div className="agent-header">
        <span className="agent-header-title">VIA Agent</span>
        <span
          className={isStreaming ? "dot streaming" : "dot"}
          aria-label={isStreaming ? "streaming" : "idle"}
          data-testid="stream-dot"
        />
      </div>

      <div className="agent-messages" role="log" aria-live="polite">
        {messages.length === 0 ? (
          <div className="agent-empty">Ask about this video…</div>
        ) : null}
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`msg ${m.role === "user" ? "role-user" : "role-assistant"}`}
            data-role={m.role}
          >
            <div className="msg-content">{m.content}</div>
            {m.citations && m.citations.length > 0 ? (
              <div className="msg-citations">
                {m.citations.map((c, ci) => (
                  <button
                    key={ci}
                    type="button"
                    className="cite"
                    onClick={() => onSeek?.(c.ts)}
                    aria-label={`Seek to ${formatTs(c.ts)}`}
                    title={c.text}
                  >
                    [{formatTs(c.ts)}]
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>

      <div className="agent-input-row">
        <textarea
          className="agent-input"
          placeholder="Ask VIA..."
          value={text}
          disabled={disabled}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          aria-label="Ask VIA"
        />
        <button
          type="button"
          className="agent-send"
          disabled={disabled || !text.trim()}
          onClick={handleSend}
          aria-label="Send"
        >
          Send
        </button>
      </div>
    </aside>
  );
}
