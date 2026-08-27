/**
 * Video library list — dense technical browsing and selection surface.
 * Exports `Library` and `LibraryProps` (`videos`, `selectedId`, `onSelect`) rendering boxy 56px rows (88px thumb, mono duration, status dot) with green left-edge selection (`--accent`) and `aria-selected`.
 * Depends on `lib/status.ts` (`formatDuration`/`statusColor`) and `Library.css` tokens; composed by `Shell` center pane and driven by `page.tsx` selection state.
 */

"use client";

import React from "react";
import "./Library.css";
import { formatDuration, statusColor } from "../lib/status";
import type { Video } from "../lib/api";

/**
 * Props for the video library list.
 *
 * `videos` is rendered newest-first, `selectedId` drives the green left-edge
 * highlight and `aria-selected`, and `onSelect` wires click and keyboard
 * `↑`/`↓`/`Enter` selection. Rows are boxy `56px` grids owned by `Library.css`.
 */
export interface LibraryProps {
  /** Videos to display, newest first. */
  videos: Video[];
  /** Currently selected video id, or null when none is selected. */
  selectedId: string | null;
  /** Selection callback invoked with the chosen video id. */
  onSelect: (id: string) => void;
}

/**
 * Dense boxy video library with 56px rows, 88px thumb, and mono meta.
 *
 * Renders each video as a `div.row` grid (`88px 1fr`, `56px` height,
 * `1px solid var(--border)`) with a `div.thumb` placeholder
 * (`var(--panel-2)`), `14px` filename, and `12px` mono meta line
 * (`formatDuration` + status dot `var(--accent)` for `PROCESSED`).
 * Selected rows receive `row-selected` (`border-left: 2px solid
 * var(--accent)`, `background: var(--panel)`,
 * `box-shadow: inset 0 0 0 1px var(--accent-weak)`), `aria-selected`,
 * and keyboard `ArrowUp`/`ArrowDown` navigation via the listbox
 * container. Depends on `lib/status.ts` helpers and `Library.css` tokens.
 *
 * @param root0 - Component props.
 * @param root0.videos - Videos to render.
 * @param root0.selectedId - Selected video id.
 * @param root0.onSelect - Selection handler.
 * @returns The library list element.
 */
export default function Library({ videos, selectedId, onSelect }: LibraryProps) {
  if (videos.length === 0) {
    return (
      <div className="library-empty">No videos yet. Upload one to get started.</div>
    );
  }

  /**
   * Handle arrow key navigation across the list.
   *
   * @param event - Keyboard event from the listbox container.
   * @returns Nothing; moves selection with `ArrowDown`/`ArrowUp`.
   */
  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>): void {
    if (videos.length === 0) return;
    const idx = videos.findIndex((v) => v.video_id === selectedId);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      const next = idx < 0 ? 0 : Math.min(idx + 1, videos.length - 1);
      const target = videos[next];
      if (target) onSelect(target.video_id);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      const prev = idx < 0 ? 0 : Math.max(idx - 1, 0);
      const target = videos[prev];
      if (target) onSelect(target.video_id);
    }
  }

  return (
    <div
      className="library"
      role="listbox"
      aria-label="Video library"
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      {videos.map((video) => {
        const isSelected = video.video_id === selectedId;
        const dotClass = `dot dot-${video.status.toLowerCase()}`;
        return (
          <div
            key={video.video_id}
            role="option"
            aria-selected={isSelected}
            tabIndex={0}
            className={isSelected ? "row row-selected" : "row"}
            onClick={() => onSelect(video.video_id)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(video.video_id);
              }
            }}
          >
            <div className="thumb" aria-hidden="true" />
            <div className="row-main">
              <span className="filename">{video.filename}</span>
              <span className="meta mono">
                <span>{formatDuration(video.duration)}</span>
                <span
                  className={dotClass}
                  style={{ background: statusColor(video.status) }}
                  aria-hidden="true"
                />
                <span>{video.status}</span>
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
