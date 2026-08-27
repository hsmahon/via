/**
 * 3-pane workstation orchestrator composing Library + VideoWorkspace + AgentPane.
 * Owns selection and collapsed state, drives `useVideos` (polling `GET /videos`), `useVideoStream` for presigned playback, and `useAgentStream` for streaming chat with `X-User-Id: dev-user`.
 * Composes `Shell`/`Sidebar`/`Library`/`VideoWorkspace`/`AgentPane` inside the CSS grid and auto-selects the first `PROCESSED` video when no selection exists.
 */

"use client";

import React, { useEffect, useState } from "react";
import AgentPane from "../components/AgentPane";
import Library from "../components/Library";
import Shell from "../components/Shell";
import Sidebar from "../components/Sidebar";
import VideoWorkspace from "../components/VideoWorkspace";
import { useAgentStream } from "../lib/useAgentStream";
import { useVideos } from "../lib/useVideos";
import { useVideoStream } from "../lib/useVideoStream";

/**
 * Home page orchestrating the 3-pane workstation.
 *
 * @returns The workstation shell with Library, VideoWorkspace, and AgentPane.
 */
export default function HomePage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const { videos } = useVideos("dev-user");
  const src = useVideoStream(selectedId);
  const { messages, streaming, send } = useAgentStream(selectedId);

  useEffect(() => {
    if (!selectedId && videos.length > 0) {
      const firstProcessed = videos.find((v) => v.status === "PROCESSED");
      const fallback = videos[0];
      if (firstProcessed) {
        setSelectedId(firstProcessed.video_id);
      } else if (fallback) {
        setSelectedId(fallback.video_id);
      }
    }
  }, [videos, selectedId]);

  const selected = videos.find((v) => v.video_id === selectedId) ?? null;

  return (
    <Shell collapsed={collapsed} onCollapsedChange={setCollapsed}>
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
      <Library videos={videos} selectedId={selectedId} onSelect={setSelectedId} />
      <VideoWorkspace video={selected} src={src} onTimeUpdate={() => {}} />
      <AgentPane
        messages={messages}
        isStreaming={streaming}
        onSend={send}
        disabled={!selected || selected.status !== "PROCESSED"}
        onSeek={() => {}}
      />
    </Shell>
  );
}
